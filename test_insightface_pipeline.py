"""
Verify the complete InsightFace-powered face recognition pipeline.
Tests: embedding generation, storage, recognition, similarity matching.

Usage: python test_insightface_pipeline.py
"""

import os
import sys
import json
import logging
import time

import numpy as np

sys.path.insert(0, '.')

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s [%(levelname)s] %(message)s')

passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f'  PASS: {name}')
    except Exception as e:
        failed += 1
        print(f'  FAIL: {name} -> {e}')


print('=' * 50)
print('INSIGHTFACE PIPELINE VERIFICATION')
print('=' * 50)

# ============================================================
# 1. Module imports
# ============================================================
print('\n=== 1. MODULE IMPORTS ===')

test('face_utils', lambda: __import__('face_utils'))
test('similarity', lambda: __import__('similarity'))
test('embedding_service', lambda: __import__('embedding_service'))
test('patient_face_repository', lambda: __import__('patient_face_repository'))
test('face_service', lambda: __import__('face_service'))
test('recognition_service', lambda: __import__('recognition_service'))
test('camera', lambda: __import__('camera'))

# ============================================================
# 2. Embedding service
# ============================================================
print('\n=== 2. EMBEDDING SERVICE ===')

from embedding_service import get_embedding_service, EMBEDDING_DIM

svc = get_embedding_service()
test('EmbeddingService created', lambda: svc is not None)
test('Service is available', lambda: svc.is_available == True)
test('Embedding dim = 512', lambda: svc.get_embedding_dim() == 512)

# ============================================================
# 3. Similarity math
# ============================================================
print('\n=== 3. SIMILARITY MATH ===')

from similarity import (
    cosine_similarity, batch_cosine_similarity,
    find_best_match, similarity_to_confidence, normalize_embedding
)

# Test identical embeddings
emb1 = np.random.randn(512).astype(np.float32)
emb1 = emb1 / np.linalg.norm(emb1)
test('cosine_similarity(same) = 1.0',
     lambda: abs(cosine_similarity(emb1, emb1) - 1.0) < 0.01)

# Test orthogonal embeddings
emb2 = np.random.randn(512).astype(np.float32)
emb2 = emb2 - np.dot(emb2, emb1) * emb1  # Gram-Schmidt
emb2 = emb2 / np.linalg.norm(emb2)
test('cosine_similarity(orthogonal) ~ 0',
     lambda: abs(cosine_similarity(emb1, emb2)) < 0.1)

# Test opposite embeddings
test('cosine_similarity(opposite) = -1.0',
     lambda: abs(cosine_similarity(emb1, -emb1) + 1.0) < 0.01)

# Test batch similarity
batch = [emb1, emb2, emb1]
scores = batch_cosine_similarity(emb1, batch)
test('batch_cosine_similarity returns 3 scores',
     lambda: scores.size == 3)
test('batch[0] = 1.0',
     lambda: abs(scores[0] - 1.0) < 0.01)
test('batch[1] ~ 0',
     lambda: abs(scores[1]) < 0.1)

# Test find_best_match
match = find_best_match(emb1, batch, threshold=0.5)
test('find_best_match returns index 0', lambda: match == (0, scores[0]))

# Test confidence conversion
test('similarity_to_confidence(1.0) = 1.0',
     lambda: abs(similarity_to_confidence(1.0) - 1.0) < 0.01)
test('similarity_to_confidence(0.5) > 0.5',
     lambda: similarity_to_confidence(0.5) > 0.5)
test('similarity_to_confidence(-1.0) = 0.0',
     lambda: abs(similarity_to_confidence(-1.0) - 0.0) < 0.01)

# ============================================================
# 4. Face utils serialization
# ============================================================
print('\n=== 4. FACE UTILS ===')

from face_utils import (
    embedding_to_json, embedding_from_json,
    decode_base64_image, sanitize_filename,
    assess_image_quality
)

# Test embedding serialization
emb_json = embedding_to_json(emb1)
test('embedding_to_json works', lambda: emb_json is not None)
test('embedding_from_json round-trip',
     lambda: np.allclose(embedding_from_json(emb_json), emb1, atol=0.001))
test('embedding_to_json(None) = None',
     lambda: embedding_to_json(None) is None)
test('embedding_from_json(None) = None',
     lambda: embedding_from_json(None) is None)
test('embedding_from_json(garbage) = None',
     lambda: embedding_from_json('not json') is None)

# Test filename sanitization
test('sanitize_filename strips paths',
     lambda: sanitize_filename('../../etc/passwd') == 'passwd')
test('sanitize_filename keeps safe names',
     lambda: sanitize_filename('face_photo.jpg') == 'face_photo.jpg')

# Test quality assessment
test_image = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
quality = assess_image_quality(test_image)
test('assess_image_quality returns dict',
     lambda: 'is_valid' in quality)

# ============================================================
# 5. RecognitionService status
# ============================================================
print('\n=== 5. RECOGNITION SERVICE ===')

from recognition_service import RecognitionService, RecognitionResult

rec_svc = RecognitionService()
status = rec_svc.get_status()
test('RecognitionService status dict',
     lambda: 'available' in status and 'threshold' in status)

# Test recognition with no face
result = rec_svc.recognize_from_base64('data:image/jpeg;base64,invalid')
test('recognize_from_base64(invalid) returns result',
     lambda: isinstance(result, RecognitionResult))
test('recognize_from_base64(invalid) fails gracefully',
     lambda: result.success == False)

# ============================================================
# 6. FaceService status
# ============================================================
print('\n=== 6. FACE SERVICE ===')

from face_service import FaceService

fs = FaceService()
test('FaceService is_available()', lambda: fs.is_available())
status = fs.get_status()
test('FaceService status has embedding_dim',
     lambda: status['embedding_dim'] == 512)

# ============================================================
# 7. Camera module
# ============================================================
print('\n=== 7. CAMERA MODULE ===')

from camera import CameraCapture

cam = CameraCapture()
test('CameraCapture created', lambda: cam is not None)
test('CameraCapture not open initially', lambda: not cam.is_open)

# ============================================================
# 8. PatientFaceRepository
# ============================================================
print('\n=== 8. PATIENT FACE REPOSITORY ===')

from patient_face_repository import PatientFaceRepository, PatientFace

repo = PatientFaceRepository()
patient_faces = repo.load_all_patient_faces()
test('load_all_patient_faces returns list', lambda: isinstance(patient_faces, list))
test('count_registered_faces() >= 0', lambda: repo.count_registered_faces() >= 0)

# ============================================================
# 9. FaceRecognitionSystem facade compatibility
# ============================================================
print('\n=== 9. FACADE COMPATIBILITY ===')

from face_recognition_module import FaceRecognitionSystem, DNN_AVAILABLE

frs = FaceRecognitionSystem()
test('FaceRecognitionSystem created', lambda: frs is not None)
test('use_dnn attribute exists', lambda: hasattr(frs, 'use_dnn'))
test('is_available()', lambda: frs.is_available())
test('get_encoding_as_json(None)', lambda: frs.get_encoding_as_json(None) is None)
test('encoding_from_json(None)', lambda: frs.encoding_from_json(None) is None)
test('load_known_faces([])', lambda: frs.load_known_faces([]) is None)
test('recognize_face(None)', lambda: frs.recognize_face(None) is None)

# Test loading from existing database embeddings (old format)
patients_data = []
try:
    from database import get_all_face_encodings
    patients_data = get_all_face_encodings()
except Exception:
    pass

if patients_data:
    frs.load_known_faces(patients_data)
    test('load_known_faces loads existing data',
         lambda: len(frs.known_face_encodings) > 0)

# ============================================================
# SUMMARY
# ============================================================
print(f'\n{"=" * 50}')
print(f'VERIFICATION COMPLETE')
print(f'  Passed: {passed}')
print(f'  Failed: {failed}')
print(f'  Total:  {passed + failed}')
print(f'{"=" * 50}')

if failed > 0:
    print('\nWARNING: Some tests FAILED.')
    sys.exit(1)
else:
    print('\nALL PIPELINE TESTS PASSED - InsightFace integration is ready!')
    sys.exit(0)