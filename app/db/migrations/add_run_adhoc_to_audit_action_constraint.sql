-- Migration: add 'run_adhoc' to ck_custom_report_audit_action
--
-- The custom report builder supports ad-hoc (unsaved) query execution.
-- These runs are audited with action = 'run_adhoc', which was not included
-- in the original check constraint. This migration drops and re-adds the
-- constraint to include 'run_adhoc'.
--
-- Safe to run on a live DB — constraint change only, no data mutations.
-- Apply with: psql $DATABASE_URL -f add_run_adhoc_to_audit_action_constraint.sql

BEGIN;

ALTER TABLE custom_report_audit
    DROP CONSTRAINT IF EXISTS ck_custom_report_audit_action;

ALTER TABLE custom_report_audit
    ADD CONSTRAINT ck_custom_report_audit_action
    CHECK (action IN ('create', 'update', 'delete', 'run', 'run_adhoc'));

COMMIT;
