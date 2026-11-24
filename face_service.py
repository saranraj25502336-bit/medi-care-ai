# ============================================
# FACE SERVICE MODULE
# High-level face recognition service that
# orchestrates detection, embedding, and
# patient face registration.
# ============================================

import logging
import time
from typing import Optional

import numpy as np

from config import Config
from embedding_service import get_embedding_service
from face_utils import (
    assess_image_quality,
    decode_base64_image,
    ensure_rgb,
    resize_image
)
from patient_face_repository import PatientFaceRepository

logger = logging.getLogger(__name__)


class FaceService:
    """
    High-level face recognition service.

    Responsibilities:
    1. Generate face embeddings from images/base64.
    2. Register patient faces (with duplicate detection).
    3. Provide face detection status for error handling.
    4. Validate image quality before processing.
    """

    def __init__(self):
        """Initialize the face service."""
        self.embedding_service = get_embedding_service()
        self.repository = PatientFaceRepository()

    # =======================================================================
    # Embedding generation
    # =======================================================================

    def extract_embedding_from_base64(self, base64_string: str) -> dict:
        """
        Extract a face embedding from a base64 image.

        Args:
            base64_string: Base64 data URL or raw base64 string.

        Returns:
            dict with keys:
                - success: bool
                - embedding: 512-dim numpy array (if success)
                - message: str (error message if not success)
                - face_count: int (number of faces detected)
                - quality: dict (image quality assessment)
        """
        # Decode image
        image = decode_base64_image(base64_string)
        if image is None:
            return {
                'success': False,
                'embedding': None,
                'message': 'Invalid or corrupted image data',
                'face_count': 0,
                'quality': None
            }

        return self.extract_embedding_from_image(image)

    def extract_embedding_from_image(self, image: np.ndarray) -> dict:
        """
        Extract a face embedding from an image array.

        Args:
            image: RGB numpy array.

        Returns:
            dict with keys:
                - success: bool
                - embedding: 512-dim numpy array (if success)
                - message: str (error message if not success)
                - face_count: int (number of faces detected)
                - quality: dict (image quality assessment)
        """
        # Ensure RGB
        rgb = ensure_rgb(image)
        if rgb is None:
            return {
                'success': False,
                'embedding': None,
                'message': 'Invalid image format',
                'face_count': 0,
                'quality': None
            }

        # Check if InsightFace is available
        if not self.embedding_service.is_available:
            return {
                'success': False,
                'embedding': None,
                'message': 'Face recognition service is not available',
                'face_count': 0,
                'quality': None
            }

        # Detect faces (InsightFace handles poor quality internally)
        faces = self.embedding_service.detect_faces(rgb)
        face_count = len(faces)

        if face_count == 0:
            return {
                'success': False,
                'embedding': None,
                'message': 'No face detected in the image',
                'face_count': 0,
                'quality': assess_image_quality(rgb)
            }

        if face_count > 1:
            logger.info('Multiple faces detected (%d), using highest confidence',
                        face_count)

        # Get embedding from best face
        best_face = max(faces, key=lambda f: f['confidence'])
        embedding = best_face['embedding']

        if embedding is None:
            return {
                'success': False,
                'embedding': None,
                'message': 'Failed to generate face embedding',
                'face_count': face_count,
                'quality': assess_image_quality(rgb)
            }

        return {
            'success': True,
            'embedding': embedding,
            'message': 'Face embedding generated successfully',
            'face_count': face_count,
            'quality': assess_image_quality(rgb)
        }

    # =======================================================================
    # Patient face registration
    # =======================================================================

    def register_patient_face(
        self,
        patient_id: int,
        base64_string: str,
        face_image: Optional[str] = None,
        check_duplicate: bool = True
    ) -> dict:
        """
        Register a patient's face by generating and storing their embedding.

        Args:
            patient_id: Patient database ID.
            base64_string: Base64 image containing the patient's face.
            face_image: Optional face image filename.
            check_duplicate: Whether to check for duplicate face registration.

        Returns:
            dict with keys:
                - success: bool
                - message: str
                - embedding: 512-dim numpy array (if success)
                - duplicate_patient: dict (if duplicate found)
        """
        # Extract embedding
        result = self.extract_embedding_from_base64(base64_string)

        if not result['success']:
            return {
                'success': False,
                'message': result['message'],
                'embedding': None,
                'duplicate_patient': None
            }

        embedding = result['embedding']

        # Check for duplicate face registration
        if check_duplicate:
            duplicate = self.repository.find_duplicate_embedding(
                embedding,
                threshold=Config.FACE_RECOGNITION_TOLERANCE,
                exclude_patient_id=patient_id
            )

            if duplicate:
                logger.warning('Duplicate face detected: patient %d matches patient %d',
                               patient_id, duplicate.patient_id)
                return {
                    'success': False,
                    'message': f'This face is already registered to patient {duplicate.name} '
                               f'(ID: {duplicate.patient_id})',
                    'embedding': None,
                    'duplicate_patient': {
                        'patient_id': duplicate.patient_id,
                        'name': duplicate.name
                    }
                }

        # Save embedding to database
        saved = self.repository.save_face_embedding(patient_id, embedding, face_image)

        if not saved:
            return {
                'success': False,
                'message': 'Failed to save face embedding to database',
                'embedding': None,
                'duplicate_patient': None
            }

        return {
            'success': True,
            'message': 'Face registered successfully',
            'embedding': embedding,
            'duplicate_patient': None
        }

    # =======================================================================
    # Face detection status
    # =======================================================================

    def check_face_in_image(self, base64_string: str) -> dict:
        """
        Check if a face is present in an image.

        Args:
            base64_string: Base64 image.

        Returns:
            dict with keys:
                - success: bool (face detected)
                - face_count: int
                - message: str
        """
        image = decode_base64_image(base64_string)
        if image is None:
            return {
                'success': False,
                'face_count': 0,
                'message': 'Invalid image data'
            }

        rgb = ensure_rgb(image)
        if rgb is None:
            return {
                'success': False,
                'face_count': 0,
                'message': 'Invalid image format'
            }

        if not self.embedding_service.is_available:
            return {
                'success': False,
                'face_count': 0,
                'message': 'Face recognition service not available'
            }

        faces = self.embedding_service.detect_faces(rgb)
        face_count = len(faces)

        if face_count == 0:
            return {
                'success': False,
                'face_count': 0,
                'message': 'No face detected'
            }

        return {
            'success': True,
            'face_count': face_count,
            'message': f'{face_count} face(s) detected'
        }

    # =======================================================================
    # Service status
    # =======================================================================

    def is_available(self) -> bool:
        """Check if the face recognition service is operational."""
        return self.embedding_service.is_available

    def get_status(self) -> dict:
        """
        Get the status of the face recognition service.

        Returns:
            dict with service status information.
        """
        return {
            'available': self.is_available(),
            'embedding_dim': self.embedding_service.get_embedding_dim(),
            'registered_faces': self.repository.count_registered_faces()
        }