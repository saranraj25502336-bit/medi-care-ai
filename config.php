<?php
/**
 * Configuration File
 * J Hospital - AI Chatbot Configuration
 */

// ============================================
// GROQ API Configuration
// ============================================
// Get your free API key from: https://console.groq.com/keys
define('GROQ_API_KEY', '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');

// ============================================
// MySQL Database Configuration
// ============================================
define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASSWORD', '');
define('DB_NAME', 'hospital_management');

// ============================================
// Session Configuration
// ============================================
define('SESSION_MAX_MESSAGES', 20);
define('MAX_MESSAGE_LENGTH', 2000);