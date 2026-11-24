<?php
/**
 * J Hospital - AI Chatbot API Endpoint
 * 
 * This endpoint handles chatbot conversations using Groq AI.
 * It uses a retrieval-first approach: first searches the database
 * for hospital-specific info, then sends everything to Groq.
 * 
 * Endpoint: POST /api/chat.php
 * Input: {"message": "user message"}
 * Output: {"reply": "AI response"}
 */

// Start session for conversation memory
session_start();

// Load configuration
require_once __DIR__ . '/../config.php';

// ============================================
// DATABASE CONNECTION
// ============================================
function getDbConnection() {
    try {
        $conn = new mysqli(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME);
        if ($conn->connect_error) {
            error_log("DB Connection failed: " . $conn->connect_error);
            return null;
        }
        $conn->set_charset("utf8mb4");
        return $conn;
    } catch (Exception $e) {
        error_log("DB Exception: " . $e->getMessage());
        return null;
    }
}

// ============================================
// RETRIEVAL: Search MySQL for hospital info
// ============================================
function searchHospitalInfo($userMessage) {
    $conn = getDbConnection();
    if (!$conn) {
        return [];
    }

    $results = [];
    $keywords = explode(' ', preg_replace('/[^\w\s]/', '', strtolower($userMessage)));

    // 1. Search chatbot_training table for matching keywords
    $stmt = $conn->prepare("SELECT keywords, answer, category, urgency FROM chatbot_training ORDER BY id DESC LIMIT 10");
    if ($stmt) {
        $stmt->execute();
        $trainingData = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
        $stmt->close();
        
        foreach ($trainingData as $row) {
            $rowKeywords = explode(',', strtolower($row['keywords']));
            foreach ($rowKeywords as $kw) {
                $kw = trim($kw);
                if (!empty($kw) && strpos($userMessage, $kw) !== false) {
                    $results[] = [
                        'type' => 'trained_response',
                        'category' => $row['category'],
                        'urgency' => $row['urgency'],
                        'content' => $row['answer']
                    ];
                    break;
                }
            }
        }
    }

    // 2. Search doctors table
    $stmt = $conn->prepare("SELECT name, specialization, email, phone FROM doctors ORDER BY name");
    if ($stmt) {
        $stmt->execute();
        $doctors = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
        $stmt->close();

        // Check if user is asking about doctors
        $doctorKeywords = ['doctor', 'doctor', 'physician', 'specialist', 'consult', 'appointment'];
        if (array_intersect($keywords, $doctorKeywords)) {
            $doctorList = [];
            foreach ($doctors as $doc) {
                $doctorList[] = "- Dr. {$doc['name']} ({$doc['specialization']})";
            }
            if (!empty($doctorList)) {
                $results[] = [
                    'type' => 'hospital_info',
                    'category' => 'doctors',
                    'content' => "**Available Doctors at J Hospital:**\n" . implode("\n", $doctorList)
                ];
            }
        }
    }

    // 3. Search departments/services from training data
    $serviceKeywords = ['service', 'department', 'facility', 'treatment', 'care', 'clinic'];
    if (array_intersect($keywords, $serviceKeywords)) {
        // Use training data results as services
        $services = [];
        foreach ($trainingData ?? [] as $row) {
            if ($row['category'] === 'hospital') {
                $services[] = "- " . ucfirst(str_replace('_', ' ', $row['category']));
            }
        }
        if (!empty($services)) {
            $results[] = [
                'type' => 'hospital_info',
                'category' => 'services',
                'content' => "**J Hospital Services:**\n" . implode("\n", array_unique($services))
            ];
        }
    }

    $conn->close();
    return $results;
}

// ============================================
// BUILD SYSTEM PROMPT
// ============================================
function buildSystemPrompt($hospitalInfo) {
    $prompt = "You are MediCare AI, the official AI medical assistant for J Hospital.\n\n";
    $prompt .= "ROLE:\n";
    $prompt .= "- Answer ALL medical and health-related questions in a complete, structured and easy-to-understand way.\n";
    $prompt .= "- Cover: symptoms, diseases, first aid, self-care, lab tests, nutrition, fitness, mental health,\n";
    $prompt .= "  maternal and child care, medicines (educational info only), and hospital services.\n\n";
    $prompt .= "LANGUAGE RULES (IMPORTANT):\n";
    $prompt .= "- Detect the language the user writes in and ALWAYS answer in that SAME language (all languages supported).\n";
    $prompt .= "- Never reply in English when the user wrote in another language.\n\n";
    $prompt .= "STYLE (VERY IMPORTANT - ANSWER SHORTLY, SIMPLY AND PERFECTLY):\n";
    $prompt .= "- Keep every answer SHORT, SIMPLE and to the point - give the person exactly what they need, nothing more.\n";
    $prompt .= "- Answer confidently and directly without hesitation. Start with the key answer in **bold**, then add at most 3-5 short bullet points if useful.\n";
    $prompt .= "- Use **bold text** for the main answer and important words so the user can scan instantly. Never repeat the question back at length.\n";
    $prompt .= "- Explain medical terms in plain language.\n\n";
    $prompt .= "SAFETY (MUST ALWAYS HOLD):\n";
    $prompt .= "- Never prescribe medications or give a definitive diagnosis - recommend consulting a doctor.\n";
    $prompt .= "- For EMERGENCY symptoms (chest pain, trouble breathing, stroke signs, heavy bleeding,\n";
    $prompt .= "  seizures, unconsciousness, severe allergic reactions): advise calling 108/911 immediately.\n";
    $prompt .= "- Never tell users to ignore symptoms or delay care.\n";
    $prompt .= "- Remind users you are an AI assistant, not a replacement for a doctor.\n";
    $prompt .= "- If asked about J Hospital-specific information that is unavailable, respond: \"I couldn't find that information. Please contact J Hospital reception for assistance.\"\n";

    // Add retrieved hospital information as context
    if (!empty($hospitalInfo)) {
        $prompt .= "\n\nHOSPITAL INFORMATION (Use this to answer user questions):\n";
        foreach ($hospitalInfo as $info) {
            $prompt .= "\n" . $info['content'] . "\n";
        }
    }

    return $prompt;
}

// ============================================
// BUILD CONVERSATION HISTORY
// ============================================
function getConversationHistory() {
    $history = [];
    
    // System prompt will be added by the caller
    if (isset($_SESSION['chat_history']) && is_array($_SESSION['chat_history'])) {
        $history = $_SESSION['chat_history'];
    }
    
    return $history;
}

function saveConversationHistory($role, $content) {
    if (!isset($_SESSION['chat_history'])) {
        $_SESSION['chat_history'] = [];
    }
    
    $_SESSION['chat_history'][] = [
        'role' => $role,
        'content' => $content
    ];
    
    // Keep only last N messages
    if (count($_SESSION['chat_history']) > SESSION_MAX_MESSAGES) {
        $_SESSION['chat_history'] = array_slice($_SESSION['chat_history'], -SESSION_MAX_MESSAGES);
    }
}

// ============================================
// CALL GROQ API
// ============================================
function callGroqAPI($systemPrompt, $conversationHistory, $userMessage) {
    $apiKey = GROQ_API_KEY;
    
    // Check if API key is set
    if (empty($apiKey) || $apiKey === 'gsk_your_api_key_here') {
        return [
            'success' => false,
            'error' => 'Groq API key not configured. Please set GROQ_API_KEY in config.php'
        ];
    }
    
    // Build messages array
    $messages = [
        [
            'role' => 'system',
            'content' => $systemPrompt
        ]
    ];
    
    // Add conversation history
    foreach ($conversationHistory as $msg) {
        $messages[] = $msg;
    }
    
    // Add current user message
    $messages[] = [
        'role' => 'user',
        'content' => $userMessage
    ];
    
    // Prepare request payload
    $payload = [
        'model' => 'openai/gpt-oss-120b',
        'messages' => $messages,
        'temperature' => 0.4,
        'max_tokens' => 1200,
        'top_p' => 0.95,
        'stream' => false
    ];
    
    // Initialize cURL
    $ch = curl_init('https://api.groq.com/openai/v1/chat/completions');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . $apiKey
        ],
        CURLOPT_TIMEOUT => 30,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_SSL_VERIFYPEER => true
    ]);
    
    // Execute request
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlError = curl_error($ch);
    curl_close($ch);
    
    // Handle cURL errors
    if ($curlError) {
        error_log("Groq API cURL error: " . $curlError);
        return [
            'success' => false,
            'error' => 'API connection error'
        ];
    }
    
    // Parse response
    $result = json_decode($response, true);
    
    if ($httpCode === 200 && isset($result['choices'][0]['message']['content'])) {
        return [
            'success' => true,
            'reply' => $result['choices'][0]['message']['content']
        ];
    } else {
        $errorMsg = isset($result['error']['message']) ? $result['error']['message'] : 'Unknown API error';
        error_log("Groq API error (HTTP $httpCode): " . $errorMsg);
        
        // Fallback: Try alternative model
        if (strpos($errorMsg, 'model') !== false || strpos($errorMsg, 'not found') !== false) {
            $payload['model'] = 'openai/gpt-oss-20b';
            $ch = curl_init('https://api.groq.com/openai/v1/chat/completions');
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_POST => true,
                CURLOPT_POSTFIELDS => json_encode($payload),
                CURLOPT_HTTPHEADER => [
                    'Content-Type: application/json',
                    'Authorization: Bearer ' . $apiKey
                ],
                CURLOPT_TIMEOUT => 30
            ]);
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);
            
            if ($httpCode === 200) {
                $result = json_decode($response, true);
                if (isset($result['choices'][0]['message']['content'])) {
                    return [
                        'success' => true,
                        'reply' => $result['choices'][0]['message']['content']
                    ];
                }
            }
        }
        
        return [
            'success' => false,
            'error' => 'AI service error'
        ];
    }
}

// ============================================
// INPUT SANITIZATION
// ============================================
function sanitizeInput($input) {
    // Trim whitespace
    $input = trim($input);
    
    // Limit message length
    if (strlen($input) > MAX_MESSAGE_LENGTH) {
        $input = substr($input, 0, MAX_MESSAGE_LENGTH);
    }
    
    // Strip HTML tags
    $input = strip_tags($input);
    
    // Escape for safe output
    $input = htmlspecialchars($input, ENT_QUOTES, 'UTF-8');
    
    return $input;
}

// ============================================
// MAIN REQUEST HANDLER
// ============================================

// Set JSON content type
header('Content-Type: application/json');

// Only accept POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['reply' => 'Invalid request method.']);
    exit;
}

// Get and parse input
$input = file_get_contents('php://input');
$data = json_decode($input, true);

if (!$data || !isset($data['message'])) {
    echo json_encode(['reply' => 'No message received.']);
    exit;
}

// Sanitize user message
$userMessage = sanitizeInput($data['message']);

// Check for empty message
if (empty($userMessage)) {
    echo json_encode(['reply' => 'Please enter a valid message.']);
    exit;
}

// Save user message to session
saveConversationHistory('user', $userMessage);

// STEP 1: Search database for hospital-specific information (Retrieval-first)
$hospitalInfo = searchHospitalInfo($userMessage);

// STEP 2: Build system prompt with retrieved context
$systemPrompt = buildSystemPrompt($hospitalInfo);

// STEP 3: Get conversation history
$conversationHistory = getConversationHistory();

// STEP 4: Call Groq API
$apiResult = callGroqAPI($systemPrompt, $conversationHistory, $userMessage);

// STEP 5: Return response
if ($apiResult['success']) {
    $reply = $apiResult['reply'];
    
    // Save assistant reply to session
    saveConversationHistory('assistant', $reply);
    
    echo json_encode(['reply' => $reply]);
} else {
    // Graceful error handling
    echo json_encode(['reply' => 'Sorry, the AI assistant is temporarily unavailable. Please try again later.']);
}
?>
