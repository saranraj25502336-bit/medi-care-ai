# -*- coding: utf-8 -*-
"""
Database migration runner.
- Executes all .sql files inside the migrations folder against the configured DB.
- Seeds per-doctor bcrypt passwords (default 'doctor123') for doctors without one.
- Idempotent: safe to run multiple times.

Usage:
    python migrations/run_migrations.py
"""
import glob
import os
import sys
import bcrypt
import mysql.connector
from mysql.connector import Error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from database import get_doctor_password_hash, set_doctor_password

DEFAULT_DOCTOR_PASSWORD = os.environ.get('DOCTOR_DEFAULT_PASSWORD', 'doctor123')
MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_conn():
    return mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
    )


def run_sql_file(path):
    """Execute every ';' terminated statement, stripping '--' comment lines."""
    with open(path, encoding='utf-8-sig') as f:
        sql = f.read()
    conn = get_conn()
    cursor = conn.cursor()
    executed, failed = 0, 0
    for raw in sql.split(';'):
        stmt = '\n'.join(
            line for line in raw.splitlines()
            if not line.strip().startswith('--')
        ).strip()
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            conn.commit()
            executed += 1
        except Error as e:
            conn.rollback()
            failed += 1
            print(f'  [FAIL] {e}')
    cursor.close()
    conn.close()
    return executed, failed


def seed_doctor_passwords():
    """Give every doctor without a password a default bcrypt hash."""
    updated = 0
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT doctor_id FROM doctors')
    doctors = cursor.fetchall()
    for doc in doctors:
        if not get_doctor_password_hash(doc['doctor_id']):
            pw_hash = bcrypt.hashpw(
                DEFAULT_DOCTOR_PASSWORD.encode('utf-8'), bcrypt.gensalt()
            ).decode('utf-8')
            set_doctor_password(doc['doctor_id'], pw_hash)
            updated += 1
    cursor.close()
    conn.close()
    return updated


def main():
    sql_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
    if not sql_files:
        print('No migration .sql files found.')
        return

    for path in sql_files:
        print(f'Applying {os.path.basename(path)} ...')
        done, failed = run_sql_file(path)
        print(f'  -> {done} statements executed, {failed} failed')

    updated = seed_doctor_passwords()
    print(f'Doctor passwords seeded/kept for {updated} doctor(s) '
          f'(default password: {DEFAULT_DOCTOR_PASSWORD})')
    print('Migration complete.')


if __name__ == '__main__':
    main()
