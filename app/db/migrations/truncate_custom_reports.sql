-- Migration: truncate custom reports tables
-- Reason: old block-composition definition format is incompatible with the
--         new query-builder format. Run once before deploying the new builder.
--
-- Run with:
--   psql $DATABASE_URL -f app/db/migrations/truncate_custom_reports.sql

TRUNCATE TABLE custom_report_audit;
TRUNCATE TABLE custom_reports;
