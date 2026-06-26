# Ascension Florida — AHCA Culture of Safety Data Revalidation

This repository documents and reproduces Beterra's revalidation of Ascension
Florida's **2024 AHCA Culture of Safety** survey submission. It traces a
reverse-worded scoring error in the original submission, proves where the error
entered, quantifies its impact, and produces the figures and the written report
delivered to Ascension leadership.

The survey instrument is the **AHRQ Survey on Patient Safety Culture (SOPS),
Hospital version (HSOPS)**, fielded in September 2024 by the prior survey vendor
and entered into AHCA's macro-enabled Hospital Survey data-entry tool. The work
is scoped to the **eight hospitals** that were submitted to AHCA (an Ascension
Florida system roll-up is included only as supplementary context).

---

## 1. The finding, in plain terms

The AHRQ instrument contains **30 Likert (agree/disagree) questions**. 17 are
positively worded and **13 are negatively ("reverse") worded** — for those, the
*favorable* answer is to *disagree*.

What happened:

1. The prior vendor's data **export pre-flipped (normalized)** the 13 reverse
   items — it stored them so that the favorable answer already appeared as
   "agree" (`6 − x`).
2. AHCA's data-entry tool then applied its **own standard reverse-scoring** on
   top of the already-normalized data — a second flip.
3. The double-flip meant the 13 reverse items were scored **backwards** in the
   submission. The vendor's *own reports* were correct; the error entered only at
   the **export → AHCA-tool handoff** and was never undone before submission.

Because only the 13 reverse items are affected, correcting them changes only the
**8 composites that contain a reverse item**. The 2 composites with no reverse
items (*Communication About Error*, *Reporting Patient Safety Events*) are
**identical** in both versions — which is itself the proof that the rest of the
data is sound.

Throughout this repo:

- **raw** = *as submitted* to AHCA (the erroneous, backwards-scored version).
- **corrected** = the literal responses scored correctly (ready for resubmission).

---

## 2. Key terminology

| Term | Meaning |
|------|---------|
| **Percent positive** | Share of respondents giving a *favorable* answer (4–5 for a positive item; 1–2 for a reverse item). Neutral ("3") is **kept in the denominator** (AHRQ standard). |
| **OPPR** | *Overall Percent Positive Response* — a survey's single overall score across all scored questions. Pulled from the analytics view, not re-derived. |
| **Composite** | A group of related questions. 10 standard AHRQ composites; 8 are "affected" (contain a reverse item). |
| **Reverse / negatively-worded item** | A question where *disagreeing* is the favorable answer. There are 13: `A3, A5, A6, A7, A9, A11, A13, A14, B2, C7, F3, F4, F5`. |
| **Normalized export** | The prior vendor's export with reverse items pre-flipped (`6 − x`) — the root cause. |

---

## 3. Repository structure

```
ascension-analytics/
├── README.md                 ← this file
├── surveys.json              ← survey-ID crosswalk (facility ↔ corrected/raw survey_id)
├── ascension_mapping.csv     ← original facility/region mapping from the client
│
├── client_files/             ← RAW INPUTS from the client (source files, not edited)
│   ├── 2024_original/          the prior vendor's pipeline that produced the AHCA submission
│   │   ├── 1_perceptyx/         vendor source export (normalized) + column key
│   │   ├── 2_datatool/          AHCA macro-enabled Excel tool, one .xlsm per facility
│   │   └── 3_submission/        the CSVs actually submitted to AHCA
│   ├── 2024_clientfixed/      the client's manual recode of the same pipeline (cross-check)
│   │   ├── 1_recoded/          recoded vendor file (reverse items restored)
│   │   ├── 2_datatool/
│   │   └── 3_submission/
│   └── reports/               vendor reports, submission screenshots, emails, Tableau
│
├── data/                     ← DERIVED DATA — validated, analysis-ready CSVs (see §6)
├── figures/                  ← generated charts + the process map
├── sql/                      ← BigQuery queries (dataset: `public`) that pull official figures
├── scripts/                  ← Python that builds the derived data, charts, and the report
└── reports/                  ← the deliverable: live DRAFT, brand_template.docx, generated copy
```

**Source of truth.** Scored numbers (`raw` vs `corrected`) come from **BigQuery**,
keyed by `survey_id` — *not* from re-scoring the local `client_files/` folders.
The local files are used for the chain-of-custody trace and respondent counts;
the normalize/flip interaction makes local re-scoring ambiguous, so the warehouse
is authoritative.

---

## 4. How the project was built (data pipeline & provenance)

The work proceeded in stages; each produced an artifact that the next stage
consumed.

**Stage A — Scope the instrument.** Pin the item inventory and identify the 13
reverse-worded questions (confirmed against the AHRQ instrument and by comparing
the original vs recoded submissions respondent-by-respondent). Result:
`data/item_reference.csv` (hand-curated crosswalk of all 42 columns →
composite, scale type, polarity, reverse flag).

**Stage B — Pull official figures from BigQuery.** Pair each facility's
`corrected` and `raw` survey_ids and read percent-positive at the overall,
composite, and question levels from the unified analytics views.

- `sql/compare_corrected_vs_raw.sql` → exported as `data/compare_corrected_vs_raw.csv`
- `sql/chart_oppr_by_facility.sql` → captured as `data/oppr_by_facility.csv`

**Stage C — Prove the chain of custody.** Follow every item from the vendor's
source export through to the AHCA submission and compare against the corrected
figures, to pinpoint where the flip enters and to show that non-reverse items
never move. `scripts/build_chain_of_custody.py` reads the vendor export
(`client_files/2024_original/1_perceptyx/...xlsx`) plus the BigQuery comparison export →
`data/chain_of_custody.csv`.

**Stage D — Profile the respondents.** Counts and distributions from the local
submission CSVs. `scripts/build_profile.py` →
`data/response_profile.csv`, `data/question_counts.csv`,
`data/reverse_item_distributions.csv`, and `data/exec_snapshot.csv`
(the last sourced from the official OPPR).

**Stage E — Render the figures.** `scripts/render_oppr_by_facility.py` and
`scripts/render_emerald_composite_ppr.py` read the derived CSVs and write PNGs
to `figures/`.

**Stage F — Build the report.** `scripts/build_report.py` injects the data-driven
body into the Beterra-branded Word template, producing the generated report; the
live draft is hand-edited in `reports/`.

---

## 5. Reproducing the outputs

Requires Python 3 with `openpyxl` and `matplotlib`. BigQuery exports
(`compare_corrected_vs_raw.csv`, `oppr_by_facility.csv`) are already checked in;
regenerate them only by re-running the SQL in BigQuery and re-exporting.

```bash
# 1. Derived reference data
python3 scripts/build_chain_of_custody.py     # → data/chain_of_custody.csv
python3 scripts/build_profile.py              # → response_profile, question_counts,
                                              #   reverse_item_distributions, exec_snapshot

# 2. Figures
python3 scripts/render_oppr_by_facility.py        # → figures/oppr_facility_*.png
python3 scripts/render_emerald_composite_ppr.py   # → figures/ec_composite_*.png

# 3. Report (generated copy; the live DRAFT is edited by hand)
python3 scripts/build_report.py
```

---

## 6. `data/` data dictionary

| File | Built by | What it contains |
|------|----------|------------------|
| `item_reference.csv` | hand-authored | All 42 survey columns → AHRQ item, composite, scale type, polarity, reverse flag. The crosswalk everything else keys on. |
| `compare_corrected_vs_raw.csv` | `sql/compare_corrected_vs_raw.sql` (BigQuery export) | Official percent-positive, corrected vs raw, at composite + question level, for all 8 facilities and the system roll-up. |
| `oppr_by_facility.csv` | `sql/chart_oppr_by_facility.sql` (BigQuery) | Official OPPR per facility (corrected, raw, delta, n). |
| `chain_of_custody.csv` | `build_chain_of_custody.py` | Per facility × item × composite: vendor export %, as-submitted %, corrected %, and whether export = submission. Proves where the flip enters. |
| `exec_snapshot.csv` | `build_profile.py` (from `oppr_by_facility.csv`) | One row per facility: overall corrected vs submitted + delta. |
| `response_profile.csv` | `build_profile.py` | Respondent count per facility (+ pooled). |
| `question_counts.csv` | `build_profile.py` | Answered count per item per facility. |
| `reverse_item_distributions.csv` | `build_profile.py` | 1–5 response distribution for each of the 13 reverse items, corrected vs submitted (pooled). |

---

## 7. `scripts/` reference

| Script | Purpose |
|--------|---------|
| `build_chain_of_custody.py` | Builds `chain_of_custody.csv` from the vendor export + the BigQuery comparison. |
| `build_profile.py` | Builds the four profile/snapshot CSVs from local submissions + official OPPR. |
| `render_oppr_by_facility.py` | OPPR-by-hospital bar charts (raw / corrected / difference). |
| `render_emerald_composite_ppr.py` | Emerald Coast composite charts (stacked distributions + PPR difference). |
| `make_brand_template.py` | Rebuilds `reports/brand_template.docx` — a body-emptied brand shell derived from the live DRAFT (keeps styles, theme, header/footer, logo). Run after the DRAFT's branding changes. |
| `build_report.py` | Generates the Word report from `reports/brand_template.docx` + the derived data. Writes a separate `(generated)` file — never overwrites the hand-edited DRAFT. |

## 8. `sql/` reference (BigQuery Standard SQL, dataset `public`)

| Query | Feeds |
|-------|-------|
| `compare_corrected_vs_raw.sql` | `data/compare_corrected_vs_raw.csv` (the core impact table). |
| `chart_oppr_by_facility.sql` | `data/oppr_by_facility.csv` and the OPPR charts. |
| `chart_emerald_composite_ppr.sql` | Documents the Emerald composite PPR query (the renderer computes from the compare export). |
| `chart_emerald_composite_distribution.sql` | Documents the Emerald 1–5 distribution query (`response_breakdown`). |

> Note: the two `chart_emerald_*.sql` files document the equivalent BigQuery
> queries, but their results are not stored as standalone CSVs — the Emerald
> charts are computed from `compare_corrected_vs_raw.csv` + `item_reference.csv`,
> and the report's B2 distribution is a transcribed `response_breakdown` value.

---

## 9. Survey-ID crosswalk

Each entity has two survey_ids in BigQuery: the **corrected** load and the **raw**
(as-submitted) load. Full mapping in `surveys.json`.

| Ascension code | Facility | Region | corrected | raw |
|----------------|----------|--------|-----------|-----|
| 26012 | Sacred Heart Pensacola | Sacred Heart West | 3434 | 3443 |
| 26013 | Sacred Heart Gulf | Sacred Heart West | 3435 | 3444 |
| 26016 | Sacred Heart Emerald Coast | Sacred Heart West | 3436 | 3445 |
| 26042 | Sacred Heart Bay | Sacred Heart West | 3437 | 3446 |
| 52005 | St Vincent's Southside (St Luke) | Jacksonville East | 3438 | 3447 |
| 52009 | St Vincent's Riverside (St Vincent Medical Center) | Jacksonville East | 3439 | 3448 |
| 52012 | St Vincent's Clay County | Jacksonville East | 3440 | 3449 |
| 52015 | St Vincent's St John's County | Jacksonville East | 3441 | 3450 |
| — | Ascension Florida (system roll-up) | — | 1151 | 1152 |

---

## 10. Methodology notes & caveats

- **Neutral responses ("3") stay in the denominator** for percent-positive
  (AHRQ standard). Any query that excludes them will read a few points high.
- **The correction lives in the data, not the formula.** Once reverse items are
  in the correct orientation, a single uniform rule (favorable = 4/5 for positive
  items, 1/2 for reverse items) scores everything.
- **System roll-up is supplementary.** AHCA submission happens at the facility
  level; the system figures are included for context only.
- **Beterra's `risk_score` lens is out of scope** — this work uses only the
  standard AHRQ composites (`composite_source = 'AHRQ'`).
- The live report (`reports/Ascension AHCA COS Data Revalidation - DRAFT.docx`)
  is edited by hand; `build_report.py` writes a separate generated copy so manual
  edits are never overwritten.
