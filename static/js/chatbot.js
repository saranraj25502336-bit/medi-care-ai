/* ============================================
   MediCare AI Chatbot - shared front-end logic
   Multilingual - Voice input - Voice output (TTS)
   ============================================ */
(function () {
    'use strict';

    /* ---------- Language support ---------- */
    // Option text -> ISO 639-1 code
    var LANGUAGES = {
        'English': 'en',
        'हिन्दी (Hindi)': 'hi',
        'தமிழ் (Tamil)': 'ta',
        'తెలుగు (Telugu)': 'te',
        'বাংলা (Bengali)': 'bn',
        'मराठी (Marathi)': 'mr',
        'ગુજરાતી (Gujarati)': 'gu',
        'اردو (Urdu)': 'ur',
        'ਪੰਜਾਬੀ (Punjabi)': 'pa',
        'മലയാളം (Malayalam)': 'ml',
        'ಕನ್ನಡ (Kannada)': 'kn',
        'Español (Spanish)': 'es',
        'Français (French)': 'fr',
        'Deutsch (German)': 'de',
        'العربية (Arabic)': 'ar',
        'Português (Portuguese)': 'pt',
        'Русский (Russian)': 'ru',
        '中文 (Chinese)': 'zh',
        '日本語 (Japanese)': 'ja',
        '한국어 (Korean)': 'ko'
    };

    var RECOG_REGION = {
        en: 'US', es: 'ES', fr: 'FR', de: 'DE', ar: 'SA',
        pt: 'BR', ru: 'RU', zh: 'CN', ja: 'JP', ko: 'KR', ur: 'PK'
    };

    function langCode() {
        var sel = document.getElementById('chatbotLang');
        return (sel && sel.value && LANGUAGES[sel.value]) ? LANGUAGES[sel.value] : '';
    }

    function languageName() {
        var sel = document.getElementById('chatbotLang');
        return sel && sel.value ? sel.value : '';
    }

    function recogLangCode() {
        var lc = langCode();
        if (!lc) return 'en-US';
        return lc + '-' + (RECOG_REGION[lc] || 'IN');
    }

    /* ---------- State ---------- */
    var isListening = false;
    var recognition = null;
    var ttsEnabled = true;
    var ttsVoices = [];
    var mediaRecorder = null;
    var audioChunks = [];

    function notify(type, msg) {
        if (typeof window.showToast === 'function') window.showToast(type, msg);
    }

    /* ---------- Open / close ---------- */
    function toggleChatbot() {
        var panel = document.getElementById('chatbotPanel');
        if (panel) panel.classList.toggle('open');
    }

    /* ---------- Safe rendering (escape HTML + light markdown) ---------- */
    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatMessage(text) {
        var esc = escapeHtml(text).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        var lines = esc.split('\n');
        var html = '', inUl = false, inOl = false, i, m;
        for (i = 0; i < lines.length; i++) {
            var line = lines[i];
            if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
                if (!inUl) { html += '<ul>'; inUl = true; }
                html += '<li>' + m[1] + '</li>';
            } else if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
                if (!inOl) { html += '<ol>'; inOl = true; }
                html += '<li>' + m[1] + '</li>';
            } else {
                if (inUl) { html += '</ul>'; inUl = false; }
                if (inOl) { html += '</ol>'; inOl = false; }
                if (line.trim() === '') { html += '<br>'; } else { html += line; }
            }
        }
        if (inUl) html += '</ul>';
        if (inOl) html += '</ol>';
        return html.replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    function addMessage(text, sender, autoSpeak) {
        var container = document.getElementById('chatbotMessages');
        if (!container) return;
        var wrap = document.createElement('div');
        wrap.className = 'message ' + sender;
        var bubble = document.createElement('div');
        bubble.className = 'message-content';
        bubble.innerHTML = formatMessage(text);
        wrap.appendChild(bubble);
        if (sender === 'bot') {
            var actions = document.createElement('div');
            actions.className = 'message-actions';
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'msg-speak-btn';
            btn.title = 'Play voice';
            btn.innerHTML = '<i class="fas fa-volume-up"></i>';
            btn.addEventListener('click', function () { speakText(text); });
            actions.appendChild(btn);
            wrap.appendChild(actions);
        }
        container.appendChild(wrap);
        container.scrollTop = container.scrollHeight;
        if (sender === 'bot' && autoSpeak && ttsEnabled) speakText(text);
    }

    function showTyping() {
        removeTyping();
        var container = document.getElementById('chatbotMessages');
        if (!container) return;
        var div = document.createElement('div');
        div.className = 'message bot';
        div.id = 'typingIndicator';
        div.innerHTML = '<div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function removeTyping() {
        var t = document.getElementById('typingIndicator');
        if (t) t.remove();
    }

    /* ---------- Send text message ---------- */
    function sendMessage() {
        var input = document.getElementById('chatbotInput');
        if (!input) return;
        var msg = input.value.trim();
        if (!msg) return;
        addMessage(msg, 'user', false);
        input.value = '';
        showTyping();
        fetch('/chatbot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, language: languageName() || null })
        })
        .then(function (r) { return r.json(); })
        .then(function (d) {
            removeTyping();
            addMessage(d.response || d.message || "Sorry, I couldn't process that.", 'bot', true);
        })
        .catch(function () {
            removeTyping();
            addMessage("I'm here to help! Try asking about symptoms, diseases, first aid, or hospital services.", 'bot', true);
        });
    }

    function sendSuggestion(text) {
        var input = document.getElementById('chatbotInput');
        if (input) input.value = text;
        sendMessage();
    }
    /* ---------- Voice OUTPUT (text-to-speech) ---------- */
    function loadVoices() {
        if (window.speechSynthesis) ttsVoices = window.speechSynthesis.getVoices();
    }
    if (window.speechSynthesis) {
        loadVoices();
        window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    function detectScriptLang(text) {
        if (/[\u0900-\u097F]/.test(text)) return 'hi';
        if (/[\u0B80-\u0BFF]/.test(text)) return 'ta';
        if (/[\u0C00-\u0C7F]/.test(text)) return 'te';
        if (/[\u0980-\u09FF]/.test(text)) return 'bn';
        if (/[\u0A00-\u0A7F]/.test(text)) return 'pa';
        if (/[\u0D00-\u0D7F]/.test(text)) return 'ml';
        if (/[\u0C80-\u0CFF]/.test(text)) return 'kn';
        if (/[\u0600-\u06FF]/.test(text)) return 'ar';
        if (/[\u4E00-\u9FFF]/.test(text)) return 'zh';
        if (/[\u3040-\u30FF]/.test(text)) return 'ja';
        if (/[\uAC00-\uD7AF]/.test(text)) return 'ko';
        if (/[\u0400-\u04FF]/.test(text)) return 'ru';
        return 'en';
    }

    function pickVoice(text) {
        var target = langCode() || detectScriptLang(text);
        var exact = ttsVoices.filter(function (v) {
            return v.lang && v.lang.toLowerCase().indexOf(target) === 0;
        });
        if (exact.length) return exact[0];
        var partial = ttsVoices.filter(function (v) {
            return v.lang && v.lang.toLowerCase().split('-')[0] === target;
        });
        if (partial.length) return partial[0];
        return null;
    }

    function speakText(text) {
        if (!window.speechSynthesis) return;
        if (!text || !text.trim()) return;
        window.speechSynthesis.cancel();
        var clean = String(text).replace(/[#*`>]/g, ' ').replace(/\s+/g, ' ').trim();
        if (!clean) return;
        var utter = new SpeechSynthesisUtterance(clean);
        var voice = pickVoice(clean);
        if (voice) utter.voice = voice;
        utter.lang = (voice && voice.lang) || (langCode() ? recogLangCode() : 'en-US');
        utter.rate = 1.0;
        utter.pitch = 1.0;
        setTimeout(function () { window.speechSynthesis.speak(utter); }, 60);
    }

    function stopSpeaking() {
        if (window.speechSynthesis) window.speechSynthesis.cancel();
    }

    function toggleTTS() {
        ttsEnabled = !ttsEnabled;
        var btn = document.getElementById('ttsToggleBtn');
        if (btn) {
            btn.classList.toggle('active', ttsEnabled);
            btn.title = ttsEnabled ? 'Voice replies ON (click to mute)' : 'Voice replies OFF (click to enable)';
        }
        if (!ttsEnabled) stopSpeaking();
    }

    function onLangChange() {
        if (recognition) {
            try { recognition.lang = recogLangCode(); } catch (e) {}
        }
    }

    /* ---------- Voice INPUT (speech-to-text) ---------- */
    function initSpeechRecognition() {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return; // MediaRecorder + server-side Whisper fallback is used instead
        recognition = new SR();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = recogLangCode();

        recognition.onresult = function (event) {
            var transcript = event.results[0][0].transcript;
            var input = document.getElementById('chatbotInput');
            if (input) {
                input.value = transcript;
                stopListening();
                sendMessage();
            }
        };
        recognition.onerror = function (event) {
            console.error('Speech error:', event.error);
            stopListening();
            if (event.error === 'not-allowed') {
                notify('error', 'Microphone access denied. Please allow microphone permissions.');
            } else if (event.error === 'no-speech') {
                notify('info', 'No speech detected. Please try again.');
            }
        };
        recognition.onend = function () {
            stopListening();
        };
    }

    function toggleMic() {
        if (isListening) { stopListening(); return; }
        startListening();
    }

    function startListening() {
        if (recognition) {
            try {
                recognition.lang = recogLangCode();
                recognition.start();
                isListening = true;
                markMic(true);
                return;
            } catch (e) {
                console.error('Speech start error:', e);
            }
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            startFallbackRecording();
        } else {
            notify('error', 'Voice input is not supported in this browser.');
        }
    }

    function startFallbackRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function (stream) {
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                mediaRecorder.ondataavailable = function (e) {
                    if (e.data && e.data.size > 0) audioChunks.push(e.data);
                };
                mediaRecorder.onstop = function () {
                    var mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
                    var blob = new Blob(audioChunks, { type: mime });
                    stream.getTracks().forEach(function (t) { t.stop(); });
                    var reader = new FileReader();
                    reader.onloadend = function () {
                        var b64 = String(reader.result).split(',')[1] || '';
                        stopListening();
                        if (b64) sendVoiceMessage(b64, mime);
                    };
                    reader.readAsDataURL(blob);
                };
                mediaRecorder.start();
                isListening = true;
                markMic(true);
            })
            .catch(function () {
                notify('error', 'Microphone access denied. Please allow microphone permissions.');
                stopListening();
            });
    }

    function sendVoiceMessage(b64, mime) {
        showTyping();
        fetch('/chatbot/voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio: b64, mime_type: mime, language: languageName() || null })
        })
        .then(function (r) { return r.json(); })
        .then(function (d) {
            removeTyping();
            if (d.transcript) addMessage(d.transcript, 'user', false);
            addMessage(d.response || d.message || "Sorry, I couldn't process that.", 'bot', true);
        })
        .catch(function () {
            removeTyping();
            addMessage("Sorry, I couldn't hear that clearly. Please try again.", 'bot', true);
        });
    }

    function stopListening() {
        isListening = false;
        markMic(false);
        if (recognition) {
            try { recognition.stop(); } catch (e) {}
        }
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            try { mediaRecorder.stop(); } catch (e) {}
        }
    }

    function markMic(listening) {
        var btn = document.getElementById('micBtn');
        if (!btn) return;
        var input = document.getElementById('chatbotInput');
        if (listening) {
            btn.classList.add('listening');
            btn.innerHTML = '<i class="fas fa-microphone-alt"></i>';
            if (input) input.placeholder = 'Listening...';
        } else {
            btn.classList.remove('listening');
            btn.innerHTML = '<i class="fas fa-microphone"></i>';
            if (input) input.placeholder = 'Type your message...';
        }
    }

    /* ---------- Init ---------- */
    function init() {
        initSpeechRecognition();
        var ttsBtn = document.getElementById('ttsToggleBtn');
        if (ttsBtn) ttsBtn.classList.toggle('active', ttsEnabled);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { setTimeout(init, 300); });
    } else {
        setTimeout(init, 300);
    }

    /* ---------- Expose globals used by inline HTML handlers ---------- */
    window.toggleChatbot = toggleChatbot;
    window.sendMessage = sendMessage;
    window.sendSuggestion = sendSuggestion;
    window.toggleMic = toggleMic;
    window.toggleTTS = toggleTTS;
    window.onLangChange = onLangChange;
    window.speakText = speakText;
})();
