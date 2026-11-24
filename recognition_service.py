# ============================================
# RECOGNITION SERVICE MODULE
# Patient identification using Cosine Similarity
# matching against stored ArcFace embeddings.
# ============================================

import logging
import time
from typing import Optional

import numpy as np

from config import Config
from face_service import FaceService
from patient_face_repository import PatientFaceRepository
from similarity import (
    batch_cosine_similarity, similarity_to_confidence,
    batch_ensemble_similarity, find_best_match_with_margin
)

logger = logging.getLogger(__name__)


class RecognitionResult:
    """
    Result of a face recognition attempt.

    Attributes:
        success: Whether a patient was identified.
        patient_id: Matched patient's ID (if success).
        patient_name: Matched patient's name (if success).
        confidence: Confidence score (0-1).
        similarity: Raw cosine similarity score.
        recognition_time: Time taken for recognition in seconds.
        message: Human-readable message.
    """

    def __init__(
        self,
        success: bool,
        patient_id: Optional[int] = None,
        patient_name: Optional[str] = None,
        confidence: float = 0.0,
        similarity: float = 0.0,
        recognition_time: float = 0.0,
        message: str = ''
    ):
        self.success = success
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.confidence = confidence
        self.similarity = similarity
        self.recognition_time = recognition_time
        self.message = message

    def to_dict(self) -> dict:
        """Convert result to a JSON-serializable dict."""
        return {
            'success': self.success,
            'patient_id': self.patient_id,
            'name': self.patient_name,
            'confidence': round(self.confidence, 4),
            'similarity': round(self.similarity, 4),
            'recognition_time': round(self.recognition_time, 3),
            'message': self.message
        }

    def __repr__(self) -> str:
        return (f"<RecognitionResult(success={self.success}, "
                f"patient_id={self.patient_id}, confidence={self.confidence:.3f})>")


class RecognitionService:
    """
    Service for identifying patients by face.

    Workflow:
    1. Extract query embedding from image.
    2. Load all stored patient embeddings.
    3. Compute batch cosine similarity.
    4. Apply threshold to determine match.
    5. Return patient details with confidence.
    """

    def __init__(self):
        """Initialize the recognition service."""
        self.face_service = FaceService()
        self.repository = PatientFaceRepository()
        self.threshold = Config.FACE_RECOGNITION_TOLERANCE

    # =======================================================================
    # Recognition
    # =======================================================================

    def recognize_from_base64(self, base64_string: str) -> RecognitionResult:
        """
        Recognize a patient from a base64 image.

        Args:
            base64_string: Base64 data URL or raw base64 string.

        Returns:
            RecognitionResult with patient details if matched.
        """
        start_time = time.time()

        # Step 1: Extract embedding
        extraction = self.face_service.extract_embedding_from_base64(base64_string)

        if not extraction['success']:
            return RecognitionResult(
                success=False,
                message=extraction['message'],
                recognition_time=time.time() - start_time
            )

        embedding = extraction['embedding']

        # Step 2: Recognize
        return self._match_embedding(embedding, start_time)

    def recognize_from_image(self, image: np.ndarray) -> RecognitionResult:
        """
        Recognize a patient from an image array.

        Args:
            image: RGB numpy array.

        Returns:
            RecognitionResult with patient details if matched.
        """
        start_time = time.time()

        # Step 1: Extract embedding
        extraction = self.face_service.extract_embedding_from_image(image)

        if not extraction['success']:
            return RecognitionResult(
                success=False,
                message=extraction['message'],
                recognition_time=time.time() - start_time
            )

        embedding = extraction['embedding']

        # Step 2: Recognize
        return self._match_embedding(embedding, start_time)

    def recognize_embedding(self, embedding: np.ndarray) -> RecognitionResult:
        """
        Recognize a patient from a pre-computed embedding.

        Args:
            embedding: 512-dim ArcFace embedding.

        Returns:
            RecognitionResult with patient details if matched.
        """
        start_time = time.time()
        return self._match_embedding(embedding, start_time)

    # =======================================================================
    # Internal matching
    # =======================================================================

    def _match_embedding(
        self,
        embedding: np.ndarray,
        start_time: float
    ) -> RecognitionResult:
        """
        Match an embedding against stored patient embeddings.

        Uses ensemble similarity (cosine + euclidean) with a margin-based
        confidence gate to reduce false positives.

        Args:
            embedding: Query embedding (512-dim).
            start_time: Time when recognition started.

        Returns:
            RecognitionResult.
        """
        # Load all stored patient faces
        patient_faces = self.repository.load_all_patient_faces()

        if not patient_faces:
            return RecognitionResult(
                success=False,
                message='No registered faces found. Please register first.',
                recognition_time=time.time() - start_time
            )

        embeddings = [pf.embedding for pf in patient_faces]

        # --- Ensemble matching with margin gate ---
        match = find_best_match_with_margin(
            embedding,
            embeddings,
            threshold=self.threshold,
            min_margin=0.04  # Must be clearly better than 2nd best
        )

        if match is not None:
            best_index, best_score, margin = match
            matched_patient = patient_faces[best_index]

            # Map ensemble score to confidence (ensemble scores in [0,1])
            # Remap: threshold=0.5 -> 0%, score=1.0 -> 100%
            confidence = max(0.0, min(1.0, (best_score - self.threshold) / (1.0 - self.threshold)))

            result = RecognitionResult(
                success=True,
                patient_id=matched_patient.patient_id,
                patient_name=matched_patient.name,
                confidence=round(confidence, 4),
                similarity=round(best_score, 4),
                recognition_time=time.time() - start_time,
                message=f'Patient identified: {matched_patient.name}'
            )

            logger.info(
                'Face recognized: patient %d (%s) | ensemble=%.3f | margin=%.3f | time=%.2fs',
                matched_patient.patient_id, matched_patient.name,
                best_score, margin, result.recognition_time
            )
            return result

        # --- Fallback: check cosine alone for informative error ---
        cosine_scores = batch_cosine_similarity(embedding, embeddings)
        best_cosine = float(np.max(cosine_scores)) if cosine_scores.size > 0 else 0.0

        if best_cosine > 0.3:
            msg = (
                'Face not recognized with sufficient confidence. '
                'Please look directly at the camera and try again.'
            )
        else:
            msg = 'Unknown patient. Face not recognized. Please register first.'

        return RecognitionResult(
            success=False,
            message=msg,
            similarity=best_cosine,
            recognition_time=time.time() - start_time
        )


    # =======================================================================
    # Top-K candidates
    # =======================================================================

    def get_top_candidates(
        self,
        base64_string: str,
        k: int = 3
    ) -> list:
        """
        Get the top-K matching patients for a face.

        Args:
            base64_string: Base64 image.
            k: Number of candidates to return.

        Returns:
            List of dicts with patient_id, name, similarity, confidence.
        """
        extraction = self.face_service.extract_embedding_from_base64(base64_string)

        if not extraction['success']:
            return []

        embedding = extraction['embedding']
        patient_faces = self.repository.load_all_patient_faces()

        if not patient_faces:
            return []

        from similarity import find_top_k_matches, batch_ensemble_similarity
        import numpy as np

        embeddings = [pf.embedding for pf in patient_faces]
        # Use ensemble scores for top-k ranking
        ensemble_scores = batch_ensemble_similarity(embedding, embeddings)
        k_actual = min(k, len(embeddings))
        top_indices = np.argsort(ensemble_scores)[::-1][:k_actual]
        matches = [(int(i), float(ensemble_scores[i])) for i in top_indices]

        candidates = []
        for idx, score in matches:
            pf = patient_faces[idx]
            candidates.append({
                'patient_id': pf.patient_id,
                'name': pf.name,
                'similarity': round(float(score), 4),
                'confidence': round(similarity_to_confidence(float(score)), 4)
            })

        return candidates

    # =======================================================================
    # Status
    # =======================================================================

    def get_status(self) -> dict:
        """
        Get the status of the recognition service.

        Returns:
            dict with service status.
        """
        return {
            'available': self.face_service.is_available(),
            'threshold': self.threshold,
            'registered_faces': self.repository.count_registered_faces()
        }

    