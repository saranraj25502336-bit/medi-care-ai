# ============================================
# CAMERA MODULE
# OpenCV camera capture ONLY.
# No face detection or recognition here.
# All AI tasks are delegated to InsightFace.
# ============================================

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Exception raised for camera-related errors."""
    pass


class CameraCapture:
    """
    Camera capture using OpenCV.

    Responsibilities (OpenCV only):
    - Open/close camera
    - Read frames
    - Resize frames
    - Color conversion (BGR → RGB)
    - Display preview windows (development only)

    NOT responsible for:
    - Face detection
    - Face recognition
    - Face matching
    """

    def __init__(
        self,
        camera_index: Optional[int] = None,
        width: int = 640,
        height: int = 480,
        fps: int = 30
    ):
        """
        Initialize the camera capture.

        Args:
            camera_index: Camera device index (defaults to Config.CAMERA_INDEX).
            width: Desired frame width.
            height: Desired frame height.
            fps: Desired frames per second.
        """

        
        self.camera_index = camera_index if camera_index is not None else Config.CAMERA_INDEX
        self.width = width
        self.height = height
        self.fps = fps





        self._cap = None
        self._is_open = False
        self._lock = threading.Lock()
        self._last_frame = None
        self._last_frame_time = 0.0





    def open(self) -> bool:
        """
        Open the camera.

        Returns:
            True if camera opened successfully, False otherwise.
        """
        with self._lock:
            if self._is_open:
                return True

            try:
                self._cap = cv2.VideoCapture(self.camera_index)

                if not self._cap.isOpened():
                    logger.warning('Failed to open camera %d', self.camera_index)
                    self._cap = None
                    return False

                # Set camera properties
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self._cap.set(cv2.CAP_PROP_FPS, self.fps)

                self._is_open = True
                logger.info('Camera %d opened (%dx%d)', self.camera_index,
                            self.width, self.height)
                return True

            except Exception as e:
                logger.error('Camera open error: %s', e)
                self._cap = None
                self._is_open = False
                return False

    def close(self) -> None:
        """Close the camera and release resources."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._is_open = False
            self._last_frame = None
            logger.info('Camera closed')

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # =======================================================================
    # Frame capture
    # =======================================================================

    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read a single frame from the camera.

        Returns:
            RGB numpy array (H, W, 3) or None if camera is not available.
        """
        with self._lock:
            if not self._is_open or self._cap is None:
                return None

            try:
                ret, frame = self._cap.read()

                if not ret or frame is None:
                    logger.warning('Failed to read frame from camera')
                    return None

                # Convert BGR (OpenCV) to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                self._last_frame = rgb_frame
                self._last_frame_time = time.time()

                return rgb_frame

            except Exception as e:
                logger.warning('Frame read error: %s', e)
                return None

    def read_frame_bgr(self) -> Optional[np.ndarray]:
        """
        Read a single frame in BGR format (OpenCV native).

        Returns:
            BGR numpy array or None if camera is not available.
        """
        with self._lock:
            if not self._is_open or self._cap is None:
                return None

            try:
                ret, frame = self._cap.read()

                if not ret or frame is None:
                    logger.warning('Failed to read frame from camera')
                    return None

                self._last_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._last_frame_time = time.time()

                return frame

            except Exception as e:
                logger.warning('Frame read error: %s', e)
                return None

    def get_last_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recently captured frame.

        Returns:
            RGB numpy array or None if no frame captured yet.
        """
        return self._last_frame

    # =======================================================================
    # Frame processing (OpenCV only)
    # =======================================================================

    def resize_frame(self, frame: np.ndarray, width: int, height: int) -> np.ndarray:
        """
        Resize a frame to the specified dimensions.

        Args:
            frame: Input frame.
            width: Target width.
            height: Target height.

        Returns:
            Resized frame.
        """
        if frame is None:
            return None
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    def convert_to_rgb(self, frame: np.ndarray) -> np.ndarray:
        """
        Convert a BGR frame to RGB.

        Args:
            frame: BGR frame from OpenCV.

        Returns:
            RGB frame.
        """
        if frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # =======================================================================
    # Preview (development only)
    # =======================================================================

    def show_preview(self, window_name: str = 'Camera Preview', duration_ms: int = 1) -> None:
        """
        Display a live camera preview window.

        NOTE: This is for development/testing only.
        In production, the browser handles video display.

        Args:
            window_name: Name of the preview window.
            duration_ms: Wait time between frames (ms).
        """
        if not self._is_open:
            self.open()

        if not self._is_open:
            logger.error('Cannot show preview: camera not available')
            return

        logger.info('Starting camera preview. Press ESC to exit.')

        while True:
            frame = self.read_frame_bgr()
            if frame is None:
                logger.warning('Camera disconnected during preview')
                break

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(duration_ms) & 0xFF
            if key == 27:  # ESC
                break

        cv2.destroyAllWindows()

    # =======================================================================
    # Status
    # =======================================================================

    @property
    def is_open(self) -> bool:
        """Check if the camera is currently open."""
        return self._is_open

    def check_camera(self) -> dict:
        """
        Check camera availability and return status.

        Returns:
            dict with keys:
                - available: bool
                - camera_index: int
                - message: str
        """
        if self._is_open:
            return {
                'available': True,
                'camera_index': self.camera_index,
                'message': 'Camera is open'
            }

        # Try to open briefly to check
        test_cap = cv2.VideoCapture(self.camera_index)
        if test_cap.isOpened():
            test_cap.release()
            return {
                'available': True,
                'camera_index': self.camera_index,
                'message': 'Camera is available'
            }

        return {
            'available': False,
            'camera_index': self.camera_index,
            'message': f'No camera detected at index {self.camera_index}'
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------
def get_available_cameras(max_check: int = 5) -> list:
    """
    Check which camera indices are available.

    Args:
        max_check: Maximum number of camera indices to check.

    Returns:
        List of available camera indices.
    """
    available = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available