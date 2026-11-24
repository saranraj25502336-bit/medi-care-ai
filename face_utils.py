# ============================================
# FACE UTILITIES MODULE
# Shared utility functions for image handling,
# validation, and preprocessing.
# Used by all face recognition modules.
# ============================================

import base64
import io
import logging
import os
import re
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_DIMENSION = 4096
MIN_FACE_DIMENSION = 40  # Minimum dimension for reliable embedding
ALLOWED_IMAGE_FORMATS = {'jpeg', 'jpg', 'png', 'bmp', 'webp'}

# ---------------------------------------------------------------------------
# Image preprocessing for face recognition
# ---------------------------------------------------------------------------

def preprocess_for_recognition(image: np.ndarray) -> np.ndarray:
    """
    Enhance image quality before face detection/recognition.

    Applies:
    1. CLAHE (Contrast Limited Adaptive Histogram Equalization) for local
       contrast enhancement — improves recognition in poor lighting.
    2. Unsharp mask sharpening — makes facial features crisper.
    3. Denoising — reduces noise from webcam compression artifacts.

    Args:
        image: RGB numpy array.

    Returns:
        Enhanced RGB numpy array.
    """
    if image is None:
        return image

    try:
        # Convert to LAB colour space for CLAHE (only on L channel)
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # CLAHE on luminance only
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        # Reconstruct LAB and convert back to RGB
        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

        # Unsharp mask sharpening: sharpen = original + α*(original - blurred)
        blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.5)
        sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

        # Light denoising to remove webcam compression noise
        denoised = cv2.fastNlMeansDenoisingColored(sharpened, None, 3, 3, 7, 21)

        return denoised

    except Exception as e:
        logger.warning('Image preprocessing failed, using original: %s', e)
        return image


def check_image_brightness(image: np.ndarray) -> dict:
    """
    Check image brightness and suggest correction.

    Args:
        image: RGB numpy array.

    Returns:
        dict with keys: brightness (float), is_too_dark (bool), is_too_bright (bool), message (str)
    """
    if image is None:
        return {'brightness': 0, 'is_too_dark': True, 'is_too_bright': False, 'message': 'Invalid image'}

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray))

    return {
        'brightness': brightness,
        'is_too_dark': brightness < 50,
        'is_too_bright': brightness > 220,
        'message': (
            'Image is too dark. Please improve lighting.' if brightness < 50
            else 'Image is overexposed. Reduce lighting.' if brightness > 220
            else 'Lighting is good.'
        )
    }


# Base64 data URL pattern: data:image/jpeg;base64,...
BASE64_PATTERN = re.compile(
    r'^data:image/(?P<ext>jpeg|jpg|png|bmp|webp);base64,(?P<data>.+)$',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Base64 decoding
# ---------------------------------------------------------------------------
def decode_base64_image(base64_string: str) -> Optional[np.ndarray]:
    """
    Decode a base64-encoded image string into a numpy RGB array.

    Args:
        base64_string: Base64 data URL (e.g. "data:image/jpeg;base64,...")
                       or raw base64 string.

    Returns:
        RGB numpy array (H, W, 3) or None if decoding fails.
    """
    if not base64_string:
        return None

    try:
        # Strip data URL prefix if present
        match = BASE64_PATTERN.match(base64_string)
        if match:
            base64_string = match.group('data')
        elif ',' in base64_string:
            # Handle "data:image/...;base64,..." without regex match
            base64_string = base64_string.split(',', 1)[1]

        # Decode base64
        image_bytes = base64.b64decode(base64_string)

        # Check size limit
        if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            logger.warning('Image exceeds %d MB size limit', MAX_IMAGE_SIZE_MB)
            return None

        # Decode with PIL first (handles more formats)
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert('RGB')
        rgb_array = np.array(image)

        # Validate dimensions
        if rgb_array.size == 0:
            logger.warning('Decoded image is empty')
            return None

        h, w = rgb_array.shape[:2]
        if h > MAX_IMAGE_DIMENSION or w > MAX_IMAGE_DIMENSION:
            logger.warning('Image dimensions %dx%d exceed limit', w, h)
            return None

        return rgb_array

    except (base64.binascii.Error, ValueError, OSError, Image.UnidentifiedImageError) as e:
        logger.warning('Base64 image decode failed: %s', e)
        return None
    except Exception as e:
        logger.warning('Unexpected image decode error: %s', e)
        return None


# ---------------------------------------------------------------------------
# Image format conversion
# ---------------------------------------------------------------------------
def rgb_to_bgr(rgb_array: np.ndarray) -> np.ndarray:
    """Convert RGB array to BGR (OpenCV format)."""
    if rgb_array is None or len(rgb_array.shape) != 3:
        return rgb_array
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)


def bgr_to_rgb(bgr_array: np.ndarray) -> np.ndarray:
    """Convert BGR array to RGB."""
    if bgr_array is None or len(bgr_array.shape) != 3:
        return bgr_array
    return cv2.cvtColor(bgr_array, cv2.COLOR_BGR2RGB)


def ensure_rgb(image: np.ndarray) -> np.ndarray:
    """
    Ensure image is in RGB format.

    - If grayscale (2D), convert to 3-channel RGB.
    - If RGBA (4 channels), drop alpha.
    - If BGR, convert to RGB.
    """
    if image is None:
        return None

    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    if len(image.shape) == 3:
        channels = image.shape[2]
        if channels == 4:
            return image[:, :, :3]
        if channels == 3:
            return image
        if channels == 1:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    logger.warning('Unsupported image shape: %s', image.shape)
    return None


# ---------------------------------------------------------------------------
# Image resizing
# ---------------------------------------------------------------------------
def resize_image(image: np.ndarray, max_dimension: int = 640) -> np.ndarray:
    """
    Resize image while preserving aspect ratio if it exceeds max_dimension.

    Args:
        image: Input image array.
        max_dimension: Maximum width/height allowed.

    Returns:
        Resized image or original if already within limits.
    """
    if image is None:
        return None

    h, w = image.shape[:2]
    if max(h, w) <= max_dimension:
        return image

    scale = max_dimension / float(max(h, w))
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# Image quality assessment
# ---------------------------------------------------------------------------
def assess_image_quality(image: np.ndarray) -> dict:
    """
    Assess the quality of an image for face recognition.

    Checks:
    - Resolution (minimum dimensions)
    - Sharpness (Laplacian variance -- detects blur)
    - Brightness (too dark / too bright)
    - Channel validity

    Args:
        image: RGB numpy array.

    Returns:
        dict with keys:
            - is_valid: bool
            - width: int
            - height: int
            - sharpness: float (Laplacian variance; >100 is good)
            - brightness: float (mean pixel value)
            - issues: list of str
    """
    issues = []

    if image is None:
        return {
            'is_valid': False,
            'width': 0,
            'height': 0,
            'sharpness': 0.0,
            'brightness': 0.0,
            'issues': ['Image is None']
        }

    h, w = image.shape[:2]

    # Resolution check
    if w < MIN_FACE_DIMENSION or h < MIN_FACE_DIMENSION:
        issues.append(f'Image too small: {w}x{h} (min {MIN_FACE_DIMENSION}x{MIN_FACE_DIMENSION})')

    # Sharpness: Laplacian variance -- higher = sharper
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < 50:
            issues.append(f'Image appears blurry (sharpness={laplacian_var:.1f}, need >50)')
    except Exception:
        laplacian_var = 0.0

    # Brightness check
    try:
        gray_check = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
        brightness = float(np.mean(gray_check))
        if brightness < 40:
            issues.append('Image is too dark - please improve lighting')
        elif brightness > 230:
            issues.append('Image is overexposed - reduce lighting')
    except Exception:
        brightness = 0.0

    # Channel check
    if len(image.shape) == 3 and image.shape[2] not in (1, 3, 4):
        issues.append(f'Unexpected number of channels: {image.shape[2]}')

    return {
        'is_valid': len(issues) == 0,
        'width': w,
        'height': h,
        'sharpness': laplacian_var,
        'brightness': brightness,
        'issues': issues
    }


# ---------------------------------------------------------------------------
# Face crop validation
# ---------------------------------------------------------------------------
def validate_face_crop(face_crop: np.ndarray, min_dimension: int = MIN_FACE_DIMENSION) -> bool:
    """
    Validate that a face crop is usable for embedding generation.

    Args:
        face_crop: Cropped face image (RGB).
        min_dimension: Minimum width/height for a valid face.

    Returns:
        True if the crop is valid, False otherwise.
    """
    if face_crop is None:
        return False

    h, w = face_crop.shape[:2]
    if h < min_dimension or w < min_dimension:
        logger.debug('Face crop too small: %dx%d', w, h)
        return False

    quality = assess_image_quality(face_crop)
    return quality['is_valid']


# ---------------------------------------------------------------------------
# File validation (for uploaded images)
# ---------------------------------------------------------------------------
def validate_uploaded_image(file_storage) -> Tuple[bool, Optional[np.ndarray], str]:
    """
    Validate an uploaded image file.

    Args:
        file_storage: Flask/Werkzeug FileStorage object.

    Returns:
        (is_valid, rgb_array, error_message)
    """
    if file_storage is None:
        return False, None, 'No file provided'

    filename = file_storage.filename or ''
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext not in ALLOWED_IMAGE_FORMATS:
        return False, None, f'Invalid file format: {ext}. Allowed: {", ".join(sorted(ALLOWED_IMAGE_FORMATS))}'

    try:
        # Read file bytes
        file_bytes = file_storage.read()

        # Size check
        if len(file_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return False, None, f'File exceeds {MAX_IMAGE_SIZE_MB} MB limit'

        # Decode with PIL
        image = Image.open(io.BytesIO(file_bytes))
        image = image.convert('RGB')
        rgb_array = np.array(image)

        # Dimension check
        h, w = rgb_array.shape[:2]
        if h > MAX_IMAGE_DIMENSION or w > MAX_IMAGE_DIMENSION:
            return False, None, f'Image dimensions {w}x{h} exceed limit'

        return True, rgb_array, ''

    except Exception as e:
        logger.warning('Uploaded image validation failed: %s', e)
        return False, None, f'Invalid image file: {str(e)}'


# ---------------------------------------------------------------------------
# Embedding serialization
# ---------------------------------------------------------------------------
def embedding_to_json(embedding: np.ndarray) -> Optional[str]:
    """
    Serialize a face embedding numpy array to JSON string.

    Args:
        embedding: 1D numpy array of float32.

    Returns:
        JSON string or None if invalid.
    """
    if embedding is None:
        return None

    try:
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding, dtype=np.float32)

        if embedding.ndim != 1:
            logger.warning('Embedding must be 1D, got %dD', embedding.ndim)
            return None

        # Convert to list and serialize
        import json
        return json.dumps(embedding.astype(np.float32).tolist())

    except Exception as e:
        logger.warning('Embedding serialization failed: %s', e)
        return None


def embedding_from_json(json_string: Optional[str]) -> Optional[np.ndarray]:
    """
    Deserialize a face embedding from JSON string.

    Args:
        json_string: JSON string containing embedding list.

    Returns:
        numpy float32 array or None if invalid.
    """
    if not json_string:
        return None

    try:
        import json
        data = json.loads(json_string)

        if not isinstance(data, list):
            logger.warning('Embedding JSON is not a list')
            return None

        embedding = np.array(data, dtype=np.float32)

        if embedding.ndim != 1:
            logger.warning('Embedding must be 1D, got %dD', embedding.ndim)
            return None

        return embedding

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning('Embedding deserialization failed: %s', e)
        return None


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.

    Args:
        filename: Original filename.

    Returns:
        Sanitized filename with only safe characters.
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Keep only alphanumeric, dash, underscore, dot
    filename = re.sub(r'[^\w\-.]', '_', filename)

    # Limit length
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:90] + ext

    return filename or 'image.jpg'