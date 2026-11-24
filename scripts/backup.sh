#!/bin/bash
# Smart Hospital Database Backup Script
# Runs daily via cron or manually

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
DB_HOST="${MYSQL_HOST:-db}"
DB_USER="${MYSQL_USER:-smart_hospital}"
DB_PASSWORD="${MYSQL_PASSWORD}"
DB_NAME="${MYSQL_DATABASE:-hospital_management}"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup of ${DB_NAME}..."

# Perform backup
mysqldump \
    --host="${DB_HOST}" \
    --user="${DB_USER}" \
    --password="${DB_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --hex-blob \
    --complete-insert \
    "${DB_NAME}" | gzip > "${BACKUP_FILE}"

# Verify backup
if [[ -f "${BACKUP_FILE}" && -s "${BACKUP_FILE}" ]]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Backup completed: ${BACKUP_FILE} (${SIZE})"

    # Verify it can be read
    if gunzip -t "${BACKUP_FILE}" 2>/dev/null; then
        echo "[$(date)] Backup integrity verified"
    else
        echo "[$(date)] ERROR: Backup file corrupted!"
        exit 1
    fi
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Clean old backups
echo "[$(date)] Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

REMAINING=$(find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" | wc -l)
echo "[$(date)] Cleanup complete. ${REMAINING} backups retained."

echo "[$(date)] Backup process finished successfully."