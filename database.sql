-- ============================================
-- DATABASE SCHEMA
-- AI-Based Smart Patient Recognition
-- and Hospital Management System
-- ============================================

CREATE DATABASE IF NOT EXISTS hospital_management;
USE hospital_management;

-- ============================================
-- TABLE 1: patients
-- Stores patient registration details
-- ============================================
CREATE TABLE IF NOT EXISTS patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    phone VARCHAR(15) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) DEFAULT NULL,
    face_encoding LONGTEXT DEFAULT NULL,
    face_image VARCHAR(255) DEFAULT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE 2: doctors
-- Stores doctor information
-- ============================================
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100) NOT NULL,
    email VARCHAR(100) DEFAULT NULL,
    phone VARCHAR(15) DEFAULT NULL,
    available_days VARCHAR(255) DEFAULT 'Monday,Tuesday,Wednesday,Thursday,Friday',
    available_time VARCHAR(50) DEFAULT '09:00-17:00'
);

-- ============================================
-- TABLE 3: medical_records
-- Stores patient medical history
-- ============================================
CREATE TABLE IF NOT EXISTS medical_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    symptoms TEXT DEFAULT NULL,
    diagnosis TEXT DEFAULT NULL,
    prescription TEXT DEFAULT NULL,
    doctor_name VARCHAR(100) NOT NULL,
    doctor_notes TEXT DEFAULT NULL,
    visit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- ============================================
-- TABLE 4: appointments
-- Stores appointment bookings
-- ============================================
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    symptoms TEXT DEFAULT NULL,
    status ENUM('pending', 'approved', 'rejected', 'completed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE
);

-- ============================================
-- TABLE 5: chatbot_training
-- Stores AI chatbot training data (keywords + responses)
-- This is where the admin-trained responses are stored
-- ============================================
CREATE TABLE IF NOT EXISTS chatbot_training (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keywords TEXT NOT NULL COMMENT 'Comma-separated trigger words (e.g., fever, high temperature)',
    question TEXT DEFAULT NULL COMMENT 'Optional question pattern',
    answer TEXT NOT NULL COMMENT 'The AI response to give when keywords match',
    category VARCHAR(50) DEFAULT 'general' COMMENT 'symptom, general, medicine, emergency, appointment, hospital',
    urgency VARCHAR(20) DEFAULT 'low' COMMENT 'low, moderate, high',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE 6: notifications
-- Stores notification logs
-- ============================================
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    sent_via VARCHAR(20) DEFAULT 'email',
    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- ============================================
-- INSERT SAMPLE DATA
-- ============================================

-- Sample Doctors (6 specialists)
INSERT INTO doctors (name, specialization, email, phone) VALUES
('Dr. Rajesh Sharma', 'Cardiologist', 'rajesh.sharma@hospital.com', '9876543210'),
('Dr. Priya Patel', 'Neurologist', 'priya.patel@hospital.com', '9876543211'),
('Dr. Amit Verma', 'Orthopedic Surgeon', 'amit.verma@hospital.com', '9876543212'),
('Dr. Sunita Reddy', 'Pediatrician', 'sunita.reddy@hospital.com', '9876543213'),
('Dr. Vikram Singh', 'General Physician', 'vikram.singh@hospital.com', '9876543214'),
('Dr. Ananya Gupta', 'Dermatologist', 'ananya.gupta@hospital.com', '9876543215');

-- Sample Chatbot Training Data (common symptoms)
INSERT INTO chatbot_training (keywords, question, answer, category, urgency) VALUES
('fever, high temperature, body hot', 'What should I do for fever?', 'Rest, drink plenty of water, and take paracetamol if temperature exceeds 102°F. Monitor your temperature every 4 hours. If fever persists for more than 3 days or exceeds 104°F, consult a doctor immediately.', 'symptom', 'moderate'),
('headache, head pain, migraine', 'Why do I have a headache?', 'Common causes include stress, eye strain, dehydration, or lack of sleep. Rest in a dark room, apply a cold compress, and stay hydrated. If headaches are severe or recurring with vision changes, consult a neurologist.', 'symptom', 'low'),
('cough, coughing, sore throat', 'How to stop coughing?', 'Drink warm fluids like honey-lemon tea, use cough drops, and avoid cold foods. If cough persists for more than 2 weeks, produces blood, or is accompanied by high fever, consult a doctor.', 'symptom', 'low'),
('chest pain, chest tightness, heart pain', 'What causes chest pain?', '⚠️ CHEST PAIN CAN BE SERIOUS! If you have sudden chest pain with shortness of breath, sweating, or pain radiating to arm/jaw, call emergency immediately. For mild chest pain, it could be acid reflux or muscle strain.', 'emergency', 'high'),
('stomach pain, abdominal pain, belly ache', 'Why does my stomach hurt?', 'Common causes: indigestion, gas, food poisoning, or gastritis. Avoid spicy foods, eat small meals, and stay hydrated. If pain is severe, accompanied by vomiting blood, or persists for more than 2 days, see a doctor.', 'symptom', 'moderate'),
('cold, common cold, runny nose, sneezing', 'How to cure common cold?', 'Common cold usually resolves in 7-10 days. Get plenty of rest, drink warm fluids, use saline nasal spray, and take vitamin C. Over-the-counter cold medicines can help with symptoms. See a doctor if symptoms worsen after 10 days.', 'symptom', 'low');