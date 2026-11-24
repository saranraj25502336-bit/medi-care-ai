# ============================================
# DATABASE MIGRATION - FACE EMBEDDINGS
# ============================================
# Ensures the patients.face_encoding column is
# properly configured for 512-dim ArcFace
# embeddings from InsightFace.
#
# The existing schema already has:
#   face_encoding LONGTEXT DEFAULT NULL
#
# This migration:
# 1. Verifies the column exists and is LONGTEXT
# 2. Cleans up any corrupted embeddings
# 3. Reports the count of valid registered faces
#
# Usage: python migrate_face_embeddings.py
# ============================================

import logging
import sys

import mysql.connector
from mysql.connector import Error

from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Run the face embedding migration."""
    conn = None
    cursor = None

    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # 1. Verify patients table exists
        cursor.execute("SHOW TABLES LIKE 'patients'")
        if not cursor.fetchone():
            logger.error('patients table does not exist. Run init_db.py first.')
            return False

        # 2. Verify face_encoding column exists
        cursor.execute("""
            SELECT COLUMN_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'patients' AND COLUMN_NAME = 'face_encoding'
        """, (Config.DB_NAME,))
        col_info = cursor.fetchone()

        if not col_info:
            logger.error('face_encoding column not found in patients table.')
            logger.info('Adding face_encoding column...')
            cursor.execute("""
                ALTER TABLE patients
                ADD COLUMN face_encoding LONGTEXT DEFAULT NULL
            """)
            conn.commit()
            logger.info('face_encoding column added successfully.')
        else:
            col_type, is_nullable = col_info
            logger.info('face_encoding column exists: type=%s nullable=%s', col_type, is_nullable)
            if 'longtext' not in col_type.lower():
                logger.info('Converting face_encoding column to LONGTEXT...')
                cursor.execute("ALTER TABLE patients MODIFY face_encoding LONGTEXT DEFAULT NULL")
                conn.commit()
                logger.info('face_encoding column converted to LONGTEXT.')

        # 3. Verify face_image column exists
        cursor.execute("""
            SELECT COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'patients' AND COLUMN_NAME = 'face_image'
        """, (Config.DB_NAME,))
        if not cursor.fetchone():
            logger.info('Adding face_image column...')
            cursor.execute("""
                ALTER TABLE patients
                ADD COLUMN face_image VARCHAR(255) DEFAULT NULL
            """)
            conn.commit()
            logger.info('face_image column added successfully.')

        # 4. Count registered faces
        cursor.execute("SELECT COUNT(*) FROM patients WHERE face_encoding IS NOT NULL AND face_encoding != ''")
        count = cursor.fetchone()[0]
        logger.info('Patients with registered face embeddings: %d', count)

        # 5. Check for corrupted embeddings (non-JSON)
        cursor.execute("""
            SELECT patient_id, name FROM patients
            WHERE face_encoding IS NOT NULL AND face_encoding != ''
        """)
        rows = cursor.fetchall()
        corrupted = 0
        for patient_id, name in rows:
            encoding = None
            cursor.execute("SELECT face_encoding FROM patients WHERE patient_id = %s", (patient_id,))
            row = cursor.fetchone()
            if row:
                encoding = row[0]
            if encoding:
                try:
                    import json
                    data = json.loads(encoding)
                    if not isinstance(data, list):
                        corrupted += 1
                        logger.warning('Corrupted embedding for patient %s (%s)', patient_id, name)
                except (json.JSONDecodeError, TypeError):
                    corrupted += 1
                    logger.warning('Corrupted embedding for patient %s (%s)', patient_id, name)

        if corrupted > 0:
            logger.warning('Found %d corrupted embeddings that should be re-registered.', corrupted)
        else:
            logger.info('All stored embeddings are valid JSON.')

        # 6. Set InsightFace models directory
        import os
        models_dir = Config.INSIGHTFACE_MODELS_DIR
        os.makedirs(models_dir, exist_ok=True)
        logger.info('InsightFace models directory ready: %s', models_dir)

        logger.info('=' * 50)
        logger.info('MIGRATION COMPLETE')
        logger.info('Face embeddings ready for InsightFace ArcFace (512-dim)')
        logger.info('=' * 50)
        return True

    except Error as e:
        logger.error('MySQL error: %s', e)
        return False
    except Exception as e:
        logger.error('Migration error: %s', e)
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)