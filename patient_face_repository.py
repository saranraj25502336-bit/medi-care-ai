# ============================================
# PATIENT FACE REPOSITORY MODULE
# Data access layer for patient face embeddings.
# Reuses existing patients.face_encoding column.
# ============================================

import json
import logging
from typing import List, Optional

import numpy as np

from database import (
    get_all_face_encodings,
    get_patient_by_id,
    update_face_encoding
)
from face_utils import embedding_from_json, embedding_to_json

logger = logging.getLogger(__name__)


class PatientFace:
    """
    Represents a stored face embedding for a patient.

    Attributes:
        patient_id: Patient's database ID.
        name: Patient's full name.
        embedding: 512-dim numpy array (ArcFace embedding).
    """

    def __init__(self, patient_id: int, name: str, embedding: np.ndarray):
        self.patient_id = patient_id
        self.name = name
        self.embedding = embedding

    def __repr__(self) -> str:
        return f"<PatientFace(patient_id={self.patient_id}, name='{self.name}')>"


class PatientFaceRepository:
    """
    Repository for managing patient face embeddings in the database.

    This repository:
    1. Stores ArcFace embeddings linked to patient IDs.
    2. Loads all embeddings for batch recognition.
    3. Detects duplicate face registrations.
    4. Validates embedding integrity before storage.
    """

    def __init__(self):
        """Initialize the repository."""
        pass

    # =======================================================================
    # Storage
    # =======================================================================

    def save_face_embedding(
        self,
        patient_id: int,
        embedding: np.ndarray,
        face_image: Optional[str] = None
    ) -> bool:
        """
        Save a face embedding for a patient.

        Args:
            patient_id: Patient database ID.
            embedding: 512-dim ArcFace embedding.
            face_image: Optional face image filename.

        Returns:
            True if saved successfully, False otherwise.
        """
        if not patient_id:
            logger.warning('Cannot save embedding: invalid patient_id')
            return False

        # Validate embedding
        if embedding is None:
            logger.warning('Cannot save embedding: embedding is None')
            return False

        try:
            embedding_array = np.asarray(embedding, dtype=np.float32)

            # Verify embedding integrity
            if embedding_array.ndim != 1:
                logger.warning('Embedding must be 1D, got %dD', embedding_array.ndim)
                return False

            if not np.all(np.isfinite(embedding_array)):
                logger.warning('Embedding contains non-finite values')
                return False

            # Serialize to JSON
            embedding_json = embedding_to_json(embedding_array)
            if embedding_json is None:
                logger.warning('Failed to serialize embedding')
                return False

            # Save to database (reuses existing patients.face_encoding column)
            result = update_face_encoding(patient_id, embedding_json, face_image)

            if result:
                logger.info('Saved face embedding for patient %d', patient_id)
                return True

            logger.warning('Database update failed for patient %d', patient_id)
            return False

        except Exception as e:
            logger.warning('Failed to save face embedding for patient %d: %s',
                           patient_id, e)
            return False

    # =======================================================================
    # Loading
    # =======================================================================

    def load_all_patient_faces(self) -> List[PatientFace]:
        """
        Load all patients with stored face embeddings.

        Returns:
            List of PatientFace objects. Invalid/corrupted embeddings are skipped.
        """
        patient_faces = []

        try:
            rows = get_all_face_encodings()

            for row in rows:
                patient_id = row.get('patient_id')
                name = row.get('name', 'Unknown')
                face_encoding_str = row.get('face_encoding')

                if not face_encoding_str:
                    continue

                # Deserialize embedding
                embedding = embedding_from_json(face_encoding_str)
                if embedding is None:
                    logger.warning('Skipping corrupted embedding for patient %s',
                                   patient_id)
                    continue

                patient_faces.append(PatientFace(patient_id, name, embedding))

            logger.info('Loaded %d patient face embeddings', len(patient_faces))
            return patient_faces

        except Exception as e:
            logger.warning('Failed to load patient faces: %s', e)
            return []

    def load_patient_face(self, patient_id: int) -> Optional[PatientFace]:
        """
        Load a single patient's face embedding.

        Args:
            patient_id: Patient database ID.

        Returns:
            PatientFace object or None if not found/invalid.
        """
        try:
            patient = get_patient_by_id(patient_id)
            if not patient:
                return None

            face_encoding_str = patient.get('face_encoding')
            if not face_encoding_str:
                return None

            embedding = embedding_from_json(face_encoding_str)
            if embedding is None:
                logger.warning('Corrupted embedding for patient %d', patient_id)
                return None

            return PatientFace(patient_id, patient['name'], embedding)

        except Exception as e:
            logger.warning('Failed to load face for patient %d: %s', patient_id, e)
            return None

    # =======================================================================
    # Duplicate detection
    # =======================================================================

    def has_face_embedding(self, patient_id: int) -> bool:
        """
        Check if a patient already has a face embedding.

        Args:
            patient_id: Patient database ID.

        Returns:
            True if the patient has a stored embedding.
        """
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        return bool(patient.get('face_encoding'))

    def find_duplicate_embedding(
        self,
        embedding: np.ndarray,
        threshold: float = 0.5,
        exclude_patient_id: Optional[int] = None
    ) -> Optional[PatientFace]:
        """
        Find an existing patient whose embedding matches the given one.

        Used to prevent duplicate face registrations.

        Args:
            embedding: Query embedding (512-dim).
            threshold: Cosine similarity threshold (default 0.5).
            exclude_patient_id: Optional patient ID to exclude from search.

        Returns:
            Matching PatientFace or None if no duplicate found.
        """
        if embedding is None:
            return None

        from similarity import batch_cosine_similarity

        patient_faces = self.load_all_patient_faces()
        if not patient_faces:
            return None

        # Filter out excluded patient
        if exclude_patient_id is not None:
            patient_faces = [pf for pf in patient_faces
                             if pf.patient_id != exclude_patient_id]

        if not patient_faces:
            return None

        embeddings = [pf.embedding for pf in patient_faces]
        scores = batch_cosine_similarity(embedding, embeddings)

        if scores.size == 0:
            return None

        best_index = int(np.argmax(scores))
        best_score = float(scores[best_index])

        if best_score >= threshold:
            return patient_faces[best_index]

        return None

    # =======================================================================
    # Statistics
    # =======================================================================

    def count_registered_faces(self) -> int:
        """
        Count the number of patients with registered face embeddings.

        Returns:
            Integer count.
        """
        return len(self.load_all_patient_faces())