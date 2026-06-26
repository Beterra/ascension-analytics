# frozen_string_literal: true

# Queues the import of pre-generated Ascension results CSVs (fire-and-forget). This is the
# POD script: copy a directory of per-facility CSVs into the pod and run this. It does NOT
# generate anything and has no dependency on the Perceptyx workbook or roo — it only reads
# the small <subdomain>.csv files and enqueues an Import::Result for each. Sidekiq runs the
# import and the calculation it auto-triggers (survey -> ready) in the background.
#
# The CSVs are produced locally by script/ascension_results.rb (the "correct" version is the
# one to upload; "flipped" reproduces AHCA's mis-scored view).
#
# USAGE:
#   bin/rails runner script/ascension_upload_results.rb /path/to/csv_dir
#   bin/rails runner script/ascension_upload_results.rb /path/to/csv_dir stv-riverside   # one facility
#   bin/rails runner script/ascension_upload_results.rb /path/to/csv_dir dry_run         # preview only
# If no dir is given, defaults to ~/beterra/ascension-analytics/upload/results/correct.

SURVEY_NAME = "AHCA Hospital Survey 2024"
SUBDOMAINS = %w[sh-pensacola sh-gulf sh-emerald-coast sh-bay stv-southside stv-riverside stv-clay stv-st-johns].freeze

dry_run   = ARGV.include?("dry_run")
default_base = ENV["ASCENSION_DIR"] || File.expand_path("~/beterra/ascension-analytics")
dir       = ARGV.find { |a| File.directory?(a) } ||
            File.join(default_base, "upload/results/correct")
only_subs = ARGV & SUBDOMAINS
subs      = only_subs.empty? ? SUBDOMAINS : only_subs

puts "Upload dir: #{dir}#{' [dry-run]' if dry_run}"
abort "Directory not found: #{dir}" unless File.directory?(dir)

subs.each do |sub|
  csv = File.join(dir, "#{sub}.csv")
  unless File.exist?(csv)
    puts "  SKIP #{sub}: no file at #{csv}"
    next
  end
  facility = Client::Facility.find_by(subdomain: sub) or (puts "  MISSING facility #{sub}"; next)
  Client.set(facility)
  survey = facility.surveys.find_by(name: SURVEY_NAME) or (puts "  no survey #{SURVEY_NAME.inspect} for #{sub}"; next)

  if dry_run
    puts "  would import #{File.basename(csv)} -> survey #{survey.id} (#{sub})"
    next
  end

  import = Import::Result.new(client: facility, survey: survey)
  import.file.attach(io: File.open(csv), filename: "#{sub}.csv", content_type: "text/csv")
  import.save! # after_commit enqueues ResultsWorker; on completion it auto-triggers the calculation
  puts "  #{sub}: queued import ##{import.id} -> survey #{survey.id}"
end

puts(dry_run ? "Done (dry-run)." : "All imports queued. Sidekiq will import + calculate in the background.")
