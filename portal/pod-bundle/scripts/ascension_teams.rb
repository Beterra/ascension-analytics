# frozen_string_literal: true

# Creates the team backbone for the 8 Ascension Florida facilities from the Perceptyx org
# structure, and assigns each leaf team its majority AHCA work area + domain.
#
# Source: ascension_teams_2024.csv (generated from the Sept-2024 Perceptyx file), columns:
#   business_unit_id, location_name, department_name, respondents, dominant_ahca_wa, wa_matched_respondents
#
# Hierarchy (per the facility team_levels set in ascension_portals.rb):
#   Location Name   -> Team::Organizational level :department  (parent)
#   Department Name -> Team::Organizational level :unit        (leaf; respondents attach here)
#
# Work area / domain is stored per survey-instrument in TeamSurveyConfiguration (HSOPS 2),
# NOT on the team (work_area_id/domain_id are ignored columns). Each leaf unit gets the
# majority AHCA work area observed for its department; the per-respondent work area still
# travels with each respondent at upload time. Expected respondent counts are NOT set here
# (we only have actuals) — they attach later as ExpectedRespondentCount(survey, team).
#
# Idempotent: teams are found by (client, name); configs by (team, survey_instrument).
#
# USAGE:
#   bin/rails runner script/ascension_teams.rb dry_run
#   bin/rails runner script/ascension_teams.rb
#
# Run AFTER ascension_portals.rb (needs the facility clients).

require "csv"

dry_run = ARGV.include?("dry_run") || ARGV.include?("--dry-run")

CODE_TO_SUBDOMAIN = {
  "26012" => "sh-pensacola", "26013" => "sh-gulf", "26016" => "sh-emerald-coast",
  "26042" => "sh-bay", "52005" => "stv-southside", "52009" => "stv-riverside",
  "52012" => "stv-clay", "52015" => "stv-st-johns",
}.freeze

TEAMS_CSV = File.join(ENV["ASCENSION_DIR"] || File.expand_path("~/beterra/ascension-analytics"),
  "ascension_teams_2024.csv")
SOURCE_VERSION_ID = -1

instrument = SurveyInstrument.hsops_2
raise "HSOPS 2 instrument not found" if instrument.nil?

# Resolve a WorkArea (and its Domain) for an AHCA work-area code. Prefer the variant that has a
# domain attached, since several codes have a domain-less duplicate.
wa_by_code = {}
WorkArea.hsops_2.includes(:domain).each do |w|
  code = w.ahrq_wa.to_s
  next if code.empty?
  cur = wa_by_code[code]
  wa_by_code[code] = w if cur.nil? || (cur.domain.nil? && w.domain)
end

say = ->(msg) { puts(dry_run ? "[dry-run] #{msg}" : msg) }

rows = CSV.read(TEAMS_CSV, headers: true)
by_facility = rows.group_by { |r| r["business_unit_id"] }

stats = Hash.new(0)

by_facility.each do |code, frows|
  subdomain = CODE_TO_SUBDOMAIN[code]
  facility = subdomain && Client::Facility.find_by(subdomain: subdomain)
  if facility.nil?
    say.call "MISSING facility for code #{code} (#{subdomain}) — skipping"
    next
  end
  Client.set(facility)

  # Track names already used in this facility so leaf names stay unique (validates uniqueness
  # of name scoped to client). Seed with location names, which we create first.
  used_names = {}

  upsert = lambda do |name, level, parent_id|
    team = Team::Organizational.where(client: facility).find_or_initialize_by(name: name)
    existed = team.persisted?
    team.assign_attributes(level: level, parent_team_id: parent_id, source_version_id: SOURCE_VERSION_ID)
    team.save! unless dry_run
    stats[existed ? :team_existing : :team_created] += 1
    used_names[name] = true
    team
  end

  # Disambiguate a leaf department name against names already used in this facility.
  unique_name = lambda do |base, location|
    return base unless used_names.key?(base)
    candidate = "#{base} (#{location})"
    return candidate unless used_names.key?(candidate)
    i = 2
    i += 1 while used_names.key?("#{candidate} #{i}")
    "#{candidate} #{i}"
  end

  frows.group_by { |r| r["location_name"] }.each do |location, lrows|
    location_team = upsert.call(location, :department, nil)
    say.call "  dept  #{facility.subdomain}/#{location.inspect} (id=#{location_team&.id})"

    lrows.each do |r|
      dept = r["department_name"]
      name = unique_name.call(dept, location)
      unit = upsert.call(name, :unit, location_team&.id)

      wa_code = r["dominant_ahca_wa"].to_s.strip
      work_area = wa_by_code[wa_code]
      domain = work_area&.domain
      if work_area
        unless dry_run
          TeamSurveyConfiguration.find_or_initialize_by(team: unit, survey_instrument: instrument).
            update!(domain: domain, work_area: work_area)
        end
        stats[:wa_assigned] += 1
      else
        stats[:wa_missing] += 1
        say.call "    WARN no work area for #{facility.subdomain}/#{name.inspect} (code=#{wa_code.inspect})"
      end
      say.call "    unit  #{name.inspect} -> WA #{wa_code} #{work_area&.name} / domain #{domain&.code}"
    end
  end
  say.call "FACILITY #{facility.subdomain}: #{frows.size} units under #{frows.map { |r| r['location_name'] }.uniq.size} locations"
end

say.call "Done. teams created=#{stats[:team_created]} existing=#{stats[:team_existing]} " \
         "work_area_assigned=#{stats[:wa_assigned]} work_area_missing=#{stats[:wa_missing]}"
