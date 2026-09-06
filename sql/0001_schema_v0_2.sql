-- Schema v0.2 contract. Do not reopen decisions here without an explicit user request.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE intelligence.sources (
  id uuid PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  base_url text NOT NULL,
  access_method text NOT NULL CHECK (access_method IN ('api','download','web','manual','customer_upload')),
  terms_url text,
  rights_status text NOT NULL DEFAULT 'unknown'
    CHECK (rights_status IN ('unknown','internal_only','derived_outputs_allowed','redistribution_allowed')),
  schedule text,
  enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE intelligence.ingestion_runs (
  id uuid PRIMARY KEY,
  source_id uuid NOT NULL REFERENCES intelligence.sources(id),
  idempotency_key text NOT NULL,
  connector_version text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at timestamptz,
  status text NOT NULL CHECK (status IN ('running','succeeded','partial','failed')),
  cursor_in jsonb,
  cursor_out jsonb,
  fetched_count integer NOT NULL DEFAULT 0 CHECK (fetched_count >= 0),
  error_count integer NOT NULL DEFAULT 0 CHECK (error_count >= 0),
  error_summary jsonb,
  UNIQUE (source_id, idempotency_key),
  UNIQUE (id, source_id),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE intelligence.raw_records (
  id uuid PRIMARY KEY,
  source_id uuid NOT NULL REFERENCES intelligence.sources(id),
  external_key text NOT NULL,
  source_url text,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload_uri text NOT NULL,
  content_type text NOT NULL,
  source_published_at timestamptz,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_key, payload_sha256),
  UNIQUE (id, source_id)
);

CREATE TABLE intelligence.fetch_events (
  id uuid PRIMARY KEY,
  source_id uuid NOT NULL REFERENCES intelligence.sources(id),
  run_id uuid NOT NULL,
  raw_record_id uuid,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  http_status integer CHECK (http_status BETWEEN 100 AND 599),
  error_class text CHECK (error_class IS NULL OR error_class IN (
    'http_4xx','http_5xx','timeout','dns','tls','robots','parse','other'
  )),
  error_summary jsonb,
  FOREIGN KEY (run_id, source_id) REFERENCES intelligence.ingestion_runs(id, source_id),
  FOREIGN KEY (raw_record_id, source_id) REFERENCES intelligence.raw_records(id, source_id),
  CHECK (raw_record_id IS NOT NULL OR error_class IS NOT NULL)
);
CREATE UNIQUE INDEX fetch_events_run_raw
  ON intelligence.fetch_events(run_id, raw_record_id)
  WHERE raw_record_id IS NOT NULL;

CREATE TABLE intelligence.entities (
  id uuid PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('organization','project','site','phase','asset')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, kind)
);

CREATE TABLE intelligence.organizations (
  entity_id uuid PRIMARY KEY,
  kind text NOT NULL DEFAULT 'organization' CHECK (kind = 'organization'),
  legal_name text NOT NULL,
  country_code text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
  registration_number text,
  FOREIGN KEY (entity_id, kind) REFERENCES intelligence.entities(id, kind)
);
CREATE UNIQUE INDEX organizations_reg
  ON intelligence.organizations(country_code, registration_number)
  WHERE registration_number IS NOT NULL;

CREATE TABLE intelligence.projects (
  entity_id uuid PRIMARY KEY,
  kind text NOT NULL DEFAULT 'project' CHECK (kind = 'project'),
  name_th text,
  name_en text,
  project_type text NOT NULL CHECK (project_type IN ('solar_farm','data_center')),
  country_code text NOT NULL DEFAULT 'TH' CHECK (country_code ~ '^[A-Z]{2}$'),
  FOREIGN KEY (entity_id, kind) REFERENCES intelligence.entities(id, kind),
  CHECK (NULLIF(btrim(name_th), '') IS NOT NULL OR NULLIF(btrim(name_en), '') IS NOT NULL)
);

CREATE TABLE intelligence.sites (
  entity_id uuid PRIMARY KEY,
  kind text NOT NULL DEFAULT 'site' CHECK (kind = 'site'),
  project_id uuid NOT NULL REFERENCES intelligence.projects(entity_id),
  label text,
  point geometry(Point, 4326),
  boundary geometry(MultiPolygon, 4326),
  location_accuracy_m numeric,
  location_method text,
  province_code text,
  district_code text,
  FOREIGN KEY (entity_id, kind) REFERENCES intelligence.entities(id, kind),
  CHECK (point IS NULL OR ST_IsValid(point)),
  CHECK (boundary IS NULL OR ST_IsValid(boundary))
);
CREATE INDEX sites_point_gix ON intelligence.sites USING gist(point);
CREATE INDEX sites_boundary_gix ON intelligence.sites USING gist(boundary);

CREATE TABLE intelligence.phases (
  entity_id uuid PRIMARY KEY,
  kind text NOT NULL DEFAULT 'phase' CHECK (kind = 'phase'),
  site_id uuid NOT NULL REFERENCES intelligence.sites(entity_id),
  phase_key text NOT NULL,
  label text,
  FOREIGN KEY (entity_id, kind) REFERENCES intelligence.entities(id, kind),
  UNIQUE (site_id, phase_key)
);

CREATE TABLE intelligence.entity_aliases (
  id uuid PRIMARY KEY,
  entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  alias text NOT NULL,
  language text,
  raw_record_id uuid REFERENCES intelligence.raw_records(id)
);

CREATE TABLE intelligence.evidence (
  id uuid PRIMARY KEY,
  raw_record_id uuid NOT NULL REFERENCES intelligence.raw_records(id),
  extraction_key text NOT NULL,
  subject_entity_id uuid REFERENCES intelligence.entities(id),
  predicate text NOT NULL,
  value_json jsonb NOT NULL CHECK (value_json <> 'null'::jsonb),
  excerpt text,
  locator jsonb NOT NULL,
  observed_at timestamptz,
  effective_from date,
  effective_to date,
  extractor_version text NOT NULL,
  confidence numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  review_status text NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending','accepted','rejected','superseded')),
  reviewed_by text,
  reviewed_at timestamptz,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (raw_record_id, extractor_version, extraction_key),
  UNIQUE (id, subject_entity_id),
  CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
  CHECK (review_status = 'pending' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX evidence_subject_predicate
  ON intelligence.evidence(subject_entity_id, predicate, recorded_at DESC);

CREATE TABLE intelligence.evidence_review_events (
  id uuid PRIMARY KEY,
  evidence_id uuid NOT NULL REFERENCES intelligence.evidence(id),
  from_status text NOT NULL CHECK (from_status IN ('pending','accepted','rejected','superseded')),
  to_status text NOT NULL CHECK (to_status IN ('pending','accepted','rejected','superseded')),
  actor text NOT NULL,
  reason text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE intelligence.source_entity_links (
  id uuid PRIMARY KEY,
  source_id uuid NOT NULL REFERENCES intelligence.sources(id),
  external_key text NOT NULL,
  entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  evidence_id uuid NOT NULL,
  reviewed_by text NOT NULL,
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (evidence_id, entity_id) REFERENCES intelligence.evidence(id, subject_entity_id),
  UNIQUE (source_id, external_key, entity_id)
);

CREATE TABLE intelligence.match_candidates (
  id uuid PRIMARY KEY,
  raw_record_id uuid NOT NULL REFERENCES intelligence.raw_records(id),
  candidate_entity_id uuid REFERENCES intelligence.entities(id),
  score numeric,
  reasons jsonb,
  decision text CHECK (decision IS NULL OR decision IN ('pending','accepted','rejected')),
  reviewer text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE intelligence.project_parties (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES intelligence.projects(entity_id),
  organization_id uuid NOT NULL REFERENCES intelligence.organizations(entity_id),
  role text NOT NULL,
  effective_from date,
  effective_to date,
  evidence_id uuid NOT NULL REFERENCES intelligence.evidence(id),
  CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);

CREATE TABLE intelligence.capacity_facts (
  id uuid PRIMARY KEY,
  subject_entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  metric text NOT NULL CHECK (metric IN (
    'solar_dc','solar_ac','export_limit','dc_it_load','dc_facility_power','contracted_power'
  )),
  value_mw numeric NOT NULL CHECK (value_mw > 0),
  scope text NOT NULL CHECK (scope IN ('project','phase','unknown')),
  capacity_status text NOT NULL CHECK (capacity_status IN ('planned','operating','unknown')),
  as_of_date date,
  evidence_id uuid NOT NULL REFERENCES intelligence.evidence(id)
);

CREATE TABLE intelligence.milestone_facts (
  id uuid PRIMARY KEY,
  subject_entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  milestone text NOT NULL,
  date_from date,
  date_to date,
  date_precision text NOT NULL CHECK (date_precision IN ('day','month','year','range','unknown')),
  certainty text NOT NULL CHECK (certainty IN ('planned','reported_actual','independently_verified')),
  evidence_id uuid NOT NULL REFERENCES intelligence.evidence(id),
  CHECK (date_to IS NULL OR date_from IS NULL OR date_to >= date_from)
);

CREATE TABLE intelligence.status_observations (
  id uuid PRIMARY KEY,
  subject_entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  dimension text NOT NULL CHECK (dimension IN ('commercial','regulatory','construction','operation')),
  status_code text NOT NULL,
  license_kind text CHECK (license_kind IS NULL OR license_kind IN ('erc_generation','boi_promotion','other')),
  license_external_key text,
  observed_at timestamptz NOT NULL,
  evidence_id uuid NOT NULL REFERENCES intelligence.evidence(id),
  CHECK (dimension <> 'regulatory' OR license_kind IS NOT NULL)
);

CREATE TABLE intelligence.canonical_selections (
  id uuid PRIMARY KEY,
  subject_entity_id uuid NOT NULL REFERENCES intelligence.entities(id),
  field_key text NOT NULL,
  evidence_id uuid NOT NULL,
  publication_class text NOT NULL DEFAULT 'internal'
    CHECK (publication_class IN ('internal','external')),
  selected_by text NOT NULL,
  selected_at timestamptz NOT NULL DEFAULT now(),
  superseded_at timestamptz,
  reason text NOT NULL,
  invalidation_reason text,
  FOREIGN KEY (evidence_id, subject_entity_id) REFERENCES intelligence.evidence(id, subject_entity_id),
  CHECK (superseded_at IS NULL OR superseded_at >= selected_at)
);
CREATE UNIQUE INDEX canonical_one_current
  ON intelligence.canonical_selections(subject_entity_id, field_key, publication_class)
  WHERE superseded_at IS NULL;

CREATE TABLE intelligence.predicate_registry (
  registry_version text NOT NULL,
  predicate text NOT NULL,
  subject_kinds text[] NOT NULL,
  value_schema jsonb NOT NULL,
  unit text,
  canonical_field_key text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  PRIMARY KEY (registry_version, predicate)
);

CREATE INDEX raw_source_seen ON intelligence.raw_records(source_id, first_seen_at DESC);

CREATE OR REPLACE FUNCTION intelligence.reject_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER raw_records_no_update
  BEFORE UPDATE OR DELETE ON intelligence.raw_records
  FOR EACH ROW EXECUTE FUNCTION intelligence.reject_mutation();

CREATE TRIGGER review_events_no_update
  BEFORE UPDATE OR DELETE ON intelligence.evidence_review_events
  FOR EACH ROW EXECUTE FUNCTION intelligence.reject_mutation();

INSERT INTO intelligence.predicate_registry
  (registry_version, predicate, subject_kinds, value_schema, unit, canonical_field_key)
VALUES
  ('0.2.0','capacity.dc_it_load.phase.planned', ARRAY['phase'],
   '{"type":"object","required":["value","unit","scope","capacity_status"]}'::jsonb,
   'MW','capacity.dc_it_load.phase.planned'),
  ('0.2.0','capacity.dc_it_load.project.planned', ARRAY['project'],
   '{"type":"object","required":["value","unit","scope","capacity_status"]}'::jsonb,
   'MW','capacity.dc_it_load.project.planned'),
  ('0.2.0','capacity.solar_dc.project.operating', ARRAY['project'],
   '{"type":"object","required":["value","unit","scope","capacity_status"]}'::jsonb,
   'MW','capacity.solar_dc.project.operating'),
  ('0.2.0','capacity.solar_ac.project.operating', ARRAY['project'],
   '{"type":"object","required":["value","unit","scope","capacity_status"]}'::jsonb,
   'MW','capacity.solar_ac.project.operating'),
  ('0.2.0','regulatory.erc.generation', ARRAY['project','organization'],
   '{"type":"object"}'::jsonb, NULL, 'regulatory.erc.generation'),
  ('0.2.0','regulatory.boi.promotion', ARRAY['project','organization'],
   '{"type":"object"}'::jsonb, NULL, 'regulatory.boi.promotion');
