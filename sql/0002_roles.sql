-- Local/dev roles. Passwords are unused under local trust auth.
-- Re-run is safe.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'epi_migration') THEN
    CREATE ROLE epi_migration LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'epi_ingestion') THEN
    CREATE ROLE epi_ingestion LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'epi_review') THEN
    CREATE ROLE epi_review LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'epi_product_read') THEN
    CREATE ROLE epi_product_read LOGIN;
  END IF;
END $$;

GRANT CONNECT ON DATABASE intelligence TO epi_migration, epi_ingestion, epi_review, epi_product_read;
GRANT USAGE, CREATE ON SCHEMA intelligence TO epi_migration;
GRANT USAGE ON SCHEMA intelligence TO epi_ingestion, epi_review, epi_product_read;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON ALL TABLES IN SCHEMA intelligence TO epi_migration;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO epi_migration;

GRANT SELECT ON ALL TABLES IN SCHEMA intelligence TO epi_ingestion, epi_review, epi_product_read;

GRANT INSERT ON intelligence.sources, intelligence.ingestion_runs, intelligence.raw_records,
  intelligence.fetch_events, intelligence.entities, intelligence.organizations, intelligence.projects,
  intelligence.sites, intelligence.phases, intelligence.entity_aliases, intelligence.evidence,
  intelligence.match_candidates, intelligence.project_parties, intelligence.capacity_facts,
  intelligence.milestone_facts, intelligence.status_observations
  TO epi_ingestion;

GRANT UPDATE (ended_at, status, cursor_out, fetched_count, error_count, error_summary)
  ON intelligence.ingestion_runs TO epi_ingestion;

GRANT INSERT, UPDATE ON intelligence.evidence TO epi_review;
GRANT INSERT ON intelligence.evidence_review_events, intelligence.source_entity_links,
  intelligence.canonical_selections, intelligence.match_candidates TO epi_review;
GRANT UPDATE ON intelligence.canonical_selections, intelligence.match_candidates TO epi_review;

REVOKE INSERT, UPDATE, DELETE ON intelligence.canonical_selections FROM epi_ingestion;
REVOKE INSERT, UPDATE, DELETE ON intelligence.evidence_review_events FROM epi_ingestion;

ALTER DEFAULT PRIVILEGES FOR ROLE epi_migration IN SCHEMA intelligence
  GRANT SELECT ON TABLES TO epi_product_read, epi_ingestion, epi_review;
