# ============================================
# SIMILARITY MODULE
# Cosine Similarity matching for face embeddings.
# Uses ArcFace embeddings from InsightFace.
# ============================================

import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------
def cosine_similarity(embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        embedding_a: First embedding (1D numpy array).
        embedding_b: Second embedding (1D numpy array).

    Returns:
        Cosine similarity score in range [-1, 1].
        Returns 0.0 if either embedding is invalid.
    """
    if embedding_a is None or embedding_b is None:
        return 0.0

    try:
        a = np.asarray(embedding_a, dtype=np.float32).flatten()
        b = np.asarray(embedding_b, dtype=np.float32).flatten()

        if a.size == 0 or b.size == 0:
            return 0.0

        # Ensure same length
        min_len = min(a.size, b.size)
        if min_len < 10:
            logger.warning('Embeddings too short for comparison: %d', min_len)
            return 0.0

        a = a[:min_len]
        b = b[:min_len]

        # Compute cosine similarity
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    except Exception as e:
        logger.warning('Cosine similarity error: %s', e)
        return 0.0


def batch_cosine_similarity(
    query_embedding: np.ndarray,
    stored_embeddings: List[np.ndarray]
) -> np.ndarray:
    """
    Compute cosine similarity between a query embedding and a list of stored embeddings.

    This is optimized for performance using matrix operations.

    Args:
        query_embedding: Query embedding (1D numpy array).
        stored_embeddings: List of stored embeddings (each 1D numpy array).

    Returns:
        numpy array of similarity scores (same length as stored_embeddings).
    """
    if query_embedding is None or not stored_embeddings:
        return np.array([], dtype=np.float32)

    try:
        query = np.asarray(query_embedding, dtype=np.float32).flatten()
        query_norm = np.linalg.norm(query)

        if query_norm == 0:
            return np.zeros(len(stored_embeddings), dtype=np.float32)

        query_normalized = query / query_norm

        # Build matrix of stored embeddings
        matrix = []
        for emb in stored_embeddings:
            if emb is None:
                matrix.append(np.zeros_like(query_normalized))
                continue

            e = np.asarray(emb, dtype=np.float32).flatten()
            min_len = min(len(e), len(query_normalized))
            if min_len < 10:
                matrix.append(np.zeros_like(query_normalized))
                continue

            # Pad/truncate to match query length
            padded = np.zeros_like(query_normalized)
            padded[:min_len] = e[:min_len]

            norm = np.linalg.norm(padded)
            if norm > 0:
                padded = padded / norm

            matrix.append(padded)

        if not matrix:
            return np.array([], dtype=np.float32)

        # Matrix multiplication for batch cosine similarity
        matrix = np.array(matrix, dtype=np.float32)
        scores = matrix @ query_normalized

        return scores

    except Exception as e:
        logger.warning('Batch cosine similarity error: %s', e)
        return np.array([], dtype=np.float32)


# ---------------------------------------------------------------------------
# Best match
# ---------------------------------------------------------------------------
def find_best_match(
    query_embedding: np.ndarray,
    stored_embeddings: List[np.ndarray],
    threshold: float = 0.5
) -> Optional[Tuple[int, float]]:
    """
    Find the best matching embedding from a list.

    Args:
        query_embedding: Query embedding (1D numpy array).
        stored_embeddings: List of stored embeddings.
        threshold: Minimum similarity score to consider a match.

    Returns:
        Tuple of (index, similarity_score) for the best match,
        or None if no match exceeds the threshold.
    """
    if query_embedding is None or not stored_embeddings:
        return None

    scores = batch_cosine_similarity(query_embedding, stored_embeddings)

    if scores.size == 0:
        return None

    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])

    if best_score >= threshold:
        return best_index, best_score

    return None


# ---------------------------------------------------------------------------
# Top-K matches
# ---------------------------------------------------------------------------
def find_top_k_matches(
    query_embedding: np.ndarray,
    stored_embeddings: List[np.ndarray],
    k: int = 3,
    threshold: float = 0.0
) -> List[Tuple[int, float]]:
    """
    Find the top-K matching embeddings.

    Args:
        query_embedding: Query embedding (1D numpy array).
        stored_embeddings: List of stored embeddings.
        k: Number of top matches to return.
        threshold: Minimum similarity score to include.

    Returns:
        List of (index, similarity_score) tuples, sorted by score descending.
    """
    if query_embedding is None or not stored_embeddings:
        return []

    scores = batch_cosine_similarity(query_embedding, stored_embeddings)

    if scores.size == 0:
        return []

    # Get top-K indices
    k = min(k, scores.size)
    top_indices = np.argsort(scores)[::-1][:k]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score >= threshold:
            results.append((int(idx), score))

    return results


# ---------------------------------------------------------------------------
# Embedding normalization
# ---------------------------------------------------------------------------
def normalize_embedding(embedding: np.ndarray) -> Optional[np.ndarray]:
    """
    Normalize an embedding to unit length (L2 norm = 1).

    Args:
        embedding: Input embedding (1D numpy array).

    Returns:
        Normalized embedding or None if invalid.
    """
    if embedding is None:
        return None

    try:
        e = np.asarray(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(e)

        if norm == 0:
            return None

        return e / norm

    except Exception as e:
        logger.warning('Embedding normalization error: %s', e)
        return None


# ---------------------------------------------------------------------------
# Confidence score conversion
# ---------------------------------------------------------------------------
def similarity_to_confidence(similarity: float) -> float:
    """
    Convert a cosine similarity score to a confidence percentage (0-1).

    ArcFace embeddings typically have:
    - Same person: 0.5 - 0.9
    - Different person: -0.2 - 0.3

    This maps the similarity to a more intuitive confidence score.

    Args:
        similarity: Cosine similarity score.

    Returns:
        Confidence score in range [0, 1].
    """
    # Map similarity from [-0.2, 1.0] to [0, 1]
    # Below -0.2 → 0, above 1.0 → 1
    confidence = (similarity + 0.2) / 1.2
    return float(max(0.0, min(1.0, confidence)))

# ---------------------------------------------------------------------------
# Ensemble similarity (cosine + euclidean)
# ---------------------------------------------------------------------------

def ensemble_similarity(
    embedding_a: np.ndarray,
    embedding_b: np.ndarray,
    cosine_weight: float = 0.7,
    euclidean_weight: float = 0.3
) -> float:
    """
    Compute an ensemble similarity score combining cosine similarity
    and normalized euclidean distance.

    Cosine similarity captures angle; euclidean captures magnitude.
    Combining both gives a more robust match score.

    Args:
        embedding_a: First embedding (1D numpy array, L2-normalized).
        embedding_b: Second embedding (1D numpy array, L2-normalized).
        cosine_weight: Weight for cosine similarity (default 0.7).
        euclidean_weight: Weight for euclidean component (default 0.3).

    Returns:
        Ensemble score in range [0, 1].
    """
    if embedding_a is None or embedding_b is None:
        return 0.0

    try:
        a = np.asarray(embedding_a, dtype=np.float32).flatten()
        b = np.asarray(embedding_b, dtype=np.float32).flatten()

        min_len = min(len(a), len(b))
        if min_len < 10:
            return 0.0

        a, b = a[:min_len], b[:min_len]

        # Normalize to unit length
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a > 0:
            a = a / norm_a
        if norm_b > 0:
            b = b / norm_b

        # Cosine similarity: dot product of unit vectors
        cos_sim = float(np.dot(a, b))
        cos_sim = max(-1.0, min(1.0, cos_sim))
        # Map cosine from [-1, 1] to [0, 1]
        cos_score = (cos_sim + 1.0) / 2.0

        # Euclidean distance between unit vectors (range [0, 2])
        euc_dist = float(np.linalg.norm(a - b))
        # Convert to similarity: 1 - dist/2 (range [0, 1])
        euc_score = 1.0 - (euc_dist / 2.0)

        return float(cosine_weight * cos_score + euclidean_weight * euc_score)

    except Exception as e:
        logger.warning('Ensemble similarity error: %s', e)
        return 0.0


def batch_ensemble_similarity(
    query_embedding: np.ndarray,
    stored_embeddings: List[np.ndarray],
    cosine_weight: float = 0.7,
    euclidean_weight: float = 0.3
) -> np.ndarray:
    """
    Compute ensemble similarity scores between a query and stored embeddings.

    Args:
        query_embedding: Query embedding (1D numpy array).
        stored_embeddings: List of stored embeddings.
        cosine_weight: Weight for cosine component.
        euclidean_weight: Weight for euclidean component.

    Returns:
        numpy array of ensemble scores.
    """
    if query_embedding is None or not stored_embeddings:
        return np.array([], dtype=np.float32)

    scores = []
    for emb in stored_embeddings:
        scores.append(ensemble_similarity(query_embedding, emb, cosine_weight, euclidean_weight))

    return np.array(scores, dtype=np.float32)


def find_best_match_with_margin(
    query_embedding: np.ndarray,
    stored_embeddings: List[np.ndarray],
    threshold: float = 0.5,
    min_margin: float = 0.04
) -> Optional[Tuple[int, float, float]]:
    """
    Find the best match requiring a margin above the 2nd best match.

    This prevents false positives when two faces score similarly close.
    A confident match should be clearly the best -- not ambiguous.

    Args:
        query_embedding: Query embedding.
        stored_embeddings: List of stored embeddings.
        threshold: Minimum score to accept a match.
        min_margin: Required gap between 1st and 2nd best score.

    Returns:
        Tuple of (index, score, margin) or None if no confident match.
    """
    if query_embedding is None or not stored_embeddings:
        return None

    scores = batch_ensemble_similarity(query_embedding, stored_embeddings)

    if scores.size == 0:
        return None

    if scores.size == 1:
        # Only one face registered -- no margin needed
        if scores[0] >= threshold:
            return int(0), float(scores[0]), 1.0
        return None

    # Get top-2 indices
    top2_indices = np.argsort(scores)[::-1][:2]
    best_idx = int(top2_indices[0])
    second_idx = int(top2_indices[1])

    best_score = float(scores[best_idx])
    second_score = float(scores[second_idx])
    margin = best_score - second_score

    if best_score >= threshold and margin >= min_margin:
        return best_idx, best_score, margin

    return None
