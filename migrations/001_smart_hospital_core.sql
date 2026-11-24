-- ============================================================
-- MIGRATION 001: Smart Patient Check-In & Rule-Based Routing
-- Safe to re-run (idempotent). Target: MySQL / MariaDB 10.4+
-- ============================================================
USE hospital_management;

-- 1) Security / extended profile columns -----------------------
ALTER TABLE patients
  ADD COLUMN IF NOT EXISTS date_of_birth DATE NULL,
  ADD COLUMN IF NOT EXISTS gender VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS address TEXT NULL,
  ADD COLUMN IF NOT EXISTS blood_group VARCHAR(10) NULL,
  ADD COLUMN IF NOT EXISTS emergency_contact VARCHAR(15) NULL,
  ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS consent_status TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

ALTER TABLE doctors
  ADD COLUMN IF NOT EXISTS password VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS is_active TINYINT(1) NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 2) Departments -------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
  department_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT NULL,
  operating_hours VARCHAR(100) DEFAULT '09:00-18:00',
  capacity_per_day INT DEFAULT 50,
  is_active TINYINT(1) DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS doctor_departments (
  doctor_id INT NOT NULL,
  department_id INT NOT NULL,
  PRIMARY KEY (doctor_id, department_id),
  FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
  FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS doctor_schedules (
  schedule_id INT AUTO_INCREMENT PRIMARY KEY,
  doctor_id INT NOT NULL,
  week_day VARCHAR(20) NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  is_active TINYINT(1) DEFAULT 1,
  FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
  INDEX idx_sched_doctor_day (doctor_id, week_day)
);

-- 3) Check-ins ----------------------------------------------------
CREATE TABLE IF NOT EXISTS checkins (
  checkin_id INT AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  appointment_id INT NULL,
  checkin_method VARCHAR(20) NOT NULL,
  verification_status VARCHAR(20) NOT NULL DEFAULT 'verified',
  checkin_status VARCHAR(20) NOT NULL DEFAULT 'checked_in',
  assigned_department_id INT NULL,
  routing_log_id INT NULL,
  checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id) ON DELETE SET NULL,
  FOREIGN KEY (assigned_department_id) REFERENCES departments(department_id) ON DELETE SET NULL,
  INDEX idx_checkin_patient (patient_id),
  INDEX idx_checkin_status (checkin_status)
);

-- 4) Rules ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS routing_rules (
  rule_id INT AUTO_INCREMENT PRIMARY KEY,
  rule_code VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  description TEXT NULL,
  condition_json TEXT NULL,
  action_json TEXT NULL,
  priority INT DEFAULT 100,
  is_active TINYINT(1) DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routing_logs (
  routing_id INT AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  appointment_id INT NULL,
  rule_id INT NULL,
  assigned_department_id INT NULL,
  queue_category VARCHAR(30) NOT NULL DEFAULT 'regular',
  decision_reason TEXT NULL,
  recorded_by VARCHAR(50) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  FOREIGN KEY (rule_id) REFERENCES routing_rules(rule_id) ON DELETE SET NULL,
  FOREIGN KEY (assigned_department_id) REFERENCES departments(department_id) ON DELETE SET NULL,
  INDEX idx_routing_patient (patient_id)
);

-- 5) Queue tokens -------------------------------------------------
CREATE TABLE IF NOT EXISTS queue_tokens (
  token_id INT AUTO_INCREMENT PRIMARY KEY,
  token_code VARCHAR(30) NOT NULL UNIQUE,
  patient_id INT NOT NULL,
  department_id INT NOT NULL,
  doctor_id INT NULL,
  checkin_id INT NULL,
  queue_category VARCHAR(30) NOT NULL DEFAULT 'regular',
  status VARCHAR(20) NOT NULL DEFAULT 'waiting',
  position INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  called_at TIMESTAMP NULL,
  completed_at TIMESTAMP NULL,
  is_active INT GENERATED ALWAYS AS (CASE WHEN status IN ('waiting','called','consulting') THEN 1 ELSE NULL END) STORED,
  UNIQUE KEY uq_active_token (patient_id, department_id, is_active),
  FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  FOREIGN KEY (department_id) REFERENCES departments(department_id),
  FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE SET NULL,
  FOREIGN KEY (checkin_id) REFERENCES checkins(checkin_id) ON DELETE SET NULL,
  INDEX idx_token_dept_status (department_id, status)
);

CREATE TABLE IF NOT EXISTS queue_events (
  event_id INT AUTO_INCREMENT PRIMARY KEY,
  token_id INT NOT NULL,
  event_type VARCHAR(30) NOT NULL,
  note TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (token_id) REFERENCES queue_tokens(token_id) ON DELETE CASCADE,
  INDEX idx_event_token (token_id)
);

-- 6) QR appointment tokens -----------------------------------------
CREATE TABLE IF NOT EXISTS appointment_qr_tokens (
  qr_id INT AUTO_INCREMENT PRIMARY KEY,
  appointment_id INT NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at DATETIME NULL,
  used_at DATETIME NULL,
  is_revoked TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id) ON DELETE CASCADE,
  INDEX idx_qr_appointment (appointment_id)
);

-- 7) Chronic follow-up management ----------------------------------
CREATE TABLE IF NOT EXISTS patient_followups (
  followup_id INT AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  appointment_id INT NULL,
  department_id INT NOT NULL,
  doctor_id INT NOT NULL,
  followup_date DATE NOT NULL,
  followup_time TIME NULL,
  instructions TEXT NULL,
  status VARCHAR(20) DEFAULT 'scheduled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id) ON DELETE SET NULL,
  FOREIGN KEY (department_id) REFERENCES departments(department_id),
  FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
  INDEX idx_followup_patient (patient_id),
  INDEX idx_followup_date (followup_date)
);

-- 8) Audit log -----------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id INT AUTO_INCREMENT PRIMARY KEY,
  user_type VARCHAR(20) NULL,
  user_id INT NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(50) NULL,
  entity_id VARCHAR(50) NULL,
  details TEXT NULL,
  ip_address VARCHAR(45) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_audit_user (user_type, user_id),
  INDEX idx_audit_entity (entity_type, entity_id),
  INDEX idx_audit_time (created_at)
);

-- 9) Notification delivery logs ------------------------------------
CREATE TABLE IF NOT EXISTS notification_delivery_logs (
  log_id INT AUTO_INCREMENT PRIMARY KEY,
  notification_type VARCHAR(50) NOT NULL,
  recipient_type VARCHAR(20) NOT NULL,
  recipient_id INT NULL,
  channel VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  error_message TEXT NULL,
  attempts INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_notif_recipient (recipient_type, recipient_id)
);

-- ============================================================
-- SEED DATA (idempotent)
-- ============================================================

INSERT INTO departments (name, description, operating_hours, capacity_per_day) VALUES
('General Medicine', 'Primary care and general medical consultations', '09:00-18:00', 60),
('Cardiology', 'Heart and cardiovascular care', '09:00-18:00', 40),
('Orthopaedics', 'Bone, joint and muscle care', '09:00-18:00', 40),
('Paediatrics', 'Child health and care', '09:00-18:00', 40),
('Neurology', 'Brain, spine and nervous system care', '09:00-18:00', 30),
('Dermatology', 'Skin, hair and nail care', '09:00-18:00', 40),
('ENT', 'Ear, nose and throat care', '09:00-18:00', 40),
('Ophthalmology', 'Eye care', '09:00-18:00', 40)
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'Cardiology') FROM doctors WHERE specialization LIKE '%Cardi%';
INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'Neurology') FROM doctors WHERE specialization LIKE '%Neur%';
INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'Orthopaedics') FROM doctors WHERE specialization LIKE '%Orth%';
INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'Paediatrics') FROM doctors WHERE specialization LIKE '%Ped%';
INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'General Medicine') FROM doctors WHERE specialization LIKE '%General%';
INSERT IGNORE INTO doctor_departments (doctor_id, department_id)
SELECT doctor_id, (SELECT department_id FROM departments WHERE name = 'Dermatology') FROM doctors WHERE specialization LIKE '%Dermat%';

INSERT INTO routing_rules (rule_code, name, description, condition_json, action_json, priority, is_active) VALUES
('RULE 001', 'Approved appointment routes to doctor department', 'If appointment is approved and doctor is available, route to the doctor department.', '{"appointment_status":"approved","doctor_available":true}', '{"action":"route_to_department","queue":"regular"}', 10, 1),
('RULE 002', 'Cancelled/rejected appointment blocks check-in', 'If appointment is cancelled or rejected, prevent normal check-in and show the reason.', '{"appointment_status":["cancelled","rejected"]}', '{"action":"block_checkin","show_reason":true}', 5, 1),
('RULE 003', 'No appointment offers walk-in', 'If appointment does not exist, offer walk-in registration.', '{"appointment_exists":false}', '{"action":"offer_walkin","queue":"walkin"}', 10, 1),
('RULE 004', 'Approved follow-up routes to follow-up workflow', 'If patient has an approved follow-up appointment, route to assigned follow-up workflow.', '{"appointment_type":"followup","appointment_status":"approved"}', '{"action":"route_to_followup","queue":"followup"}', 20, 1),
('RULE 005', 'Doctor unavailable stops routing', 'If doctor is unavailable, notify reception and offer rescheduling or approved alternative.', '{"doctor_available":false}', '{"action":"reception_intervention","notify":true}', 8, 1),
('RULE 006', 'Department unavailable requires reception', 'If department is unavailable, prevent automatic routing and request reception intervention.', '{"department_available":false}', '{"action":"reception_intervention","auto_route":false}', 8, 1),
('RULE 007', 'Clinically assigned priority goes first', 'If a clinician assigns urgent priority, send for immediate clinical assessment.', '{"clinical_priority":"urgent"}', '{"action":"immediate_assessment","queue":"priority"}', 5, 1),
('RULE 008', 'Active check-in prevents duplication', 'If an active check-in already exists, retrieve existing token and prevent duplicate.', '{"has_active_checkin":true}', '{"action":"return_existing_token"}', 5, 1),
('RULE 009', 'Regular appointment queue', 'If patient is a regular appointment, assign the appropriate regular queue.', '{"appointment_type":"regular"}', '{"action":"assign_queue","queue":"regular"}', 40, 1),
('RULE 010', 'Walk-in scheduling workflow', 'If patient is a walk-in, assign walk-in registration and scheduling workflow.', '{"appointment_type":"walkin"}', '{"action":"walkin_scheduling","queue":"walkin"}', 40, 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);
