# ============================================
# EMBEDDING SERVICE MODULE
# Wraps InsightFace FaceAnalysis for face
# detection, alignment, and embedding generation.
# Uses ArcFace (w600k_r50) for 512-dim embeddings.
# ============================================

import logging
import os
import threading
from typing import List, Optional

import numpy as np

from config import Config
from face_utils import (
    ensure_rgb, resize_image, validate_face_crop, assess_image_quality,
    preprocess_for_recognition
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 512
DET_SIZE = Config.FACE_DETECTION_SIZE
MIN_DETECTION_CONFIDENCE = Config.FACE_MIN_DETECTION_CONFIDENCE
MAX_FACES_PER_IMAGE = 5

# Set InsightFace home to project directory for portability
os.environ['INSIGHTFACE_HOME'] = Config.INSIGHTFACE_HOME


class EmbeddingService:
    """
    Service for generating face embeddings using InsightFace.

    This is a singleton-style service that lazily initializes
    the InsightFace model on first use to avoid startup delays.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one model instance is loaded."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
                cls._instance._app = None
            return cls._instance

    # =======================================================================
    # Initialization
    # =======================================================================

    def _initialize(self) -> bool:
        """
        Initialize the InsightFace FaceAnalysis model.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        if self._initialized:
            return self._app is not None

        try:
            from insightface.app import FaceAnalysis

            # Determine providers (CPU for portability, GPU if available)
            providers = list(Config.FACE_PROVIDERS)

            # Try to use CUDA if available
            try:
                import onnxruntime as ort
                available_providers = ort.get_available_providers()
                if 'CUDAExecutionProvider' in available_providers and 'CUDAExecutionProvider' not in providers:
                    providers.insert(0, 'CUDAExecutionProvider')
                    logger.info('Using CUDA for InsightFace')
            except ImportError:
                pass

            # Initialize FaceAnalysis with configurable model pack
            self._app = FaceAnalysis(
                name=Config.FACE_RECOGNITION_MODEL,
                providers=providers,
                allowed_modules=['detection', 'recognition']
            )
            self._app.prepare(ctx_id=0, det_size=DET_SIZE)

            self._initialized = True
            logger.info('InsightFace initialized successfully (providers=%s)', providers)
            return True

        except Exception as e:
            logger.error('InsightFace initialization failed: %s', e)
            self._initialized = True  # Mark as attempted to avoid retry loops
            self._app = None
            return False

    @property
    def is_available(self) -> bool:
        """Check if the embedding service is available."""
        if not self._initialized:
            self._initialize()
        return self._app is not None

    # =======================================================================
    # Face detection
    # =======================================================================

    def detect_faces(self, image: np.ndarray) -> List[dict]:
        """
        Detect faces in an image using InsightFace.

        Args:
            image: RGB numpy array.

        Returns:
            List of face dicts with keys:
                - bbox: [x1, y1, x2, y2]
                - confidence: detection confidence
                - embedding: 512-dim numpy array (if recognition enabled)
                - face_crop: cropped face image (RGB)
        """
        if not self.is_available:
            logger.warning('InsightFace not available')
            return []

        if image is None:
            return []

        try:
            # Ensure RGB format
            rgb = ensure_rgb(image)
            if rgb is None:
                return []

            # Resize if too large for performance - keep larger for webcam detection
            rgb = resize_image(rgb, max_dimension=1280)

            # Skip CLAHE for real-time speed (enable for registration only)
            if os.environ.get('FACE_SKIP_PREPROCESS', '1') == '1':
                pass  # Skip preprocessing for speed
            else:
                rgb = preprocess_for_recognition(rgb)

            # Run InsightFace detection + recognition
            faces = self._app.get(rgb)
            logger.info('InsightFace detected %d raw faces', len(faces))

            results = []
            for face in faces:
                if face.det_score < MIN_DETECTION_CONFIDENCE:
                    logger.debug('Face rejected: det_score=%.3f < threshold=%.3f',
                                 face.det_score, MIN_DETECTION_CONFIDENCE)
                    continue
                logger.info('Face accepted: det_score=%.3f', face.det_score)

                bbox = face.bbox.astype(int).tolist()
                x1, y1, x2, y2 = bbox

                # Validate bbox
                if x2 <= x1 or y2 <= y1:
                    continue

                # Crop face
                face_crop = rgb[y1:y2, x1:x2]

                # Check crop dimensions (relaxed - don't reject on quality)
                crop_h, crop_w = face_crop.shape[:2]
                if crop_h < 20 or crop_w < 20:
                    logger.debug('Face crop too small: %dx%d', crop_w, crop_h)
                    continue

                # Log quality warning but don't reject
                quality = assess_image_quality(face_crop)
                if not quality['is_valid']:
                    logger.debug('Face crop quality warning: %s', quality['message'])

                det_score = float(getattr(face, 'det_score', 0.0))
                bbox_for_score = bbox
                face_area = max(0, (bbox_for_score[2] - bbox_for_score[0]) * (bbox_for_score[3] - bbox_for_score[1]))
                result = {
                    'bbox': bbox,
                    'confidence': det_score,
                    'quality_score': det_score * (face_area ** 0.5),
                    'face_crop': face_crop,
                    'embedding': None
                }

                # Extract embedding if available
                if hasattr(face, 'normed_embedding') and face.normed_embedding is not None:
                    result['embedding'] = face.normed_embedding.astype(np.float32)
                elif hasattr(face, 'embedding') and face.embedding is not None:
                    # Normalize the embedding
                    emb = face.embedding.astype(np.float32)
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        result['embedding'] = emb / norm

                results.append(result)

                # Limit number of faces
                if len(results) >= MAX_FACES_PER_IMAGE:
                    break

            return results

        except Exception as e:
            logger.warning('Face detection error: %s', e)
            return []

    # =======================================================================
    # Embedding generation
    # =======================================================================

    def get_embedding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Generate a face embedding from an image.

        Args:
            image: RGB numpy array containing a face.

        Returns:
            512-dim normalized numpy array, or None if no face detected.
        """
        faces = self.detect_faces(image)

        if not faces:
            return None

        # Return the best face by quality_score (confidence x sqrt(area))
        best_face = max(faces, key=lambda f: f.get('quality_score', f['confidence']))

        if best_face['embedding'] is None:
            return None

        return best_face['embedding']

    def get_embedding_from_base64(self, base64_string: str) -> Optional[np.ndarray]:
        """
        Generate a face embedding from a base64-encoded image.

        Args:
            base64_string: Base64 data URL or raw base64 string.

        Returns:
            512-dim normalized numpy array, or None if no face detected.
        """
        from face_utils import decode_base64_image

        image = decode_base64_image(base64_string)
        if image is None:
            return None

        return self.get_embedding(image)

    def get_embeddings_from_image(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Generate embeddings for all faces in an image.

        Args:
            image: RGB numpy array.

        Returns:
            List of 512-dim normalized numpy arrays.
        """
        faces = self.detect_faces(image)
        embeddings = []

        for face in faces:
            if face['embedding'] is not None:
                embeddings.append(face['embedding'])

        return embeddings

    # =======================================================================
    # Face alignment
    # =======================================================================

    def align_face(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Align a face in an image using InsightFace's landmark detection.

        InsightFace automatically aligns faces during detection.
        This method returns the aligned face crop.

        Args:
            image: RGB numpy array containing a face.

        Returns:
            Aligned face crop (RGB), or None if no face detected.
        """
        faces = self.detect_faces(image)

        if not faces:
            return None

        # Return the best face by quality_score (confidence x sqrt(area))
        best_face = max(faces, key=lambda f: f.get('quality_score', f['confidence']))
        return best_face['face_crop']

    # =======================================================================
    # Utility
    # =======================================================================

    def get_embedding_dim(self) -> int:
        """Return the embedding dimension (512 for ArcFace)."""
        return EMBEDDING_DIM

    def validate_embedding(self, embedding: np.ndarray) -> bool:
        """
        Validate that an embedding is well-formed.

        Args:
            embedding: Embedding to validate.

        Returns:
            True if valid, False otherwise.
        """
        if embedding is None:
            return False

        try:
            emb = np.asarray(embedding, dtype=np.float32)
            if emb.ndim != 1:
                return False
            if emb.size != EMBEDDING_DIM:
                logger.warning('Embedding has wrong dimension: %d (expected %d)',
                               emb.size, EMBEDDING_DIM)
                return False
            if not np.all(np.isfinite(emb)):
                logger.warning('Embedding contains non-finite values')
                return False
            return True

        except Exception as e:
            logger.warning('Embedding validation error: %s', e)
            return False


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get the singleton EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service