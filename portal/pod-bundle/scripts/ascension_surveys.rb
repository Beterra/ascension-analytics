# frozen_string_literal: true

# Stubs the historical AHCA / Perceptyx "Culture of Safety" surveys onto the Ascension
# Florida facility portals created by script/ascension_portals.rb.
#
# These are HISTORICAL surveys we did NOT administer:
#   - survey_instrument: HSOPS 2 (the AHCA Hospital Survey item set, columns A1..H2)
#   - vendor: nil  (no Alchemer/Qualtrics integration; data arrives as a CSV upload)
# No response data is loaded here — this only creates the empty survey shells so a CSV
# upload has a target. The per-respondent AHCA work-area code stays with each respondent
# row at upload time (it is NOT derived from the team/department).
#
# Also creates the survey's expected respondent counts (one row per HSOPS-2-configured team,
# value 0) via Survey::CreateExpectedRespondentCounts — so run ascension_teams.rb FIRST.
#
# Idempotent: finds an existing survey by (client, name) instead of duplicating.
# Writes the resulting survey id back into surveys.json (survey_id_2026).
#
# USAGE:
#   bin/rails runner script/ascension_surveys.rb dry_run
#   bin/rails runner script/ascension_surveys.rb
#
# CONFIRM BEFORE A STAGING RUN:
#   - SURVEY_NAME and the open/close/benchmark dates are PLACEHOLDERS. Set the real
#     administration window for the COS 2024 cycle.
#   - This stubs only the 2026-folder (Perceptyx "Recoded") cycle. The earlier cycle
#     (survey_id_2024) can be added by re-running with a second config block.

dry_run = ARGV.include?("dry_run") || ARGV.include?("--dry-run")

# Maps the surveys.json ascension_code -> the portal subdomain created by ascension_portals.rb.
CODE_TO_SUBDOMAIN = {
  "26012" => "sh-pensacola",
  "26013" => "sh-gulf",
  "26016" => "sh-emerald-coast",
  "26042" => "sh-bay",
  "52005" => "stv-southside",
  "52009" => "stv-riverside",
  "52012" => "stv-clay",
  "52015" => "stv-st-johns",
}.freeze

# Administration window confirmed from the Perceptyx "Date Survey was Completed" column.
SURVEY_NAME = "AHCA Hospital Survey 2024"
OPEN_AT = Date.new(2024, 9, 3)
CLOSE_AT = Date.new(2024, 9, 30)
JSON_ID_FIELD = "survey_id_2026"

surveys_json = File.join(ENV["ASCENSION_DIR"] || File.expand_path("~/beterra/ascension-analytics"),
  "surveys.json")
records = File.exist?(surveys_json) ? JSON.parse(File.read(surveys_json)) : []

say = ->(msg) { puts(dry_run ? "[dry-run] #{msg}" : msg) }

instrument = SurveyInstrument.hsops_2
raise "HSOPS 2 survey instrument not found" if instrument.nil?

CODE_TO_SUBDOMAIN.each do |code, subdomain|
  facility = Client::Facility.find_by(subdomain: subdomain)
  if facility.nil?
    say.call "MISSING facility #{subdomain} (run ascension_portals.rb first) — skipping #{code}"
    next
  end

  Client.set(facility)
  survey = facility.surveys.find_or_initialize_by(name: SURVEY_NAME)

  if survey.persisted?
    say.call "EXISTS  survey #{subdomain}/#{SURVEY_NAME.inspect} (id=#{survey.id})"
  elsif dry_run
    say.call "CREATE  survey #{subdomain}/#{SURVEY_NAME.inspect}  [hsops_2, vendor=nil, #{OPEN_AT}..#{CLOSE_AT}]"
  else
    survey.assign_attributes(
      survey_instrument: instrument,
      vendor: nil,
      open_at: OPEN_AT,
      close_at: CLOSE_AT,
      benchmark_at: CLOSE_AT,
    )
    survey.save!
    say.call "CREATED survey #{subdomain}/#{SURVEY_NAME.inspect} (id=#{survey.id})  [Ascension code #{code}]"
  end

  # Expected respondent counts: run the same interactor the survey controller uses on create.
  # It creates one row per HSOPS-2-configured team at the team's default_expected_respondent_count
  # (0 for ours), idempotently. Zeros are fine — they establish the structure to fill in later.
  if !dry_run && survey.persisted?
    result = Survey::CreateExpectedRespondentCounts.call(survey: survey)
    if result.success?
      say.call "  expected respondent counts: #{survey.expected_respondent_counts.count} rows (value 0)"
    else
      say.call "  WARN expected respondent counts: #{result.message}"
    end
  elsif dry_run
    say.call "  would create expected respondent counts via Survey::CreateExpectedRespondentCounts"
  end

  # Record the id back into surveys.json (skipped on dry-run / when not yet persisted).
  rec = records.find { |r| r["ascension_code"] == code }
  rec[JSON_ID_FIELD] = survey.id if rec && survey.persisted?
end

if dry_run
  say.call "Done (dry-run). #{CODE_TO_SUBDOMAIN.size} facilities."
else
  File.write(surveys_json, "#{JSON.pretty_generate(records)}\n") if File.exist?(surveys_json)
  say.call "Done. Stubbed #{CODE_TO_SUBDOMAIN.size} surveys; wrote ids to #{surveys_json}"
end
