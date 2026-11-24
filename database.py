# ============================================
# DATABASE LAYER
# MySQL with connection pooling & parameterized queries
# Production-ready
# ============================================

import mysql.connector
from mysql.connector import pooling, Error
from config import Config
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (singleton)
# ---------------------------------------------------------------------------
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name='hospital_pool',
                pool_size=Config.DB_POOL_SIZE,
                pool_reset_session=True,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME
            )
            logger.info('Database pool created (size=%d)', Config.DB_POOL_SIZE)
        except Error:
            # Database may not exist yet – connect without it, create DB
            try:
                conn = mysql.connector.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
                cursor.execute(f"USE {Config.DB_NAME}")
                conn.commit()
                cursor.close()
                conn.close()
                _pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name='hospital_pool',
                    pool_size=Config.DB_POOL_SIZE,
                    pool_reset_session=True,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME
                )
                logger.info('Database created and pool initialized')
            except Error as e:
                logger.error('Database initialization failed: %s', e)
                raise
    return _pool


class Database:
    """Lightweight database wrapper using connection pool."""

    def __init__(self):
        self.connection = None
        self._ensure_schema()

    def _get_connection(self):
        pool = _get_pool()
        self.connection = pool.get_connection()
        return self.connection

    def _ensure_schema(self):
        """Create tables on first use if they don't exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            self._create_tables(cursor)
            conn.commit()
            cursor.close()
        except Error as e:
            logger.error('Schema creation: %s', e)
        finally:
            if self.connection:
                self.connection.close()

    @staticmethod
    def _get_connection_from_cursor(cursor):
        """Get connection from cursor (compatible with mysql-connector-python 8.x and 9.x)."""
        if hasattr(cursor, '_connection'):
            return cursor._connection
        return cursor.connection

    @staticmethod
    def _create_tables(cursor):
        """Create all required tables if they don't exist."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                age INT NOT NULL,
                phone VARCHAR(15) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) DEFAULT NULL,
                face_encoding LONGTEXT DEFAULT NULL,
                face_image VARCHAR(255) DEFAULT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                specialization VARCHAR(100) NOT NULL,
                email VARCHAR(100) DEFAULT NULL,
                phone VARCHAR(15) DEFAULT NULL,
                available_days VARCHAR(255) DEFAULT 'Monday,Tuesday,Wednesday,Thursday,Friday',
                available_time VARCHAR(50) DEFAULT '09:00-17:00'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_records (
                record_id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                symptoms TEXT DEFAULT NULL,
                diagnosis TEXT DEFAULT NULL,
                prescription TEXT DEFAULT NULL,
                doctor_name VARCHAR(100) NOT NULL,
                doctor_notes TEXT DEFAULT NULL,
                visit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                doctor_id INT NOT NULL,
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                symptoms TEXT DEFAULT NULL,
                status ENUM('pending','approved','rejected','completed') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_training (
                id INT AUTO_INCREMENT PRIMARY KEY,
                keywords TEXT NOT NULL,
                question TEXT DEFAULT NULL,
                answer TEXT NOT NULL,
                category VARCHAR(50) DEFAULT 'general',
                urgency VARCHAR(20) DEFAULT 'low',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                type VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                sent_via VARCHAR(20) DEFAULT 'email',
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
            )
        """)

        # Seed doctors if table empty
        cursor.execute("SELECT COUNT(*) FROM doctors")
        if cursor.fetchone()[0] == 0:
            sample_doctors = [
                ('Dr. Rajesh Sharma', 'Cardiologist', 'rajesh.sharma@hospital.com', '9876543210'),
                ('Dr. Priya Patel', 'Neurologist', 'priya.patel@hospital.com', '9876543211'),
                ('Dr. Amit Verma', 'Orthopedic Surgeon', 'amit.verma@hospital.com', '9876543212'),
                ('Dr. Sunita Reddy', 'Pediatrician', 'sunita.reddy@hospital.com', '9876543213'),
                ('Dr. Vikram Singh', 'General Physician', 'vikram.singh@hospital.com', '9876543214'),
                ('Dr. Ananya Gupta', 'Dermatologist', 'ananya.gupta@hospital.com', '9876543215'),
            ]
            cursor.executemany(
                "INSERT INTO doctors (name, specialization, email, phone) VALUES (%s, %s, %s, %s)",
                sample_doctors
            )
            logger.info('Seed doctors inserted')
        conn = Database._get_connection_from_cursor(cursor)
        conn.commit()

    def execute_query(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE, return lastrowid or None."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid
        except Error as e:
            logger.error('Query error: %s', e)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def fetch_one(self, query, params=None):
        """Fetch single row as dict."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchone()
        except Error as e:
            logger.error('Fetch error: %s', e)
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def fetch_all(self, query, params=None):
        """Fetch all rows as list of dicts."""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchall()
        except Error as e:
            logger.error('Fetch error: %s', e)
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def close(self):
        """No-op: connections are returned to pool automatically."""


# ============================================================================
# CRUD HELPERS
# ============================================================================

def register_patient(name, age, phone, email, face_encoding=None, face_image=None):
    db = Database()
    q = """INSERT INTO patients (name, age, phone, email, face_encoding, face_image)
           VALUES (%s, %s, %s, %s, %s, %s)"""
    return db.execute_query(q, (name, age, phone, email, face_encoding, face_image))


def get_patient_by_id(patient_id):
    db = Database()
    return db.fetch_one("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))


def get_patient_by_email(email):
    db = Database()
    return db.fetch_one("SELECT * FROM patients WHERE email = %s", (email,))


def get_all_patients():
    db = Database()
    return db.fetch_all(
        "SELECT patient_id, name, age, phone, email, registration_date FROM patients ORDER BY name"
    )


def update_face_encoding(patient_id, face_encoding, face_image):
    db = Database()
    return db.execute_query(
        "UPDATE patients SET face_encoding = %s, face_image = %s WHERE patient_id = %s",
        (face_encoding, face_image, patient_id)
    )


def update_patient(patient_id, name, age, phone, email):
    db = Database()
    return db.execute_query(
        "UPDATE patients SET name = %s, age = %s, phone = %s, email = %s WHERE patient_id = %s",
        (name, age, phone, email, patient_id)
    )


def delete_patient(patient_id):
    db = Database()
    return db.execute_query("DELETE FROM patients WHERE patient_id = %s", (patient_id,))


def add_doctor(name, specialization, email=None, phone=None,
               available_days='Monday,Tuesday,Wednesday,Thursday,Friday',
               available_time='09:00-17:00'):
    db = Database()
    q = """INSERT INTO doctors (name, specialization, email, phone, available_days, available_time)
           VALUES (%s, %s, %s, %s, %s, %s)"""
    return db.execute_query(q, (name, specialization, email, phone, available_days, available_time))


def get_all_doctors():
    db = Database()
    return db.fetch_all("SELECT * FROM doctors ORDER BY name")


def get_doctor_by_id(doctor_id):
    db = Database()
    return db.fetch_one("SELECT * FROM doctors WHERE doctor_id = %s", (doctor_id,))


def add_medical_record(patient_id, symptoms, diagnosis, prescription, doctor_name, doctor_notes=''):
    db = Database()
    q = """INSERT INTO medical_records (patient_id, symptoms, diagnosis, prescription, doctor_name, doctor_notes)
           VALUES (%s, %s, %s, %s, %s, %s)"""
    return db.execute_query(q, (patient_id, symptoms, diagnosis, prescription, doctor_name, doctor_notes))


def _convert_datetime(data):
    for item in data:
        for key in ('visit_date', 'registration_date', 'created_at', 'sent_date'):
            val = item.get(key)
            if val and not isinstance(val, str) and hasattr(val, 'strftime'):
                item[key] = val.strftime('%Y-%m-%d %H:%M:%S')
    return data


def get_patient_medical_records(patient_id):
    db = Database()
    rows = db.fetch_all(
        "SELECT * FROM medical_records WHERE patient_id = %s ORDER BY visit_date DESC",
        (patient_id,)
    )
    return _convert_datetime(rows)


def get_all_medical_records():
    db = Database()
    rows = db.fetch_all("""
        SELECT mr.*, p.name as patient_name, p.age as patient_age
        FROM medical_records mr
        JOIN patients p ON mr.patient_id = p.patient_id
        ORDER BY mr.visit_date DESC
    """)
    return _convert_datetime(rows)


def book_appointment(patient_id, doctor_id, appointment_date, appointment_time, symptoms=''):
    db = Database()
    q = """INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, symptoms)
           VALUES (%s, %s, %s, %s, %s)"""
    return db.execute_query(q, (patient_id, doctor_id, appointment_date, appointment_time, symptoms))


def _convert_timedelta(data):
    for item in data:
        t = item.get('appointment_time')
        if t and not isinstance(t, str) and hasattr(t, 'seconds'):
            total = t.seconds
            item['appointment_time'] = f"{total // 3600:02d}:{(total % 3600) // 60:02d}:00"
        d = item.get('appointment_date')
        if d and not isinstance(d, str) and hasattr(d, 'strftime'):
            item['appointment_date'] = d.strftime('%Y-%m-%d')
    return data


def get_patient_appointments(patient_id):
    db = Database()
    rows = db.fetch_all("""
        SELECT a.*, d.name as doctor_name, d.specialization
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (patient_id,))
    return _convert_timedelta(rows)


def get_all_appointments():
    db = Database()
    rows = db.fetch_all("""
        SELECT a.*, p.name as patient_name, p.phone as patient_phone,
               p.email as patient_email, d.name as doctor_name, d.specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN doctors d ON a.doctor_id = d.doctor_id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """)
    return _convert_timedelta(rows)


def update_appointment_status(appointment_id, status):
    db = Database()
    return db.execute_query(
        "UPDATE appointments SET status = %s WHERE appointment_id = %s",
        (status, appointment_id)
    )


def get_appointment_by_id(appointment_id):
    db = Database()
    return db.fetch_one("""
        SELECT a.*, p.name as patient_name, p.email as patient_email,
               p.phone as patient_phone, d.name as doctor_name, d.specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.appointment_id = %s
    """, (appointment_id,))


def save_notification(patient_id, ntype, message, sent_via='email'):
    db = Database()
    q = "INSERT INTO notifications (patient_id, type, message, sent_via) VALUES (%s, %s, %s, %s)"
    return db.execute_query(q, (patient_id, ntype, message, sent_via))


def get_all_face_encodings():
    db = Database()
    return db.fetch_all(
        "SELECT patient_id, name, face_encoding FROM patients WHERE face_encoding IS NOT NULL"
    )


def get_patient_by_face_encoding(face_encoding_str):
    db = Database()
    return db.fetch_one(
        "SELECT * FROM patients WHERE face_encoding = %s", (face_encoding_str,)
    )


def add_training_data(keywords, answer, question=None, category='general', urgency='low'):
    db = Database()
    q = """INSERT INTO chatbot_training (keywords, question, answer, category, urgency)
           VALUES (%s, %s, %s, %s, %s)"""
    return db.execute_query(q, (keywords, question, answer, category, urgency))


def get_all_training_data():
    db = Database()
    return db.fetch_all("SELECT * FROM chatbot_training ORDER BY id DESC")


def get_training_by_id(training_id):
    db = Database()
    return db.fetch_one("SELECT * FROM chatbot_training WHERE id = %s", (training_id,))


def update_training_data(training_id, keywords, answer, question=None, category='general', urgency='low'):
    db = Database()
    q = """UPDATE chatbot_training
           SET keywords=%s, question=%s, answer=%s, category=%s, urgency=%s
           WHERE id=%s"""
    return db.execute_query(q, (keywords, question, answer, category, urgency, training_id))


def delete_training_data(training_id):
    db = Database()
    return db.execute_query("DELETE FROM chatbot_training WHERE id = %s", (training_id,))


def get_patient_password_hash(patient_id):
    """Fetch the stored bcrypt password hash for a patient."""
    db = Database()
    row = db.fetch_one(
        "SELECT password FROM patients WHERE patient_id = %s", (patient_id,)
    )
    return row['password'] if row else None


def set_patient_password(patient_id, hashed_password):
    """Store a bcrypt password hash for a patient."""
    db = Database()
    return db.execute_query(
        "UPDATE patients SET password = %s WHERE patient_id = %s",
        (hashed_password, patient_id)
    )

def get_doctor_password_hash(doctor_id):
    """Fetch the stored bcrypt password hash for a doctor."""
    db = Database()
    row = db.fetch_one(
        "SELECT password FROM doctors WHERE doctor_id = %s", (doctor_id,)
    )
    return row['password'] if row else None


def set_doctor_password(doctor_id, hashed_password):
    """Store a bcrypt password hash for a doctor."""
    db = Database()
    return db.execute_query(
        "UPDATE doctors SET password = %s WHERE doctor_id = %s",
        (hashed_password, doctor_id)
    )

# ============================================================================
# SMART CHECK-IN / ROUTING DATA LAYER (migration 001/002 tables)
# ============================================================================

# ---------------------------------------------------------------- departments
def get_all_departments(active_only=False):
    db = Database()
    q = "SELECT * FROM departments"
    if active_only:
        q += " WHERE is_active = 1"
    return db.fetch_all(q + " ORDER BY name")


def get_department_by_id(department_id):
    db = Database()
    return db.fetch_one("SELECT * FROM departments WHERE department_id = %s", (department_id,))


def get_default_department_id():
    db = Database()
    row = db.fetch_one(
        "SELECT department_id FROM departments WHERE name = 'General Medicine' AND is_active = 1 "
        "ORDER BY department_id LIMIT 1"
    )
    if row:
        return row['department_id']
    row = db.fetch_one("SELECT department_id FROM departments WHERE is_active = 1 ORDER BY department_id LIMIT 1")
    return row['department_id'] if row else None


def add_department(name, description='', operating_hours='09:00-18:00', capacity_per_day=50):
    db = Database()
    return db.execute_query(
        "INSERT INTO departments (name, description, operating_hours, capacity_per_day) "
        "VALUES (%s, %s, %s, %s)",
        (name, description, operating_hours, capacity_per_day),
    )


def update_department(department_id, name, description, operating_hours, capacity_per_day, is_active):
    db = Database()
    return db.execute_query(
        "UPDATE departments SET name=%s, description=%s, operating_hours=%s, "
        "capacity_per_day=%s, is_active=%s WHERE department_id=%s",
        (name, description, operating_hours, capacity_per_day, int(is_active), department_id),
    )


def set_department_status(department_id, is_active):
    db = Database()
    return db.execute_query(
        "UPDATE departments SET is_active = %s WHERE department_id = %s",
        (int(is_active), department_id),
    )


def assign_doctor_to_department(doctor_id, department_id):
    db = Database()
    return db.execute_query(
        "INSERT IGNORE INTO doctor_departments (doctor_id, department_id) VALUES (%s, %s)",
        (doctor_id, department_id),
    )


def remove_doctor_from_department(doctor_id, department_id):
    db = Database()
    return db.execute_query(
        "DELETE FROM doctor_departments WHERE doctor_id = %s AND department_id = %s",
        (doctor_id, department_id),
    )


def get_doctors_for_department(department_id):
    db = Database()
    return db.fetch_all(
        "SELECT d.doctor_id, d.name, d.specialization, d.email, d.phone, d.is_active "
        "FROM doctors d JOIN doctor_departments dd ON d.doctor_id = dd.doctor_id "
        "WHERE dd.department_id = %s ORDER BY d.name",
        (department_id,),
    )


def get_departments_for_doctor(doctor_id):
    db = Database()
    return db.fetch_all(
        "SELECT dep.* FROM departments dep "
        "JOIN doctor_departments dd ON dep.department_id = dd.department_id "
        "WHERE dd.doctor_id = %s AND dep.is_active = 1 ORDER BY dep.name",
        (doctor_id,),
    )


def get_doctor_department_for_doctor(doctor_id):
    db = Database()
    return db.fetch_one(
        "SELECT dep.* FROM departments dep "
        "JOIN doctor_departments dd ON dep.department_id = dd.department_id "
        "WHERE dd.doctor_id = %s ORDER BY dep.department_id LIMIT 1",
        (doctor_id,),
    )


def is_department_available(department_id):
    """Returns dict: {available, capacity_per_day, today_count}."""
    db = Database()
    dept = get_department_by_id(department_id)
    if not dept or dept.get('is_active') != 1:
        return {'available': False, 'capacity_per_day': 0, 'today_count': 0}
    # real count of today's check-ins routed to this department
    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM checkins "
        "WHERE assigned_department_id = %s AND DATE(checkin_time) = CURRENT_DATE()",
        (department_id,),
    )
    today = row['c'] if row else 0
    return {
        'available': today < int(dept.get('capacity_per_day') or 50),
        'capacity_per_day': dept.get('capacity_per_day') or 50,
        'today_count': today,
    }

# ------------------------------------------------------------- appointments
def update_appointment_status_with_reason(appointment_id, status, rejection_reason=None):
    db = Database()
    if rejection_reason:
        return db.execute_query(
            "UPDATE appointments SET status = %s, rejection_reason = %s WHERE appointment_id = %s",
            (status, rejection_reason, appointment_id),
        )
    return db.execute_query(
        "UPDATE appointments SET status = %s WHERE appointment_id = %s",
        (status, appointment_id),
    )


def check_appointment_conflict(doctor_id, appointment_date, appointment_time):
    db = Database()
    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM appointments "
        "WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s "
        "AND status IN ('pending','approved')",
        (doctor_id, appointment_date, appointment_time),
    )
    return row['c'] if row else 0


def get_appointments_for_date(appointment_date):
    db = Database()
    rows = db.fetch_all(
        "SELECT a.*, p.name AS patient_name, p.phone AS patient_phone, "
        "d.name AS doctor_name, d.specialization "
        "FROM appointments a "
        "JOIN patients p ON a.patient_id = p.patient_id "
        "JOIN doctors d ON a.doctor_id = d.doctor_id "
        "WHERE a.appointment_date = %s "
        "ORDER BY a.appointment_time ASC",
        (appointment_date,),
    )
    return _convert_timedelta(rows)


# ----------------------------------------------------------------- checkins
def create_checkin(patient_id, appointment_id, method, clinical_priority='normal'):
    db = Database()
    return db.execute_query(
        "INSERT INTO checkins (patient_id, appointment_id, checkin_method, "
        "verification_status, checkin_status, clinical_priority) "
        "VALUES (%s, %s, %s, 'verified', 'checked_in', %s)",
        (patient_id, appointment_id, method, clinical_priority),
    )


def update_checkin_token(checkin_id, token_code):
    db = Database()
    return db.execute_query(
        "UPDATE checkins SET token_code = %s WHERE checkin_id = %s",
        (token_code, checkin_id),
    )


def update_checkin_status(checkin_id, status):
    db = Database()
    return db.execute_query(
        "UPDATE checkins SET checkin_status = %s WHERE checkin_id = %s",
        (status, checkin_id),
    )


def get_active_checkin(patient_id):
    """Active = created today and not completed/cancelled."""
    db = Database()
    return db.fetch_one(
        "SELECT * FROM checkins WHERE patient_id = %s AND DATE(checkin_time) = CURRENT_DATE() "
        "AND checkin_status NOT IN ('completed','cancelled') "
        "ORDER BY checkin_id DESC LIMIT 1",
        (patient_id,),
    )


def get_active_checkin_by_id(checkin_id):
    db = Database()
    return db.fetch_one("SELECT * FROM checkins WHERE checkin_id = %s", (checkin_id,))


def get_checkins_today():
    db = Database()
    rows = db.fetch_all(
        "SELECT ci.*, p.name AS patient_name, p.phone AS patient_phone, "
        "dep.name AS department_name "
        "FROM checkins ci "
        "LEFT JOIN patients p ON ci.patient_id = p.patient_id "
        "LEFT JOIN departments dep ON ci.assigned_department_id = dep.department_id "
        "WHERE DATE(ci.checkin_time) = CURRENT_DATE() "
        "ORDER BY ci.checkin_id DESC LIMIT 30"
    )
    return _convert_datetime(rows)


def get_recent_checkins(limit=20):
    db = Database()
    rows = db.fetch_all(
        "SELECT ci.*, p.name AS patient_name, dep.name AS department_name "
        "FROM checkins ci "
        "LEFT JOIN patients p ON ci.patient_id = p.patient_id "
        "LEFT JOIN departments dep ON ci.assigned_department_id = dep.department_id "
        "ORDER BY ci.checkin_id DESC LIMIT %s",
        (limit,),
    )
    return _convert_datetime(rows)


# ------------------------------------------------------------------ routing
def get_routing_rules(active_only=True):
    db = Database()
    q = "SELECT * FROM routing_rules"
    if active_only:
        q += " WHERE is_active = 1"
    return db.fetch_all(q + " ORDER BY priority ASC, rule_id ASC")


def set_rule_status(rule_id, is_active):
    db = Database()
    return db.execute_query(
        "UPDATE routing_rules SET is_active = %s WHERE rule_id = %s",
        (int(is_active), rule_id),
    )


def create_routing_log(patient_id, appointment_id, rule_id, department_id,
                       queue_category, reason, recorded_by=None):
    db = Database()
    return db.execute_query(
        "INSERT INTO routing_logs (patient_id, appointment_id, rule_id, "
        "assigned_department_id, queue_category, decision_reason, recorded_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (patient_id, appointment_id, rule_id, department_id, queue_category, reason, recorded_by),
    )


def get_today_routing_logs(limit=30):
    db = Database()
    rows = db.fetch_all(
        "SELECT rl.*, p.name AS patient_name, dep.name AS department_name "
        "FROM routing_logs rl "
        "LEFT JOIN patients p ON rl.patient_id = p.patient_id "
        "LEFT JOIN departments dep ON rl.assigned_department_id = dep.department_id "
        "WHERE DATE(rl.created_at) = CURRENT_DATE() "
        "ORDER BY rl.routing_id DESC LIMIT %s",
        (limit,),
    )
    return _convert_datetime(rows)

# ---------------------------------------------------------------- queue
def create_queue_token(token_code, patient_id, department_id, doc_id,
                       checkin_id, category, est_wait=None):
    db = Database()
    return db.execute_query(
        "INSERT INTO queue_tokens (token_code, patient_id, department_id, doctor_id, "
        "checkin_id, queue_category, est_wait_min) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (token_code, patient_id, department_id, doc_id, checkin_id, category, est_wait),
    )


def get_token_by_code(token_code):
    db = Database()
    return db.fetch_one("SELECT * FROM queue_tokens WHERE token_code = %s", (token_code,))


def get_active_token_for_patient(patient_id):
    db = Database()
    return db.fetch_one(
        "SELECT qt.*, dep.name AS department_name "
        "FROM queue_tokens qt "
        "LEFT JOIN departments dep ON qt.department_id = dep.department_id "
        "WHERE qt.patient_id = %s AND qt.status IN ('waiting','called','consulting') "
        "ORDER BY qt.token_id DESC LIMIT 1",
        (patient_id,),
    )


def get_active_tokens_for_department(department_id):
    db = Database()
    rows = db.fetch_all(
        "SELECT qt.*, p.name AS patient_name, dt.name AS doctor_name "
        "FROM queue_tokens qt "
        "LEFT JOIN patients p ON qt.patient_id = p.patient_id "
        "LEFT JOIN doctors dt ON qt.doctor_id = dt.doctor_id "
        "WHERE qt.department_id = %s AND qt.status IN ('waiting','called','consulting') "
        "ORDER BY qt.created_at ASC",
        (department_id,),
    )
    return _convert_datetime(rows)


def get_queue_count_before(department_id):
    """Count tokens issued today for this department (for next sequence number)."""
    db = Database()
    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM queue_tokens "
        "WHERE department_id = %s AND DATE(created_at) = CURRENT_DATE()",
        (department_id,),
    )
    return row['c'] if row else 0


def update_token_status(token_id, status, note=None):
    db = Database()
    upd = "UPDATE queue_tokens SET status = %s"
    params = [status]
    if status == 'called':
        upd += ", called_at = NOW()"
    if status == 'consulting':
        upd += ", called_at = COALESCE(called_at, NOW())"
    if status == 'completed':
        upd += ", completed_at = NOW()"
    upd += " WHERE token_id = %s"
    params.append(token_id)
    done = db.execute_query(upd, tuple(params))
    if note:
        create_queue_event_row(token_id, status, note)
    return done


def create_queue_event_row(token_id, event_type, note=None):
    db = Database()
    return db.execute_query(
        "INSERT INTO queue_events (token_id, event_type, note) VALUES (%s, %s, %s)",
        (token_id, event_type, note),
    )


def get_queue_history(department_id, limit=30):
    db = Database()
    rows = db.fetch_all(
        "SELECT qt.token_code, qt.patient_id, p.name AS patient_name, "
        "qt.queue_category, qt.status, qt.created_at, qt.called_at, qt.completed_at "
        "FROM queue_tokens qt "
        "LEFT JOIN patients p ON qt.patient_id = p.patient_id "
        "WHERE qt.department_id = %s "
        "ORDER BY qt.token_id DESC LIMIT %s",
        (department_id, limit),
    )
    return _convert_datetime(rows)


def get_department_queue_stats(department_id):
    db = Database()
    rows = db.fetch_all(
        "SELECT status, COUNT(*) AS c FROM queue_tokens "
        "WHERE department_id = %s AND DATE(created_at) = CURRENT_DATE() GROUP BY status",
        (department_id,),
    )
    stats = {'waiting': 0, 'called': 0, 'consulting': 0, 'completed': 0, 'skipped': 0, 'cancelled': 0}
    for row in rows or []:
        stats[row['status']] = row['c']
    return stats


# -------------------------------------------------------------------- QR
def create_qr_token(appointment_id, token_hash, expires_at):
    db = Database()
    return db.execute_query(
        "INSERT INTO appointment_qr_tokens (appointment_id, token_hash, expires_at) "
        "VALUES (%s, %s, %s)",
        (appointment_id, token_hash, expires_at),
    )


def get_qr_by_hash(token_hash):
    db = Database()
    return db.fetch_one(
        "SELECT * FROM appointment_qr_tokens WHERE token_hash = %s", (token_hash,)
    )


def get_qrs_for_appointment(appointment_id):
    db = Database()
    return db.fetch_all(
        "SELECT * FROM appointment_qr_tokens WHERE appointment_id = %s "
        "ORDER BY qr_id DESC LIMIT 5",
        (appointment_id,),
    )


def mark_qr_used(qr_id):
    db = Database()
    return db.execute_query(
        "UPDATE appointment_qr_tokens SET used_at = NOW() WHERE qr_id = %s AND used_at IS NULL",
        (qr_id,),
    )


def revoke_qr_tokens_for_appointment(appointment_id):
    db = Database()
    return db.execute_query(
        "UPDATE appointment_qr_tokens SET is_revoked = 1 WHERE appointment_id = %s",
        (appointment_id,),
    )


# --------------------------------------------------------------- followups
def create_followup(patient_id, appointment_id, department_id, doc_id,
                    followup_date, followup_time=None, instructions=''):
    db = Database()
    return db.execute_query(
        "INSERT INTO patient_followups (patient_id, appointment_id, department_id, "
        "doctor_id, followup_date, followup_time, instructions) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (patient_id, appointment_id, department_id, doc_id, followup_date, followup_time, instructions),
    )


def get_followups_for_patient(patient_id):
    db = Database()
    rows = db.fetch_all(
        "SELECT pf.*, dep.name AS department_name, dt.name AS doctor_name "
        "FROM patient_followups pf "
        "LEFT JOIN departments dep ON pf.department_id = dep.department_id "
        "LEFT JOIN doctors dt ON pf.doctor_id = dt.doctor_id "
        "WHERE pf.patient_id = %s ORDER BY pf.followup_date DESC",
        (patient_id,),
    )
    return _convert_datetime(rows)


def mark_followup_status(followup_id, status):
    db = Database()
    return db.execute_query(
        "UPDATE patient_followups SET status = %s WHERE followup_id = %s",
        (status, followup_id),
    )


# ------------------------------------------------------------------- audit
def log_audit_row(user_type, user_id, action, entity_type=None, entity_id=None,
                  details=None, ip_address=''):
    db = Database()
    return db.execute_query(
        "INSERT INTO audit_logs (user_type, user_id, action, entity_type, "
        "entity_id, details, ip_address) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (user_type, user_id, action, entity_type, entity_id, details, ip_address),
    )


def get_audit_logs(limit=100):
    db = Database()
    rows = db.fetch_all(
        "SELECT * FROM audit_logs ORDER BY audit_id DESC LIMIT %s", (limit,)
    )
    return _convert_datetime(rows)


# ------------------------------------------------------- notification logs
def log_notification_delivery(notification_type, recipient_type, recipient_id,
                              channel, status='pending', error_message=None):
    db = Database()
    return db.execute_query(
        "INSERT INTO notification_delivery_logs (notification_type, recipient_type, "
        "recipient_id, channel, status, error_message) VALUES (%s, %s, %s, %s, %s, %s)",
        (notification_type, recipient_type, recipient_id, channel, status, error_message),
    )


def get_notification_delivery_logs(limit=50):
    db = Database()
    rows = db.fetch_all(
        "SELECT * FROM notification_delivery_logs ORDER BY log_id DESC LIMIT %s",
        (limit,),
    )
    return _convert_datetime(rows)

# ------------------------------------------------------------------ access
def get_doctor_patient_ids(doctor_id):
    """Distinct patients connected to a doctor (appointments / follow-ups / records)."""
    db = Database()
    rows = db.fetch_all(
        "SELECT patient_id FROM appointments WHERE doctor_id = %s "
        "UNION SELECT patient_id FROM patient_followups WHERE doctor_id = %s "
        "UNION SELECT patient_id FROM medical_records WHERE doctor_id = %s ",
        (doctor_id, doctor_id, doctor_id),
    )
    return sorted({r['patient_id'] for r in (rows or [])})


def get_doctor_patients(doctor_id):
    """Full patient rows for a doctor's own patients."""
    ids = get_doctor_patient_ids(doctor_id)
    if not ids:
        return []
    ph = ','.join(['%s'] * len(ids))
    db = Database()
    rows = db.fetch_all(
        f"SELECT * FROM patients WHERE patient_id IN ({ph}) ORDER BY name", tuple(ids)
    )
    return rows


def doctor_can_access_patient(doctor_id, patient_id):
    return patient_id in get_doctor_patient_ids(doctor_id)


def get_doctor_records(doctor_id):
    """Medical records authored by the doctor (doctor_id or legacy doctor_name)."""
    db = Database()
    doc = db.fetch_one("SELECT name FROM doctors WHERE doctor_id = %s", (doctor_id,))
    name = (doc or {}).get('name') or ''
    rows = db.fetch_all(
        "SELECT * FROM medical_records WHERE doctor_id = %s OR doctor_name = %s "
        "ORDER BY visit_date DESC",
        (doctor_id, name),
    )
    return _convert_datetime(rows)


def get_doctor_appointments(doctor_id):
    db = Database()
    rows = db.fetch_all(
        "SELECT a.*, p.name AS patient_name, p.phone AS patient_phone "
        "FROM appointments a JOIN patients p ON a.patient_id = p.patient_id "
        "WHERE a.doctor_id = %s ORDER BY a.appointment_date DESC, a.appointment_time DESC",
        (doctor_id,),
    )
    return _convert_timedelta(rows)


def get_records_for_patients(patient_ids):
    if not patient_ids:
        return []
    ph = ','.join(['%s'] * len(patient_ids))
    db = Database()
    rows = db.fetch_all(
        f"SELECT * FROM medical_records WHERE patient_id IN ({ph}) "
        "ORDER BY visit_date DESC",
        tuple(patient_ids),
    )
    return _convert_datetime(rows)
