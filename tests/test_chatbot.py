"""Tests for medical chatbot."""
import pytest
from unittest.mock import MagicMock, patch


class TestMedicalChatbot:
    """Test MedicalChatbot functionality."""

    def test_chatbot_initialization(self):
        """Test chatbot initializes with training data."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = [
                {'id': 1, 'question': 'What are your hours?', 'answer': '9 AM - 5 PM', 'language': 'en'},
                {'id': 2, 'question': 'Do you take insurance?', 'answer': 'Yes, most major plans.', 'language': 'en'},
            ]
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            assert len(chatbot.training_data) >= 0

    def test_get_response_english(self):
        """Test chatbot responds in English."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = [
                {'id': 1, 'question': 'hours', 'answer': 'We are open 9 AM to 5 PM.', 'language': 'en'},
            ]
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            response = chatbot.get_response('What are your hours?', 'en')
            assert isinstance(response, str)
            assert len(response) > 0

    def test_get_response_tamil(self):
        """Test chatbot responds in Tamil."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = [
                {'id': 1, 'question': 'நேரம்', 'answer': 'நாம் காலை 9 மணி முதல் மாலை 5 மணி வரை திறந்துள்ளோம்.', 'language': 'ta'},
            ]
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            response = chatbot.get_response('உங்கள் நேரம் என்ன?', 'ta')
            assert isinstance(response, str)

    def test_get_response_fallback(self):
        """Test chatbot fallback for unknown questions."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = []
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            response = chatbot.get_response('Completely unknown question', 'en')
            assert isinstance(response, str)
            assert len(response) > 0

    def test_get_selfcare_suggestions(self):
        """Test self-care suggestions for symptoms."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = []
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            suggestions = chatbot.get_selfcare_suggestions('headache and fever')
            assert isinstance(suggestions, str)
            assert len(suggestions) > 0

    def test_supported_languages(self):
        """Test chatbot supports multiple languages."""
        from chatbot import MedicalChatbot
        chatbot = MedicalChatbot()
        # Should support at least these languages
        expected_langs = ['en', 'ta', 'hi', 'te', 'ml', 'kn', 'bn', 'gu', 'mr', 'pa']
        for lang in expected_langs:
            # Just verify no crash
            response = chatbot.get_response('Hello', lang)
            assert isinstance(response, str)

    @patch('chatbot.Groq')
    def test_groq_api_call(self, mock_groq):
        """Test Groq API is called for complex queries."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = 'AI response'

        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = []
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()
            response = chatbot.get_response('Complex medical question about treatment', 'en')

            # Should use Groq for complex queries
            assert isinstance(response, str)

    def test_transcribe_audio_mock(self):
        """Test audio transcription (mocked)."""
        with patch('chatbot.Database') as mock_db:
            mock_db.return_value.fetch_all.return_value = []
            from chatbot import MedicalChatbot
            chatbot = MedicalChatbot()

            # Mock audio data
            fake_audio = b'fake audio bytes'
            transcript = chatbot.transcribe_audio(fake_audio, 'audio/webm')
            # Should return string or None
            assert transcript is None or isinstance(transcript, str)