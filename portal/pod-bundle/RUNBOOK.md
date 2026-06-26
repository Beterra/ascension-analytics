# Ascension Florida — pod deploy runbook

Self-contained bundle to stand up the 8 Ascension FL hospital portals, their team backbones,
the historical **AHCA Hospital Survey 2024** (Sept 3–30, 2024) surveys, a combined rollup
survey, and the response data — by copying this folder into a pod and running 5 scripts in order.

All scripts are **idempotent** and accept `dry_run` to preview. They read their data files from
`$ASCENSION_DIR` (set it to wherever you copy this bundle).

## 1. Copy the bundle into the pod

```bash
kubectl cp pod-bundle <pod>:/tmp/ascension
```

## 2. Run, in order (from the Rails app root inside the pod)

Set `ASCENSION_DIR` so the scripts find the copied data. Preview each with `dry_run`, then run for real.

```bash
export ASCENSION_DIR=/tmp/ascension

# 1) Portals — 1 Combined parent (ascension-fl) + 8 Facility children.
#    Bed size / teaching / CCN are baked in; CCN resolves to cms_hospitals at runtime.
bin/rails runner /tmp/ascension/scripts/ascension_portals.rb dry_run
bin/rails runner /tmp/ascension/scripts/ascension_portals.rb

# 2) Teams — Location -> department, Department -> unit; majority AHCA work area per unit.
#    Needs ascension_teams_2024.csv (in this bundle). Run AFTER portals.
bin/rails runner /tmp/ascension/scripts/ascension_teams.rb dry_run
bin/rails runner /tmp/ascension/scripts/ascension_teams.rb

# 3) Surveys — one "AHCA Hospital Survey 2024" per facility (HSOPS 2, no vendor),
#    plus expected respondent counts (value 0). Run AFTER teams.
bin/rails runner /tmp/ascension/scripts/ascension_surveys.rb dry_run
bin/rails runner /tmp/ascension/scripts/ascension_surveys.rb

# 4) Combined survey — rolls all 8 facility surveys up onto the ascension-fl parent.
#    Safe to re-run later to recalculate after the result uploads finish.
bin/rails runner /tmp/ascension/scripts/ascension_combined_survey.rb dry_run
bin/rails runner /tmp/ascension/scripts/ascension_combined_survey.rb

# 5) Results upload — queues the CORRECT (raw) CSVs to Sidekiq (fire-and-forget).
#    Sidekiq runs the import and the calculation it auto-triggers. Needs Sidekiq workers running.
bin/rails runner /tmp/ascension/scripts/ascension_upload_results.rb dry_run
bin/rails runner /tmp/ascension/scripts/ascension_upload_results.rb
```

After step 5, re-run step 4 (`ascension_combined_survey.rb`) once the facility imports finish, so
the combined rollup picks up the responses.

## Notes

- **Correct vs flipped.** `upload/results/correct/` holds the raw respondent values — the app
  reverse-scores negatively-worded items itself, so these reproduce the true Perceptyx report
  composites (validated: Riverside Staffing 49.9%, Response to Error 57.5%, etc.). `flipped/`
  has the 15 reverse items pre-inverted; loading it reproduces AHCA's mis-scored (depressed)
  numbers. **Upload `correct/`.** To load flipped instead:
  `ascension_upload_results.rb /tmp/ascension/upload/results/flipped`.
- **One facility at a time** (e.g. to test): append a subdomain, e.g.
  `ascension_upload_results.rb stv-riverside`.
- **Re-running upload** re-imports; respondents/responses dedupe on `VENDOR_UID`, so it updates
  in place rather than duplicating.
- Regenerating the CSVs (`ascension_results.rb`) is a **local** step (needs the Perceptyx workbook
  + roo) and is intentionally NOT in this pod bundle.
```
