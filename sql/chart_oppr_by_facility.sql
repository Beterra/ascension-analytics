-- chart_oppr_by_facility.sql   (BigQuery Standard SQL)
-- ============================================================================
-- Official OPPR (Overall Percent Positive Response) per facility, AS SUBMITTED
-- (raw) vs CORRECTED, plus the difference. Feeds Table 4 and the OPPR-by-facility
-- chart set (render_oppr_by_facility.py).
--
-- OPPR is the view's OWN survey-level overall: aggregation_level='overall',
-- dimension_type='survey', composite_source='AHRQ' (the 10 standard composites;
-- AHRQ-S is the supplemental single-items and is NOT used here).
-- ============================================================================
WITH pair AS (
  SELECT '26012' AS code, 'Sacred Heart Pensacola'                       AS facility, 3434 AS sid_corr, 3443 AS sid_raw UNION ALL
  SELECT '26013', 'Sacred Heart Gulf',                                   3435, 3444 UNION ALL
  SELECT '26016', 'Sacred Heart Emerald Coast',                         3436, 3445 UNION ALL
  SELECT '26042', 'Sacred Heart Bay',                                   3437, 3446 UNION ALL
  SELECT '52005', 'St Vincent\'s Southside (St Luke)',                  3438, 3447 UNION ALL
  SELECT '52009', 'St Vincent\'s Riverside (St Vincent Medical Center)', 3439, 3448 UNION ALL
  SELECT '52012', 'St Vincent\'s Clay County',                          3440, 3449 UNION ALL
  SELECT '52015', 'St Vincent\'s St John\'s County',                    3441, 3450
),
oppr AS (
  SELECT survey_id, survey_oppr
  FROM public.survey_oppr_and_default_benchmarks_unified_cached
  WHERE aggregation_level = 'overall'
    AND dimension_type    = 'survey'
    AND composite_source  = 'AHRQ'
)
SELECT
  p.code, p.facility,
  ROUND(c.survey_oppr * 100, 1)                 AS oppr_corrected,
  ROUND(r.survey_oppr * 100, 1)                 AS oppr_raw,
  ROUND((c.survey_oppr - r.survey_oppr) * 100, 1) AS delta
FROM pair p
JOIN oppr c ON c.survey_id = p.sid_corr
JOIN oppr r ON r.survey_id = p.sid_raw
ORDER BY oppr_corrected DESC;
