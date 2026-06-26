-- compare_corrected_vs_raw.sql   (BigQuery Standard SQL)
-- ============================================================================
-- Pairs each entity's CORRECTED and RAW (uncorrected) survey_ids and reports
-- percent-positive side by side with the delta, at composite + question level.
-- Single statement; covers all 8 FACILITIES and the SYSTEM roll-up.
--
-- Lens (validated): dimension_type='survey', composite_source='AHRQ',
-- survey_oppr = 0-1 percent positive. survey_id_2024_raw loaded 2026-06-26.
-- Dataset is named `public`.
--
-- IMPORTANT: the facility view ALSO contains the system survey_ids (1151/1152)
-- under a small-n SOPS-1.0 scoring, so the two views must NOT be UNION-ed and
-- joined by survey_id (that fans out / mixes instruments). Facility comparison
-- uses the facility view only; system comparison uses the combined view only.
-- Resubmission scope = FACILITY level; system block is supplementary.
-- ============================================================================

-- ========================= FACILITY level (resubmission scope) =========================
WITH entity_pair AS (
  SELECT '26012' AS ascension_code, 'Sacred Heart Pensacola'                      AS facility, 3434 AS sid_corrected, 3443 AS sid_raw UNION ALL
  SELECT '26013', 'Sacred Heart Gulf',                                 3435, 3444 UNION ALL
  SELECT '26016', 'Sacred Heart Emerald Coast',                        3436, 3445 UNION ALL
  SELECT '26042', 'Sacred Heart Bay',                                  3437, 3446 UNION ALL
  SELECT '52005', 'St Vincent\'s Southside (St Luke)',                 3438, 3447 UNION ALL
  SELECT '52009', 'St Vincent\'s Riverside (St Vincent Medical Center)',3439, 3448 UNION ALL
  SELECT '52012', 'St Vincent\'s Clay County',                         3440, 3449 UNION ALL
  SELECT '52015', 'St Vincent\'s St John\'s County',                   3441, 3450
),
scores AS (
  SELECT survey_id, aggregation_level, aggregation_code, aggregation_name, survey_oppr, response_count
  FROM public.survey_oppr_and_default_benchmarks_unified_cached
  WHERE dimension_type = 'survey' AND composite_source = 'AHRQ'
    AND aggregation_level IN ('composite', 'question')
)
SELECT
  p.ascension_code, p.facility,
  c.aggregation_level, c.aggregation_code, c.aggregation_name,
  ROUND(c.survey_oppr * 100, 1)                   AS pct_corrected,
  ROUND(r.survey_oppr * 100, 1)                   AS pct_raw,
  ROUND((c.survey_oppr - r.survey_oppr) * 100, 1) AS delta_pts,   -- corrected − raw
  c.response_count AS n_corrected,
  r.response_count AS n_raw
FROM entity_pair p
JOIN      scores c ON c.survey_id = p.sid_corrected
LEFT JOIN scores r ON r.survey_id = p.sid_raw
                  AND r.aggregation_level = c.aggregation_level
                  AND r.aggregation_code  = c.aggregation_code
ORDER BY p.ascension_code, c.aggregation_level DESC, c.aggregation_code;


-- ========================= SYSTEM roll-up (supplementary) =========================
-- Combined view ONLY (clean: ten 2.0 composites, aggregation_id 29-38).
WITH s AS (
  SELECT combined_survey_id AS survey_id, aggregation_level, aggregation_code, aggregation_name,
         survey_oppr, response_count
  FROM public.combined_survey_oppr_and_default_benchmarks_unified_cached
  WHERE dimension_type = 'survey' AND composite_source = 'AHRQ'
    AND aggregation_level IN ('composite', 'question')
)
SELECT
  'SYSTEM' AS ascension_code, 'Ascension Florida' AS facility,
  c.aggregation_level, c.aggregation_code, c.aggregation_name,
  ROUND(c.survey_oppr * 100, 1)                   AS pct_corrected,
  ROUND(r.survey_oppr * 100, 1)                   AS pct_raw,
  ROUND((c.survey_oppr - r.survey_oppr) * 100, 1) AS delta_pts,
  c.response_count AS n_corrected, r.response_count AS n_raw
FROM      s c
LEFT JOIN s r ON r.aggregation_level = c.aggregation_level
             AND r.aggregation_code  = c.aggregation_code
             AND r.survey_id = 1152
WHERE c.survey_id = 1151
ORDER BY c.aggregation_level DESC, c.aggregation_code;
