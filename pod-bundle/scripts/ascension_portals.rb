# frozen_string_literal: true

# Creates the Ascension Florida portal tree:
#   - one Client::Combined parent ("system" portal, level: client)
#   - eight Client::Facility children, each linked to the parent via act_system_id
#   - the "culture_module" entitlement on every created client (matches the admin
#     Facility-create path in ClientsController#create)
#
# Idempotent: re-running finds existing clients by subdomain instead of duplicating,
# and only links / entitles what is missing.
#
# USAGE (local dev or inside a staging pod):
#   bin/rails runner script/ascension_portals.rb dry_run   # print plan, change nothing
#   bin/rails runner script/ascension_portals.rb           # create everything
#
# In a pod:
#   kubectl cp script/ascension_portals.rb <pod>:/tmp/ascension_portals.rb
#   kubectl exec <pod> -- bundle exec rails runner /tmp/ascension_portals.rb dry_run
#
# REVIEW BEFORE A REAL RUN:
#   - bed_size / teaching are best-guess placeholders. Confirm real values: they feed
#     the benchmark buckets (Client::BED_SIZES must coordinate with benchmarks).
#   - Only the 8 hospitals are created; the non-hospital BUs in the source data
#     (MSO 26010, Medical Grp 26014, NW FL 26040, Health System 52006, Ambulatory 52007)
#     are intentionally excluded. Confirm that is correct.

dry_run = ARGV.include?("dry_run") || ARGV.include?("--dry-run")

# team_levels must be present on a Facility (validates :at_least_one_active_level).
# Mirrors the default org structure used elsewhere.
default_team_levels = {
  "unit" => "Unit",
  "division" => "Division",
  "department" => "Department",
  "service_line" => "Service Line",
}.freeze

# The parent "system" portal.
parent_attrs = {
  subdomain: "ascension-fl",
  name: "Ascension Florida",
  short_name: "Ascension FL",
}.freeze

# Children. tz: panhandle (Sacred Heart West) is Central; Jacksonville East is Eastern.
# bed_size / teaching / ccn are from the CMS Provider of Services File (Hospital & other,
# Q1 2026), field CRTFD_BED_CNT; teaching from documented ACGME residency. The CCN is resolved
# to clients.cms_hospital_id (a FK into cms_hospitals.facility_id) at runtime below.
# teaching flags marked lower-confidence — see notes in the chat thread:
#   - 26016 Emerald Coast: residency began summer 2024 (new); true only if data is >= 2024.
#   - 52005 Southside / 52012 Clay: rotation sites only; false unless "any campus" counts.
#   - 26042 Bay: no residency found; false.
facilities = [
  { code: "26012", subdomain: "sh-pensacola",     name: "Sacred Heart Pensacola",                          short_name: "SH Pensacola",     region: "Sacred Heart West", tz: "Central Time (US & Canada)", bed_size: "500+",    teaching: true,  ccn: "100025" },
  { code: "26013", subdomain: "sh-gulf",          name: "Sacred Heart Gulf",                               short_name: "SH Gulf",          region: "Sacred Heart West", tz: "Central Time (US & Canada)", bed_size: "6-24",    teaching: false, ccn: "100313" },
  { code: "26016", subdomain: "sh-emerald-coast", name: "Sacred Heart Emerald Coast",                      short_name: "SH Emerald Coast", region: "Sacred Heart West", tz: "Central Time (US & Canada)", bed_size: "50-99",   teaching: true,  ccn: "100292" },
  { code: "26042", subdomain: "sh-bay",           name: "Sacred Heart Bay",                                short_name: "SH Bay",           region: "Sacred Heart West", tz: "Central Time (US & Canada)", bed_size: "300-399", teaching: false, ccn: "100026" },
  { code: "52005", subdomain: "stv-southside",    name: "St Vincent's Southside (St Luke)",                short_name: "StV Southside",    region: "Jacksonville East", tz: "Eastern Time (US & Canada)", bed_size: "200-299", teaching: false, ccn: "100307" },
  { code: "52009", subdomain: "stv-riverside",    name: "St Vincent's Riverside (St Vincent Medical Ctr)", short_name: "StV Riverside",    region: "Jacksonville East", tz: "Eastern Time (US & Canada)", bed_size: "500+",    teaching: true,  ccn: "100040" },
  { code: "52012", subdomain: "stv-clay",         name: "St Vincent's Clay County",                        short_name: "StV Clay County",  region: "Jacksonville East", tz: "Eastern Time (US & Canada)", bed_size: "100-199", teaching: false, ccn: "100321" },
  { code: "52015", subdomain: "stv-st-johns",     name: "St Vincent's St John's County",                   short_name: "StV St John's",    region: "Jacksonville East", tz: "Eastern Time (US & Canada)", bed_size: "50-99",   teaching: false, ccn: "100361" },
].freeze

# Resolve each facility's CCN to its cms_hospitals FK once.
cms_id_for = facilities.to_h do |f|
  hosp = CmsHospital.find_by(facility_id: f[:ccn])
  warn "WARN: no cms_hospitals row for CCN #{f[:ccn]} (#{f[:subdomain]})" if hosp.nil?
  [f[:subdomain], hosp&.id]
end

say = ->(msg) { puts(dry_run ? "[dry-run] #{msg}" : msg) }

culture_module = Entitlement.find_by(key: "culture_module")
say.call "WARN: culture_module entitlement not found; clients will be created without it." if culture_module.nil?

# Idempotently attach the culture_module entitlement.
ensure_entitlement = lambda do |client|
  return if culture_module.nil? || dry_run
  return if client.entitlements.exists?(culture_module.id)

  client.entitlements << culture_module
end

ActiveRecord::Base.transaction do
  # --- Parent (Combined "system" portal) ----------------------------------
  parent = Client::Combined.find_by(subdomain: parent_attrs[:subdomain])
  if parent
    say.call "EXISTS  system  #{parent_attrs[:subdomain]} (id=#{parent.id})"
  elsif dry_run
    say.call "CREATE  system  #{parent_attrs[:subdomain]}  \"#{parent_attrs[:name]}\""
  else
    parent = Client::Combined.create!(
      subdomain: parent_attrs[:subdomain],
      name: parent_attrs[:name],
      short_name: parent_attrs[:short_name],
      level: :client,
      state: :published,
      state_code: "FL",
      time_zone: "Eastern Time (US & Canada)",
    )
    say.call "CREATED system  #{parent.subdomain} (id=#{parent.id})"
  end
  ensure_entitlement.call(parent) if parent

  # --- Facility children ---------------------------------------------------
  facilities.each do |f|
    existing = Client::Facility.find_by(subdomain: f[:subdomain])
    if existing
      # Reconcile the data-sourced fields so a re-run heals records created with old values.
      changes = {
        act_system_id: parent&.id,
        bed_size: f[:bed_size],
        teaching: f[:teaching],
        cms_hospital_id: cms_id_for[f[:subdomain]],
        state_code: "FL",
      }.select { |attr, val| existing.public_send(attr) != val }
      unless dry_run || changes.empty?
        existing.update!(changes)
        say.call "UPDATED facility #{f[:subdomain]} #{changes.keys.inspect}"
      end
      ensure_entitlement.call(existing)
      say.call "EXISTS  facility #{f[:subdomain]} (id=#{existing.id})"
      next
    end

    if dry_run
      say.call "CREATE  facility #{f[:subdomain]}  \"#{f[:name]}\"  [#{f[:region]}, #{f[:tz]}, beds #{f[:bed_size]}, teaching #{f[:teaching]}]"
      next
    end

    facility = Client::Facility.create!(
      subdomain: f[:subdomain],
      name: f[:name],
      short_name: f[:short_name],
      level: :client,
      state: :published,
      state_code: "FL",
      time_zone: f[:tz],
      bed_size: f[:bed_size],
      teaching: f[:teaching],
      cms_hospital_id: cms_id_for[f[:subdomain]],
      act_system_id: parent.id,
      team_levels: default_team_levels,
    )
    ensure_entitlement.call(facility)
    say.call "CREATED facility #{facility.subdomain} (id=#{facility.id})  [Ascension code #{f[:code]}]"
  end

  raise ActiveRecord::Rollback if dry_run
end

say.call "Done. system=#{parent_attrs[:subdomain]}, facilities=#{facilities.size}"
unless dry_run
  say.call "NOTE: surveys (survey_id_2024/2026 are null in surveys.json) and facility 'submitter'"
  say.call "      contacts still need to be created / invited per portal."
end
