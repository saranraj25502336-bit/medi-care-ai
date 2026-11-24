# ============================================
# AI CHATBOT MODULE
# MediCare AI Medical Assistant
# Multilingual - General medical AI - Voice ready
# Backed by Groq LLMs (GPT-OSS) + Whisper STT
# ============================================

import json
import re
import time
import requests
from config import Config
from database import get_all_training_data


class MedicalChatbot:
    """Multilingual, general-purpose medical AI assistant (Groq-powered)."""

    # Verified available Groq chat models (Nov 2026)
    PRIMARY_MODEL = "openai/gpt-oss-120b"
    FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
    STT_MODEL = "whisper-large-v3-turbo"

    # Emergency messages in major languages (used when AI is unreachable)
    EMERGENCY_MSGS = {
        'en': "EMERGENCY! Call 108 (India) / 911 (US) NOW! Get medical help immediately!",
        'hi': "आपातकाल! अभी 108/911 पर कॉल करें! तुरंत चिकित्सा सहायता लें!",
        'ta': "அவசரம்! உடனடியாக 108/911 ஐ அழைக்கவும்! உடனே மருத்துவ உதவி பெறுங்கள்!",
        'te': "అత్యవసరం! వెంటనే 108/911 కి కాల్ చేయండి! వైద్య సహాయం పొందండి!",
        'bn': "জরুরি অবস্থা! এখনই ১০৮/৯১১ কল করুন! অবিলম্বে চিকিৎসা সহায়তা নিন!",
        'mr': "आणीबाणी! आत्ताच १०८/९११ वर कॉल करा! लगेच वैद्यकीय मदत घ्या!",
        'gu': "કટોકટી! હમણાં જ 108/911 પર કૉલ કરો! તાત્કાલિક તબીબી મદદ મેળવો!",
        'ur': "ایمرجنسی! ابھی 108/911 پر کال کریں! فوری طبی امداد حاصل کریں!",
        'es': "EMERGENCIA! Llama al 108/911 AHORA! Busca ayuda medica de inmediato!",
        'fr': "URGENCE ! Appelez le 108/911 MAINTENANT ! Obtenez une aide medicale immediate !",
        'de': "NOTFALL! Rufen Sie jetzt 108/911 an! Holen Sie sofort medizinische Hilfe!",
        'ar': "طارئ! اتصل بـ 108/911 الآن! احصل على مساعدة طبية فورا!",
        'pt': "EMERGENCIA! Ligue para 108/911 AGORA! Procure ajuda medica imediatamente!",
        'ru': "СРОЧНО! Звоните 108/911 СЕЙЧАС! Немедленно обратитесь за медицинской помощью!",
        'zh': "紧急情况！请立即拨打 108/911！马上寻求医疗帮助！",
        'ja': "緊急事態！すぐに108/911へ電話してください！直ちに医療援助を受けてください！",
    }

    def __init__(self):
        self.groq_api_key = Config.GROQ_API_KEY
        self.api_key = Config.OPENROUTER_API_KEY
        self.use_ai = bool(self.groq_api_key or self.api_key)
        self.training_data = []
        self._load_training_data()
        self.conversation_history = []
        self.emergency_keywords = [
            'chest pain', 'difficulty breathing', 'cannot breathe', "can't breathe",
            'stroke', 'heavy bleeding', 'uncontrolled bleeding', 'seizure', 'unconscious',
            'passed out', 'not breathing', 'heart attack', 'severe allergic', 'anaphylaxis',
            'suicide', 'kill myself', 'overdose', 'poisoning', 'choking',
            'सीने में दर्द', 'सांस लेने में तकलीफ', 'dolor en el pecho', 'douleur a la poitrine'
        ]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def get_response(self, user_message, language=None):
        """Get an AI response. `language` is an optional hint like 'Hindi'."""
        user_message = (user_message or '').strip()
        if not user_message:
            return "How can I help you today? "

        # Keep conversation context (last 20 messages)
        self.conversation_history.append({"role": "user", "content": user_message})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # 1) Emergency triage first (works across languages)
        emergency = self._get_emergency_response(user_message)
        if emergency:
            self.conversation_history.append({"role": "assistant", "content": emergency})
            return emergency

        # 2) Groq AI - general medical assistant, multilingual
        if self.groq_api_key:
            response = self._get_groq_response(user_message, language)
            if response:
                self.conversation_history.append({"role": "assistant", "content": response})
                return response

        # 3) OpenRouter fallback
        if self.api_key:
            response = self._get_openrouter_response(user_message)
            if response:
                self.conversation_history.append({"role": "assistant", "content": response})
                return response

        # 4) Offline canned responses
        response = self._get_fallback_response(user_message)
        self.conversation_history.append({"role": "assistant", "content": response})
        return response
    # ------------------------------------------------------------------
    # Language detection + emergency triage
    # ------------------------------------------------------------------
    def _detect_language(self, text):
        """Best-effort language detection for fallback/emergency messages."""
        t = text.lower()
        markers = {
            'hi': ['namaste', 'kaise', 'kya haal', 'kya', 'hum', 'main'],
            'ta': ['vanakkam', 'epdi', 'irukka', 'enga', 'illa', 'illai'],
            'te': ['namaskaram', 'ela unnav', 'entra', 'kavali'],
            'bn': ['nomoskar', 'kemon', 'dhonnobad', 'ami'],
            'mr': ['namaskar', 'kshama', 'majhya', 'kasa'],
            'gu': ['kem cho', 'aabhar', 'tame'],
            'ur': ['salam', 'shukriya', 'kaise ho', 'kya haal'],
            'es': ['hola', 'como estas', 'gracias', 'ayuda', 'que tal'],
            'fr': ['bonjour', 'merci', 'comment', 's il vous plait'],
            'de': ['hallo', 'danke', 'wie geht', 'bitte'],
            'pt': ['ola', 'obrigado', 'como vai', 'ajuda'],
            'it': ['ciao', 'grazie', 'come stai'],
            'ru': ['привет', 'спасибо', 'помогите'],
            'ar': ['مرحبا', 'شكرا', 'كيف حالك'],
            'zh': ['你好', '谢谢', '帮助'],
            'ja': ['こんにちは', 'ありがとう'],
            'ko': ['안녕하세요', '감사합니다', '도와주세요'],
        }
        for lang, words in markers.items():
            if any(w in t for w in words):
                return lang
        # Script-based fallback for non-Latin scripts
        if re.search('[\u0900-\u097F]', text):
            return 'hi'
        if re.search('[\u0B80-\u0BFF]', text):
            return 'ta'
        if re.search('[\u0C00-\u0C7F]', text):
            return 'te'
        if re.search('[\u0980-\u09FF]', text):
            return 'bn'
        if re.search('[\u0600-\u06FF]', text):
            return 'ar'
        if re.search('[\u4E00-\u9FFF]', text):
            return 'zh'
        if re.search('[\u3040-\u30FF]', text):
            return 'ja'
        if re.search('[\u0400-\u04FF]', text):
            return 'ru'
        return 'en'

    def _get_emergency_response(self, message):
        msg_lower = message.lower()
        if any(k in msg_lower for k in self.emergency_keywords):
            lang = self._detect_language(message)
            return self.EMERGENCY_MSGS.get(lang, self.EMERGENCY_MSGS['en'])
        return None

    # ------------------------------------------------------------------
    # System prompt - general medical AI, multilingual, hospital-aware
    # ------------------------------------------------------------------
    def _build_system_prompt(self, language=None):
        lang_hint = ""
        if language:
            lang_hint = (
                f"\nThe user has selected the language: '{language}'. "
                "ALWAYS reply in that language."
            )

        prompt = f"""You are MediCare AI, a warm, knowledgeable medical assistant for MediCare AI Hospital.

ROLE:
- Answer ALL medical and health-related questions in a complete, structured and easy-to-understand way.
- Cover: symptoms, diseases, first aid, self-care, lab tests, nutrition, fitness, mental health,
  maternal and child care, geriatric care, medicines (educational information only), vaccines,
  and hospital services.
- Act like a general-purpose AI for the medical field - the user may ask anything health related.{lang_hint}

LANGUAGE RULES (VERY IMPORTANT):
- Detect the language the user writes in and ALWAYS answer in that SAME language.
- You support ALL languages: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Urdu, Punjabi,
  Malayalam, Kannada, Spanish, French, German, Arabic, Portuguese, Russian, Chinese, Japanese, Korean, and more.
- Match the user's tone naturally. If the user switches language, switch with them.
- NEVER reply in English when the user wrote in another language.

STYLE (VERY IMPORTANT - ANSWER SHORTLY, SIMPLY AND PERFECTLY):
- Keep every answer SHORT, SIMPLE and to the point - give the person exactly what they need, nothing more.
- Answer confidently and directly without hesitation. Never use phrases like "I think" or "maybe" for standard facts.
- Start with the key answer in **bold**, then add at most 3-5 short bullet points only if they add real value.
- Use **bold text** for the main answer and the most important words so the user can scan instantly.
- Never repeat the question back at length, and never write long introductions or conclusions.
- Explain medical terms in plain language.
- Be warm, empathetic and professional.

SAFETY (MUST ALWAYS HOLD):
- Never prescribe medications or give a definitive diagnosis - recommend consulting a qualified doctor.
- For EMERGENCY symptoms (chest pain, trouble breathing, stroke signs, heavy bleeding, unconsciousness,
  severe allergic reaction, suicidal thoughts): tell the user to call 108/911 immediately, BEFORE any other advice.
- Never tell users to ignore symptoms or delay care.
- Remind users occasionally that you are an AI assistant, not a replacement for a doctor.

HOSPITAL INFO (MediCare AI Hospital):
- Hours: Mon-Fri 8AM-8PM, Sat 9AM-6PM, Sunday emergency only.
- Emergency / ambulance: 108. Hospital phone: +91-1800-123-4567.
- Location: 123 Healthcare Avenue, Medical District, New Delhi.
- Services: AI Diagnostics, Cardiology, Neurology, Orthopedics, Pediatrics, Ophthalmology.
- Appointments can be booked on the website or by phone."""

        # Inject hospital-specific trained knowledge when relevant
        if self.training_data:
            prompt += "\n\nTRAINED KNOWLEDGE (use it when it helps answer the user):\n"
            for item in self.training_data[:12]:
                keywords = item.get('keywords', '')
                answer = item.get('answer', '')
                if keywords and answer:
                    prompt += f"- {keywords}: {answer[:300]}\n"
        return prompt

    # ------------------------------------------------------------------
    # Groq API calls (chat + speech-to-text)
    # ------------------------------------------------------------------
    def _get_groq_response(self, user_message, language=None):
        """Get a response from Groq, trying current models in order."""
        try:
            messages = [{"role": "system", "content": self._build_system_prompt(language)}]
            for msg in self.conversation_history[-12:]:
                messages.append(msg)

            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            }

            models = [self.PRIMARY_MODEL] + self.FALLBACK_MODELS
            for model in models:
                data = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1200,
                    "top_p": 0.95,
                    "stream": False,
                }
                try:
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        reply = result["choices"][0]["message"]["content"]
                        return reply.strip()[:4000]
                    print(f"[WARN] Groq model '{model}' failed: HTTP {response.status_code}")
                except Exception as e:
                    print(f"[WARN] Groq model '{model}' error: {e}")

        except Exception as e:
            print(f"[WARN] Groq API error: {e}")
        return None

    def transcribe_audio(self, audio_bytes, mime_type="audio/webm"):
        """Server-side speech-to-text using Groq Whisper. Returns transcript or None."""
        if not self.groq_api_key or not audio_bytes:
            return None
        try:
            ext = "webm"
            if "wav" in mime_type:
                ext = "wav"
            elif "mp3" in mime_type:
                ext = "mp3"
            elif "ogg" in mime_type:
                ext = "ogg"
            elif "m4a" in mime_type or "mp4" in mime_type:
                ext = "m4a"
            elif "aac" in mime_type:
                ext = "aac"
            elif "amr" in mime_type:
                ext = "amr"
            elif "flac" in mime_type:
                ext = "flac"
            filename = f"voice_{int(time.time() * 1000)}.{ext}"

            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.groq_api_key}"},
                files={"file": (filename, audio_bytes, mime_type)},
                data={"model": self.STT_MODEL},
                timeout=30,
            )
            if response.status_code == 200:
                return response.json().get("text", "").strip()
            print(f"[WARN] STT failed: HTTP {response.status_code} {response.text[:200]}")
        except Exception as e:
            print(f"[WARN] STT error: {e}")
        return None

    def _get_openrouter_response(self, user_message):
        """Fallback: response via OpenRouter API."""
        try:
            messages = [{"role": "system", "content": self._build_system_prompt()}]
            for msg in self.conversation_history[-10:]:
                messages.append(msg)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "model": "mistralai/mistral-7b-instruct",
                "messages": messages,
                "max_tokens": 800,
            }
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=20,
            )
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"][:4000]
        except Exception as e:
            print(f"OpenRouter error: {e}")
        return None
    # ------------------------------------------------------------------
    # Offline fallback responses (multilingual basics)
    # ------------------------------------------------------------------
    def _get_fallback_response(self, user_message):
        msg_lower = user_message.lower().strip()
        lang = self._detect_language(user_message)

        # Greetings
        if any(g in msg_lower for g in ['hi', 'hello', 'hey', 'namaste', 'vanakkam', 'hola', 'bonjour', 'hallo', '你好', 'مرحبا', 'salam']):
            return {
                'en': "Hello! I'm MediCare AI. Ask me anything about your health or our hospital services.",
                'hi': "नमस्ते! मैं MediCare AI हूँ। अपने स्वास्थ्य या हमारी अस्पताल सेवाओं के बारे में कुछ भी पूछें।",
                'ta': "வணக்கம்! நான் MediCare AI. உங்கள் உடல்நலம் அல்லது எங்கள் மருத்துவமனை சேவைகள் பற்றி எதுவும் கேளுங்கள்.",
                'te': "నమస్కారం! నేను MediCare AI ని. మీ ఆరోగ్యం గురించి లేదా మా ఆసుపత్రి సేవల గురించి ఏదైనా అడగండి.",
                'es': "Hola! Soy MediCare AI. Preguntame lo que quieras sobre tu salud o nuestros servicios del hospital.",
                'fr': "Bonjour ! Je suis MediCare AI. Posez-moi des questions sur votre sante ou nos services.",
                'de': "Hallo! Ich bin MediCare AI. Fragen Sie mich alles zu Ihrer Gesundheit oder unseren Diensten.",
                'zh': "你好！我是 MediCare AI。请问我任何关于健康或医院服务的问题。",
                'ar': "مرحبا! أنا MediCare AI. اسألني أي شيء عن صحتك أو خدمات المستشفى.",
            }.get(lang, 'en')

        # Thanks
        if 'thank' in msg_lower or any(t in msg_lower for t in ['dhanyavad', 'nandri', 'shukriya', 'gracias', 'merci', 'danke', 'شكرا', 'aabhar']):
            return {
                'en': "You're welcome! Anything else I can help with?",
                'hi': "आपका स्वागत है! और कुछ मदद चाहिए?",
                'ta': "வரவேற்கிறேன்! வேறு ஏதேனும் உதவி வேண்டுமா?",
                'te': "మీకు స్వాగతం! ఇంకేమైనా సహాయం కావాలా?",
                'es': "De nada! Necesitas algo mas?",
            }.get(lang, 'en')

        if 'bye' in msg_lower:
            return "Take care and stay healthy!"

        # Trained data match
        trained = self._get_trained_response(msg_lower)
        if trained:
            return trained[:400]

        # Symptom shortcuts
        symptom_responses = {
            'fever': "Rest and drink plenty of fluids/ORS. Monitor temperature every 4 hours. If fever is above 103F or lasts more than 3 days, see a doctor.",
            'headache': "Rest in a dark, quiet room, stay hydrated and avoid screens. See a doctor if the headache is severe or recurring.",
            'cough': "Drink warm fluids with honey, and try steam inhalation. See a doctor if the cough persists beyond 2 weeks or you have trouble breathing.",
            'stomach': "Eat light foods (rice, bananas), avoid spicy/oily food and stay hydrated. Seek emergency care for severe pain or blood.",
            'throat': "Gargle warm salt water and drink honey-lemon tea. See a doctor if pain prevents swallowing.",
            'cold': "Rest, drink warm fluids and use saline spray. Most colds resolve in 7-10 days.",
            'allergy': "Avoid known triggers, use a saline rinse and wear a mask outdoors. Seek emergency care if you have trouble breathing.",
            'diabetes': "Monitor blood sugar, eat a balanced diet, exercise daily and take prescribed medicines on time.",
            'blood pressure': "Reduce salt intake, exercise regularly, manage stress and take your medicines consistently.",
        }
        for key, response in symptom_responses.items():
            if key in msg_lower:
                return response

        if 'appointment' in msg_lower:
            return "You can book an appointment online on our website or by calling +91-1800-123-4567."
        if 'hour' in msg_lower or 'timing' in msg_lower:
            return "Mon-Fri 8AM-8PM, Sat 9AM-6PM. Sunday - emergency only. For emergencies call 108 or +91-1800-123-4567."
        if 'doctor' in msg_lower:
            return "We have specialists in Cardiology, Neurology, Orthopedics, Pediatrics, Ophthalmology and more. Visit our website for details."
        if 'location' in msg_lower or 'address' in msg_lower:
            return "MediCare AI Hospital, 123 Healthcare Avenue, Medical District, New Delhi. Call +91-1800-123-4567 for directions."
        if 'emergency' in msg_lower:
            return "For emergencies, call 108 or visit our emergency room immediately. We are open 24/7 for emergencies."
        if 'payment' in msg_lower or 'insurance' in msg_lower:
            return "We accept insurance, cash, cards and UPI. Contact +91-1800-123-4567 for insurance-related queries."
        if 'covid' in msg_lower:
            return "Get vaccinated, wear a mask in crowds, wash hands frequently and test if you have symptoms."

        return "I can help with symptoms, diseases, first aid, hospital services, appointments and general health advice. Please ask me anything!"

    def _get_trained_response(self, user_message):
        """Check if any trained data matches"""
        if not self.training_data:
            return None
        best_match = None
        best_score = 0
        for item in self.training_data:
            keywords = [k.strip().lower() for k in item.get('keywords', '').split(',')]
            for keyword in keywords:
                if keyword in user_message:
                    score = len(keyword)
                    if score > best_score:
                        best_score = score
                        best_match = item.get('answer', '')
        return best_match

    def _load_training_data(self):
        """Load trained data from database"""
        try:
            self.training_data = get_all_training_data()
            print(f"[OK] Loaded {len(self.training_data)} training items")
        except Exception as e:
            print(f"Could not load training data: {e}")
            self.training_data = []

    def reload_training_data(self):
        """Reload training data"""
        self._load_training_data()

    def get_selfcare_suggestions(self, symptoms):
        """Generate AI-powered self-care suggestions"""
        if not symptoms or not symptoms.strip():
            return self._get_default_suggestions()

        if self.groq_api_key:
            ai_suggestions = self._get_ai_selfcare_suggestions(symptoms)
            if ai_suggestions:
                return ai_suggestions

        return self._get_keyword_suggestions(symptoms.lower())

    def _get_ai_selfcare_suggestions(self, symptoms):
        """Get short self-care suggestions from Groq API"""
        try:
            system_prompt = """Generate 5 short self-care tips as a JSON array. Each tip must be 1 sentence only.
Output format: ["tip 1", "tip 2", "tip 3", "tip 4", "tip 5"]
Never prescribe medication. Focus on comfort until doctor visit."""

            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            }
            models = [self.PRIMARY_MODEL] + self.FALLBACK_MODELS
            for model in models:
                data = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Symptoms: {symptoms}. Give 5 short self-care tips."},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "top_p": 0.9,
                    "stream": False,
                }
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=20,
                )
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    try:
                        suggestions = json.loads(content)
                        if isinstance(suggestions, list) and len(suggestions) >= 3:
                            return suggestions[:5]
                    except Exception:
                        pass
            return None

        except Exception as e:
            print(f"[WARN] Error getting AI suggestions: {e}")
        return None

    def _get_keyword_suggestions(self, symptoms):
        """Generate short suggestions based on keywords"""
        suggestions_map = {
            'fever': [
                "Rest and drink water/ORS frequently.",
                "Monitor temperature every 4 hours.",
                "Use a damp cloth on forehead for comfort.",
                "Avoid cold baths - use lukewarm sponging.",
                "If fever >103F, visit emergency immediately."
            ],
            'headache': [
                "Rest in a dark, quiet room.",
                "Apply cold compress to forehead.",
                "Stay hydrated - dehydration worsens headaches.",
                "Avoid screens and bright lights.",
                "Seek emergency if severe or with vision changes."
            ],
            'cough': [
                "Drink warm fluids with honey to soothe throat.",
                "Use steam inhalation to ease congestion.",
                "Avoid cold foods and drinks.",
                "Sleep with head elevated on extra pillows.",
                "Visit ER if you have difficulty breathing."
            ],
            'cold': [
                "Drink warm fluids like soup and herbal tea.",
                "Rest to help your immune system fight.",
                "Use saline spray for nasal congestion.",
                "Gargle warm salt water for sore throat.",
                "Avoid close contact to prevent spreading."
            ],
            'stomach': [
                "Eat light foods like rice and bananas.",
                "Avoid spicy, oily, and dairy foods.",
                "Sip water or ORS slowly throughout day.",
                "Apply warm water bottle for relief.",
                "Seek emergency if severe pain or blood."
            ],
            'chest': [
                "Call 108 immediately for chest pain!",
                "Stop all activity and rest sitting up.",
                "Don't drive yourself - get emergency help.",
                "Keep emergency contacts handy.",
                "Do NOT wait - this needs urgent care!"
            ],
            'breathing': [
                "Call 108 immediately if trouble breathing!",
                "Sit upright to help open airways.",
                "Stay calm - anxiety makes it worse.",
                "Loosen tight clothing around neck.",
                "This needs immediate emergency attention!"
            ]
        }

        for emergency_key in ['chest', 'breathing']:
            if emergency_key in symptoms:
                return suggestions_map[emergency_key]

        for key, suggestions in suggestions_map.items():
            if key in symptoms:
                return suggestions

        return self._get_default_suggestions()

    def _get_default_suggestions(self):
        """Get default self-care suggestions"""
        return [
            "Drink plenty of water to stay hydrated.",
            "Get adequate rest until your appointment.",
            "Note any new symptoms to tell your doctor.",
            "Bring relevant medical reports to your visit.",
            "Call 108 for any emergency."
        ]
