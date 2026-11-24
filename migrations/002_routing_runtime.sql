-- ============================================================
-- MIGRATION 002: Routing runtime columns + follow-up support
-- Idempotent. Target: MySQL / MariaDB 10.4+
-- ============================================================
USE hospital_management;

-- Appointments: extended status values + rejection/reschedule metadata
ALTER TABLE appointments
  MODIFY COLUMN status ENUM('pending','approved','rejected','completed','cancelled','rescheduled') NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS rejection_reason TEXT NULL,
  ADD COLUMN IF NOT EXISTS rescheduled_from INT NULL,
  ADD COLUMN IF NOT EXISTS appointment_type VARCHAR(20) NOT NULL DEFAULT 'regular';

-- Check-ins: link to generated token + clinical priority flag
ALTER TABLE checkins
  ADD COLUMN IF NOT EXISTS token_code VARCHAR(30) NULL,
  ADD COLUMN IF NOT EXISTS clinical_priority VARCHAR(20) NOT NULL DEFAULT 'normal';

-- Queue tokens: store the live estimated wait for display
ALTER TABLE queue_tokens
  ADD COLUMN IF NOT EXISTS est_wait_min INT NULL;

-- Consent flag for face enrollment on legacy patients (default 1 = legacy consent, documented)
ALTER TABLE patients
  ADD COLUMN IF NOT EXISTS face_consent_at TIMESTAMP NULL;

-- Follow-up status index (MariaDB 10.4: no IF NOT EXISTS on ADD INDEX, so guarded)
SET @followup_index := (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'patient_followups' AND INDEX_NAME = 'idx_followup_status');
SET @ddl := IF(@followup_index = 0,
  'ALTER TABLE patient_followups ADD INDEX idx_followup_status (status)',
  'SET @done = 1');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
