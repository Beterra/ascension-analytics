-- what survey_ids are mapped to a combined_survey_id

select
	sm.survey_id,
	c.name,
	c.type,
	c.bed_size,
	s.name as survey_name,
	s.open_at,
	s.close_at
from public.survey_mappings sm
join public.surveys s on s.id = sm.survey_id
join public.clients c on c.id = s.client_id
where sm.combined_survey_id in UNNEST(sample_combined_survey_ids)