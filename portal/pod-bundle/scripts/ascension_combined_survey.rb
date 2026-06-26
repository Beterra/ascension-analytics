# frozen_string_literal: true

# Creates a CombinedSurvey on the Ascension Florida parent portal (ascension-fl) that rolls up
# all 8 facility "AHCA Hospital Survey 2024" surveys, then recalculates it.
#
# Idempotent: finds the combined survey by (parent client, name) and only adds member surveys
# that aren't already mapped. Re-running also re-recalculates (picks up any newly imported
# responses), so it's safe to run again after the facility result uploads finish.
#
# USAGE:
#   bin/rails runner script/ascension_combined_survey.rb
#   bin/rails runner script/ascension_combined_survey.rb dry_run
#
# Run AFTER the parent portal + facility surveys exist (and, ideally, after the facility
# results are imported so the rollup has data — but it can be re-run later to recalculate).

dry_run = ARGV.include?("dry_run") || ARGV.include?("--dry-run")

PARENT_SUBDOMAIN = "ascension-fl"
SURVEY_NAME = "AHCA Hospital Survey 2024"
FACILITY_SUBDOMAINS = %w[sh-pensacola sh-gulf sh-emerald-coast sh-bay
  stv-southside stv-riverside stv-clay stv-st-johns].freeze
OPEN_AT = Date.new(2024, 9, 3)
CLOSE_AT = Date.new(2024, 9, 30)

say = ->(msg) { puts(dry_run ? "[dry-run] #{msg}" : msg) }

parent = Client::Combined.find_by(subdomain: PARENT_SUBDOMAIN)
abort "Parent portal #{PARENT_SUBDOMAIN} not found (run ascension_portals.rb first)" if parent.nil?
Client.set(parent)

instrument = SurveyInstrument.hsops_2
abort "HSOPS 2 instrument not found" if instrument.nil?

# Collect the 8 facility surveys.
member_surveys = FACILITY_SUBDOMAINS.filter_map do |sub|
  facility = Client::Facility.find_by(subdomain: sub)
  next say.call("MISSING facility #{sub} — skipping") if facility.nil?

  survey = facility.surveys.find_by(name: SURVEY_NAME)
  next say.call("no survey #{SURVEY_NAME.inspect} for #{sub} — skipping") if survey.nil?

  survey
end
say.call "Found #{member_surveys.size} facility surveys to roll up."

combined = CombinedSurvey.find_or_initialize_by(client_id: parent.id, name: SURVEY_NAME)
if combined.persisted?
  say.call "EXISTS  combined survey #{SURVEY_NAME.inspect} (id=#{combined.id})"
elsif dry_run
  say.call "CREATE  combined survey #{SURVEY_NAME.inspect} on #{parent.subdomain}"
else
  combined.assign_attributes(
    survey_instrument: instrument,
    open_at: OPEN_AT,
    close_at: CLOSE_AT,
    benchmark_at: CLOSE_AT,
    access_at: OPEN_AT,
    client_admin_access_at: CLOSE_AT,
  )
  combined.save!
  say.call "CREATED combined survey #{SURVEY_NAME.inspect} (id=#{combined.id})"
end

unless dry_run
  existing_ids = combined.survey_ids
  member_surveys.each do |survey|
    if existing_ids.include?(survey.id)
      say.call "  already mapped: survey #{survey.id} (#{survey.client.subdomain})"
    else
      combined.add_survey(survey)
      say.call "  added survey #{survey.id} (#{survey.client.subdomain})"
    end
  end
  combined.recalculate
  say.call "Recalculated. Combined survey #{combined.id} now spans #{combined.surveys.count} facility surveys."
end

if dry_run
  say.call "Would roll up #{member_surveys.size} surveys: #{member_surveys.map { |s| s.client.subdomain }.join(', ')}"
end
