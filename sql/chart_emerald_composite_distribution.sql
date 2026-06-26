-- chart_emerald_composite_distribution.sql   (BigQuery Standard SQL)
-- ============================================================================
-- Response-value counts (1..5) per QUESTION for Emerald Coast (26016), for both
-- the as-submitted (raw, survey_id 3445) and corrected (3436) datasets, pulled
-- from the response_breakdown array. Feeds the two stacked-bar charts; the
-- renderer rolls questions up to composite via reference/item_reference.csv
-- (sum the counts across each composite's items).
--
-- For reverse-worded items the stored value differs between the two datasets
-- (normalized vs literal), so the 1-2 vs 4-5 mass swaps on affected composites
-- and is identical on unaffected ones.
-- ============================================================================
SELECT
  CASE WHEN s.survey_id = 3436 THEN 'corrected' ELSE 'as_submitted' END AS variant,
  s.aggregation_code AS item_code,
  CAST(b.raw_value AS INT64) AS response,   -- 1..5
  b.count                    AS n
FROM public.survey_oppr_and_default_benchmarks_unified_cached s,
     UNNEST(s.response_breakdown) b
WHERE s.dimension_type   = 'survey'
  AND s.composite_source = 'AHRQ'
  AND s.aggregation_level = 'question'
  AND s.survey_id IN (3436, 3445)
  AND b.raw_value IN ('1', '2', '3', '4', '5')
ORDER BY variant, item_code, response;
