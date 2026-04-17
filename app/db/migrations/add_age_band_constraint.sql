-- Migration: define age_band controlled vocabulary and add CHECK constraint
--
-- Introduces the authorised age band vocabulary:
--   under_18 | 18_25 | 26_34 | 35_49 | 50_69 | 70_79 | 80_89 | 90_plus
--
-- The pipeline's to_age_band() function previously produced decade-band labels
-- (18_29, 30_39, 40_49, 50_59, 60_69, 70_over). These are incompatible with
-- the new vocabulary and must be nullified before the constraint is added.
--
-- Decision: old-vocabulary age_band values are SET TO NULL rather than
-- remapped. Remapping decade bands to the new non-decade bands would require
-- assumptions about member ages that cannot be reconstructed from stored labels.
-- Correct values will be recalculated on the next import cycle.
--
-- IMPORTANT: Deploy updated pipeline code BEFORE running this migration.
-- Apply with: psql $DATABASE_URL -f add_age_band_constraint.sql

BEGIN;

UPDATE members
SET age_band = NULL
WHERE age_band IS NOT NULL
  AND age_band NOT IN (
    'under_18', '18_25', '26_34', '35_49',
    '50_69',    '70_79', '80_89', '90_plus'
  );

ALTER TABLE members
    ADD CONSTRAINT ck_members_age_band
    CHECK (age_band IN (
        'under_18', '18_25', '26_34', '35_49',
        '50_69',    '70_79', '80_89', '90_plus'
    ));

COMMIT;
