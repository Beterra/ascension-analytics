-- chart_emerald_composite_ppr.sql   (BigQuery Standard SQL)
-- ============================================================================
-- Data for the Emerald Coast (26016) composite chart set: percent-positive by
-- composite, AS SUBMITTED (raw, survey_id 3445) vs CORRECTED (3436), plus the
-- difference. Feeds scripts/render_emerald_composite_ppr.py (raw / corrected /
-- difference bar charts, 10 composites).
--
-- "affected" = composite contains >=1 reverse-worded item (8 of 10); the two
-- unaffected composites (Communication About Error, Reporting Patient Safety
-- Events) are flagged so the renderer can de-emphasize them.
-- ============================================================================
WITH s AS (
  SELECT survey_id, aggregation_code, aggregation_name, survey_oppr
  FROM public.survey_oppr_and_default_benchmarks_unified_cached
  WHERE dimension_type = 'survey'
    AND composite_source = 'AHRQ'
    AND aggregation_level = 'composite'
    AND survey_id IN (3436, 3445)         -- 3436 corrected, 3445 raw (Emerald Coast)
)
SELECT
  c.aggregation_code  AS composite_code,
  c.aggregation_name  AS composite_name,
  ROUND(r.survey_oppr * 100, 1)                   AS ppr_raw,
  ROUND(c.survey_oppr * 100, 1)                   AS ppr_corrected,
  ROUND((c.survey_oppr - r.survey_oppr) * 100, 1) AS ppr_difference,
  c.aggregation_code NOT IN ('FCE', 'RPSE')       AS affected
FROM      s c
JOIN      s r ON r.aggregation_code = c.aggregation_code AND r.survey_id = 3445
WHERE c.survey_id = 3436
ORDER BY ppr_corrected DESC;
