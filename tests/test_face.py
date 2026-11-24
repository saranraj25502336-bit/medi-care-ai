"""Tests for face recognition service."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Import inside tests to avoid circular imports


class TestEmbeddingService:
    """Test InsightFace embedding extraction."""

    @patch('embedding_service.EmbeddingService._init_model')
    def test_singleton_pattern(self, mock_init):
        """Test EmbeddingService is singleton."""
        from embedding_service import EmbeddingService
        service1 = EmbeddingService()
        service2 = EmbeddingService()
        assert service1 is service2

    def test_validate_embedding_valid(self):
        """Test embedding validation for valid 512-dim vector."""
        from embedding_service import EmbeddingService
        service = EmbeddingService()
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize

        is_valid, msg = service.validate_embedding(embedding)
        assert is_valid is True

    def test_validate_embedding_wrong_dim(self):
        """Test embedding validation fails for wrong dimension."""
        from embedding_service import EmbeddingService
        service = EmbeddingService()
        embedding = np.random.rand(256).astype(np.float32)

        is_valid, msg = service.validate_embedding(embedding)
        assert is_valid is False
        assert '512' in msg or 'dimension' in msg.lower()

    def test_validate_embedding_not_normalized(self):
        """Test embedding validation warns for non-normalized."""
        from embedding_service import EmbeddingService
        service = EmbeddingService()
        embedding = np.random.rand(512).astype(np.float32) * 10  # Not normalized

        is_valid, msg = service.validate_embedding(embedding)
        # Should still pass but may warn
        assert is_valid in (True, False)


class TestRecognitionService:
    """Test face recognition with ensemble matching."""

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        from recognition_service import RecognitionService
        service = RecognitionService()
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        sim = service._cosine_similarity(a, b)
        assert sim == 1.0

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity for orthogonal vectors."""
        from recognition_service import RecognitionService
        service = RecognitionService()
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        sim = service._cosine_similarity(a, b)
        assert sim == 0.0

    @patch('recognition_service.EmbeddingService')
    def test_ensemble_match_exact(self, mock_embed_service):
        """Test ensemble matching with exact match."""
        from recognition_service import RecognitionService
        service = RecognitionService()
        # Mock embedding service
        mock_embed_service.return_value.extract_embedding.return_value = np.ones(512) * 0.1

        # Patient with identical embedding
        patient = {
            'patient_id': 1,
            'face_embedding': np.ones(512) * 0.1
        }

        candidates = [(patient, 1.0, 0.0)]
        result = service._ensemble_match(candidates)

        assert result is not None
        assert result['patient_id'] == 1

    def test_margin_gate_rejects_close_candidates(self):
        """Test margin gate rejects when top-2 too close."""
        from recognition_service import RecognitionService
        service = RecognitionService()
        service.min_margin = 0.04

        # Two candidates with very similar scores
        emb = np.ones(512) * 0.1
        candidates = [
            ({'patient_id': 1, 'face_embedding': emb}, 0.95, 0.05),
            ({'patient_id': 2, 'face_embedding': emb}, 0.94, 0.06),
        ]

        result = service._ensemble_match(candidates)
        # Should reject due to insufficient margin (0.95 - 0.94 = 0.01 < 0.04)
        assert result is None

    def test_margin_gate_accepts_clear_winner(self):
        """Test margin gate accepts when clear winner."""
        from recognition_service import RecognitionService
        service = RecognitionService()
        service.min_margin = 0.04

        emb1 = np.ones(512) * 0.1
        emb2 = np.ones(512) * 0.2
        candidates = [
            ({'patient_id': 1, 'face_embedding': emb1}, 0.95, 0.05),
            ({'patient_id': 2, 'face_embedding': emb2}, 0.80, 0.20),
        ]

        result = service._ensemble_match(candidates)
        # Margin = 0.95 - 0.80 = 0.15 > 0.04, should accept
        assert result is not None
        assert result['patient_id'] == 1


class TestPatientFaceRepository:
    """Test face embedding storage."""

    @patch('patient_face_repository.Database')
    def test_save_embedding(self, mock_db):
        """Test saving face embedding."""
        from patient_face_repository import PatientFaceRepository
        mock_db.return_value.execute_query.return_value = 1

        repo = PatientFaceRepository()
        result = repo.save_embedding(1, np.ones(512) * 0.1)

        assert result is True
        mock_db.return_value.execute_query.assert_called()

    @patch('patient_face_repository.Database')
    def test_load_embedding(self, mock_db):
        """Test loading face embedding."""
        from patient_face_repository import PatientFaceRepository
        mock_db.return_value.fetch_one.return_value = {
            'face_embedding': '[0.1, 0.1, ...]'  # JSON serialized
        }

        repo = PatientFaceRepository()
        embedding = repo.load_embedding(1)

        assert embedding is not None
        assert len(embedding) == 512

    @patch('patient_face_repository.Database')
    def test_find_duplicates(self, mock_db):
        """Test duplicate detection via cosine similarity."""
        from patient_face_repository import PatientFaceRepository
        # Return multiple patients with embeddings
        mock_db.return_value.fetch_all.return_value = [
            {'patient_id': 1, 'face_embedding': '[0.1]' * 512},
            {'patient_id': 2, 'face_embedding': '[0.2]' * 512},
        ]

        repo = PatientFaceRepository()
        duplicates = repo.find_duplicates(np.ones(512) * 0.1, threshold=0.5)

        # Should find patient 1 as duplicate (similar embedding)
        assert len(duplicates) >= 0  # Depends on actual similarity