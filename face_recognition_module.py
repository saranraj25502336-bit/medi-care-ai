# ============================================
# FACE RECOGNITION MODULE (COMPATIBILITY FACADE)
# ============================================
# This module is a backward-compatibility facade
# that preserves the existing FaceRecognitionSystem
# interface while delegating all AI operations to
# the new InsightFace-based pipeline.
#
# The actual AI work is performed by:
#   - embedding_service.py  (InsightFace detection + ArcFace embeddings)
#   - recognition_service.py (Cosine Similarity matching)
#   - face_service.py        (High-level orchestration)
#   - patient_face_repository.py (Database access)
#   - similarity.py          (Cosine Similarity math)
#   - face_utils.py          (Image utilities)
# ============================================

# Backward-compatibility: DNN is no longer used.
# Set to True for test_imports.py compatibility.
DNN_AVAILABLE = True

import json
import logging
from typing import Optional

import numpy as np

from config import Config
from embedding_service import get_embedding_service
from face_utils import embedding_from_json, embedding_to_json
from patient_face_repository import PatientFaceRepository
from recognition_service import RecognitionService
from similarity import batch_cosine_similarity, similarity_to_confidence

logger = logging.getLogger(__name__)


class FaceRecognitionSystem:
    """
    Backward-compatible face recognition system.

    This class maintains the original interface used by app.py
    and qa_verify.py, but internally uses the InsightFace-powered
    pipeline for all face detection and recognition tasks.

    Original methods preserved:
    - capture_from_base64()
    - load_known_faces()
    - recognize_face()
    - get_encoding_as_json()
    - encoding_from_json()
    - is_available()
    """

    def __init__(self):
        """Initialize the face recognition system."""
        self.embedding_service = get_embedding_service()
        self.repository = PatientFaceRepository()
        self.recognition_service = RecognitionService()
        self.tolerance = Config.FACE_RECOGNITION_TOLERANCE

        # Maintained for backward compatibility
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.use_dnn = DNN_AVAILABLE  # Compatibility: no longer uses DNN

    # =======================================================================
    # Face encoding (InsightFace ArcFace)
    # =======================================================================

    def capture_from_base64(self, base64_string: str) -> Optional[np.ndarray]:
        """
        Extract a face embedding from a base64 image.

        Uses InsightFace for face detection and ArcFace embedding generation.

        Args:
            base64_string: Base64 data URL or raw base64 string.

        Returns:
            512-dim numpy array (ArcFace embedding) or None if no face found.
        """
        try:
            embedding = self.embedding_service.get_embedding_from_base64(base64_string)
            if embedding is not None:
                logger.info('Face embedding computed (%d dims)', len(embedding))
                return embedding
            logger.info('No face found in image')
            return None

        except Exception as e:
            logger.warning('Base64 embedding error: %s', e)
            return None

    # =======================================================================
    # Known faces loading
    # =======================================================================

    def load_known_faces(self, patients_data: list) -> None:
        """
        Load known face embeddings from database records.

        Args:
            patients_data: List of dicts with patient_id, name, face_encoding.
        """
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []

        for patient in patients_data:
            if patient.get('face_encoding'):
                try:
                    encoding = embedding_from_json(patient['face_encoding'])
                    if encoding is not None:
                        self.known_face_encodings.append(encoding)
                        self.known_face_ids.append(patient['patient_id'])
                        self.known_face_names.append(patient['name'])
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning('Invalid encoding for patient %s: %s',
                                   patient.get('patient_id'), e)

        logger.info('Loaded %d known face embeddings', len(self.known_face_encodings))

    # =======================================================================
    # Face recognition (Cosine Similarity)
    # =======================================================================

    def recognize_face(self, face_encoding: np.ndarray) -> Optional[dict]:
        """
        Match a face embedding against known faces using Cosine Similarity.

        Args:
            face_encoding: 512-dim ArcFace embedding.

        Returns:
            dict with patient_id, name, confidence or None if no match.
        """
        if not self.known_face_encodings or face_encoding is None:
            return None

        # Use batch cosine similarity for efficiency
        scores = batch_cosine_similarity(face_encoding, self.known_face_encodings)

        if scores.size == 0:
            return None

        best_index = int(np.argmax(scores))
        best_sim = float(scores[best_index])

        # Threshold check
        if best_sim >= self.tolerance:
            confidence = similarity_to_confidence(best_sim)
            return {
                'patient_id': self.known_face_ids[best_index],
                'name': self.known_face_names[best_index],
                'confidence': float(max(0.0, min(1.0, confidence)))
            }

        logger.info('No match (best similarity: %.3f)', best_sim)
        return None

    # =======================================================================
    # Serialization helpers
    # =======================================================================

    def get_encoding_as_json(self, face_encoding: np.ndarray) -> Optional[str]:
        """
        Convert a face embedding to JSON string.

        Args:
            face_encoding: 512-dim numpy array.

        Returns:
            JSON string or None if invalid.
        """
        return embedding_to_json(face_encoding)

    def encoding_from_json(self, json_string: str) -> Optional[np.ndarray]:
        """
        Convert a JSON string back to a numpy array.

        Args:
            json_string: JSON string containing embedding.

        Returns:
            numpy float32 array or None if invalid.
        """
        return embedding_from_json(json_string)

    # =======================================================================
    # Status
    # =======================================================================

    def is_available(self) -> bool:
        """
        Check if the face recognition system is operational.

        Returns:
            True if InsightFace is available.
        """
        return self.embedding_service.is_available