-- ============================================================
-- MIGRATION 003: Doctor-to-record linkage + integrity
-- Idempotent. Target: MySQL / MariaDB 10.4+
-- ============================================================
USE hospital_management;

-- Link medical records to the creating doctor (authorization boundary)
ALTER TABLE medical_records
  ADD COLUMN IF NOT EXISTS doctor_id INT NULL,
  ADD INDEX IF NOT EXISTS idx_mr_doctor (doctor_id);

-- Index appointments by doctor for fast per-doctor access control
ALTER TABLE appointments
  ADD INDEX IF NOT EXISTS idx_appt_doctor (doctor_id);
