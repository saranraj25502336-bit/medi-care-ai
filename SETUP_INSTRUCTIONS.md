# 🏥 AI-Based Smart Hospital Management System

## Production Deployment Guide — AWS EC2 + Gunicorn + Nginx

---

## 📋 Overview

| Component | Technology |
|-----------|-----------|
| Backend | Python Flask 3.x |
| Database | MySQL 8.x |
| Face Recognition | OpenCV DNN (no dlib, no Haar) |
| AI Chatbot | Groq API / OpenRouter API |
| Notifications | Gmail SMTP + Fast2SMS |
| Web Server | Gunicorn + Nginx |
| Deployment | AWS EC2 (Ubuntu 26.04) |

---

## ✅ What Was Fixed / Modernized

### 1. OpenCV Issues Fixed
- **Removed** `cv2.CascadeClassifier` (deprecated Haar cascade)
- **Removed** `cv2.data.haarcascades` dependency
- **Replaced with** OpenCV DNN face detector (Caffe model)
- DNN models auto-download on first use (lazy initialization)
- Changed from `opencv-python` to `opencv-python-headless` for server use
- No GUI dependencies — works headless on EC2

### 2. Face Recognition Redesigned
- **Removed** `dlib` dependency (incompatible with Python 3.14)
- **Removed** `face_recognition` library (incompatible)
- **Removed** Haar Cascade (deprecated)
- **New approach**: OpenCV DNN detection + HSV histogram matching
- Face descriptors stored as JSON in MySQL
- No external ML models needed at runtime

### 3. Dependencies Modernized
- `requirements.txt` now has only 7 production packages
- All packages compatible with Python 3.12+
- No `dlib`, `face_recognition`, `mediapipe`, `scikit-learn`
- `opencv-python-headless` for server environments

### 4. Database Layer Improved
- Connection pooling via `mysql.connector.pooling`
- All queries use parameterized statements (SQL injection protection)
- Auto-creates database and tables on first run
- Auto-seeds 6 sample doctors
- Proper connection cleanup with `try/finally`

### 5. Configuration Secured
- All secrets moved to environment variables
- `config.py` reads from `os.environ` with sensible defaults
- Admin credentials overridable via `ADMIN_USERNAME`/`ADMIN_PASSWORD`
- Debug mode controlled by `FLASK_DEBUG` env var

### 6. Flask Security
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = 'Lax'`
- `SESSION_COOKIE_SECURE = True` in production
- Authentication decorators for admin/doctor/staff/patient
- Proper logout routes (separate for patient, doctor, admin)
- Input validation on all routes

### 7. Logging
- Structured logging with timestamps and levels
- Configurable via `LOG_LEVEL` env var
- All exceptions logged with traceback

---

## 🚀 AWS EC2 Deployment Steps

### Prerequisites
- AWS Account
- EC2 instance (Ubuntu 26.04 LTS, t2.medium or larger)
- MySQL 8.x (RDS or installed on EC2)
- Domain name (optional, for HTTPS)

### Step 1: Launch EC2 Instance

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv nginx mysql-server

# Clone the repository
git clone https://github.com/saranraj25502336-bit/hospital-system.git
cd hospital-system
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure MySQL

```bash
# Secure MySQL installation
sudo mysql_secure_installation

# Create database and user
sudo mysql -u root -p
```

```sql
CREATE DATABASE hospital_management;
CREATE USER 'hospital_user'@'localhost' IDENTIFIED BY 'your-strong-password';
GRANT ALL PRIVILEGES ON hospital_management.* TO 'hospital_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Step 4: Set Environment Variables

```bash
# Create .env file (DO NOT commit this to git)
cat > /home/ubuntu/hospital-system/.env << 'EOF'
SECRET_KEY=your-random-secret-key-here
FLASK_DEBUG=0
DB_HOST=localhost
DB_PORT=3306
DB_USER=hospital_user
DB_PASSWORD=your-strong-password
DB_NAME=hospital_management
LOG_LEVEL=INFO
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
GROQ_API_KEY=your-groq-api-key-optional
OPENROUTER_API_KEY=your-openrouter-api-key-optional
EMAIL_ENABLED=0
SMS_ENABLED=0
EOF

# Source the env file
set -a; source /home/ubuntu/hospital-system/.env; set +a
```

### Step 5: Configure Gunicorn Systemd Service

```bash
sudo nano /etc/systemd/system/hospital.service
```

```ini
[Unit]
Description=Smart Hospital Management System
After=network.target mysql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/hospital-system
EnvironmentFile=/home/ubuntu/hospital-system/.env
ExecStart=/home/ubuntu/hospital-system/venv/bin/gunicorn app:app \
    --bind 127.0.0.1:5000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile /var/log/hospital/access.log \
    --error-logfile /var/log/hospital/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/hospital
sudo chown ubuntu:ubuntu /var/log/hospital

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable hospital
sudo systemctl start hospital
sudo systemctl status hospital
```

### Step 6: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/hospital
```

```nginx
server {
    listen 80;
    server_name your-domain.com your-ec2-public-ip;

    client_max_body_size 16M;

    location /static/ {
        alias /home/ubuntu/hospital-system/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hospital /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Configure firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Step 7: (Optional) HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Step 8: Verify Deployment

```bash
# Check service status
sudo systemctl status hospital

# Check logs
tail -f /var/log/hospital/access.log
tail -f /var/log/hospital/error.log

# Test the application
curl http://localhost:5000/
curl http://your-domain.com/
```

---

## 🔧 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | `change-this-in-production` | Flask session secret |
| `FLASK_DEBUG` | No | `0` | Set to `1` for debug mode |
| `FLASK_HOST` | No | `0.0.0.0` | Bind address |
| `FLASK_PORT` | No | `5000` | Port number |
| `DB_HOST` | Yes | `localhost` | MySQL host |
| `DB_PORT` | No | `3306` | MySQL port |
| `DB_USER` | Yes | `root` | MySQL user |
| `DB_PASSWORD` | Yes | `` | MySQL password |
| `DB_NAME` | No | `hospital_management` | Database name |
| `DB_POOL_SIZE` | No | `5` | Connection pool size |
| `ADMIN_USERNAME` | No | `admin` | Admin panel username |
| `ADMIN_PASSWORD` | No | `admin123` | Admin panel password |
| `GROQ_API_KEY` | No | `` | Groq API key for AI chatbot |
| `OPENROUTER_API_KEY` | No | `` | OpenRouter fallback API key |
| `EMAIL_ENABLED` | No | `0` | Set to `1` to enable email |
| `EMAIL_ADDRESS` | No | `` | Gmail address for SMTP |
| `EMAIL_PASSWORD` | No | `` | Gmail app password |
| `SMS_ENABLED` | No | `0` | Set to `1` to enable SMS |
| `SMS_API_KEY` | No | `` | Fast2SMS API key |
| `SMS_SENDER_ID` | No | `HOSPMG` | SMS sender ID |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `FACE_TOLERANCE` | No | `0.6` | Face match tolerance |
| `CAMERA_INDEX` | No | `0` | Camera index for local use |

---

## 📁 Project Structure

```
hospital-system/
├── app.py                          # Main Flask application
├── config.py                       # Configuration (env vars)
├── database.py                     # Database layer (connection pool)
├── face_recognition_module.py      # Face recognition (OpenCV DNN)
├── chatbot.py                      # AI Medical Chatbot
├── notifications.py                # Email/SMS notifications
├── requirements.txt                # Production dependencies
├── Procfile                        # Gunicorn process file
├── render.yaml                     # Render deployment config
├── SETUP_INSTRUCTIONS.md           # This file
├── .gitignore
├── face_encodings/                 # DNN models (auto-downloaded)
├── static/
│   ├── css/                        # Stylesheets
│   ├── js/                         # JavaScript files
│   ├── images/                     # Images
│   └── uploads/                    # Uploaded files
├── templates/                      # HTML templates
│   ├── index.html
│   ├── register.html
│   ├── dashboard.html
│   ├── appointments.html
│   ├── doctor_dashboard.html
│   ├── doctor_patient.html
│   ├── find_patient.html
│   ├── admin_login.html
│   ├── admin_train.html
│   ├── 404.html
│   ├── 500.html
│   └── partials/                   # Reusable template parts
└── api/                            # PHP API (legacy)
    └── chat.php
```

---

## 🧪 Testing

```bash
# Test all imports
python -c "
from config import Config
from database import Database
from face_recognition_module import FaceRecognitionSystem
from chatbot import MedicalChatbot
from notifications import NotificationService
from app import app
print('All imports OK')
"

# Test Flask routes
python -c "
from app import app
with app.test_client() as c:
    assert c.get('/').status_code == 200
    assert c.get('/register').status_code == 200
    assert c.get('/admin-login').status_code == 200
    assert c.get('/doctor').status_code == 302  # redirect (unauthed)
    assert c.get('/find-patient').status_code == 302  # redirect (unauthed)
print('All routes OK')
"

# Start development server
python app.py
```

---

## 🔐 Default Credentials

| Role | Username/ID | Password |
|------|-------------|----------|
| Admin | `admin` | `admin123` (change via env vars) |
| Doctor | ID 1-6 | `doctor123` |
| Patient | Register via web | N/A |

---

## 📊 API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/` | Public | Home page |
| GET/POST | `/register` | Public | Patient registration |
| POST | `/face-login` | Public | Face recognition login |
| POST | `/manual-login` | Public | Manual patient login |
| GET | `/dashboard` | Patient | Patient dashboard |
| POST | `/doctor-login` | Public | Doctor login |
| GET | `/doctor` | Doctor | Doctor dashboard |
| GET | `/doctor/patient/<id>` | Doctor | View patient |
| POST | `/add-prescription` | Doctor | Add prescription |
| GET | `/appointments` | Patient | View appointments |
| POST | `/book-appointment` | Patient | Book appointment |
| POST | `/update-appointment-status` | Doctor | Approve/reject |
| POST | `/chatbot` | Public | Chatbot API |
| POST | `/get-selfcare-suggestions` | Public | Self-care tips |
| GET | `/find-patient` | Staff | Face scan page |
| POST | `/find-patient/scan` | Staff | Scan patient face |
| GET | `/admin-login` | Public | Admin login |
| GET | `/admin/train` | Admin | Train chatbot |
| GET | `/api/check-session` | Public | Session status |
| GET | `/api/patients` | Doctor | List patients |
| GET | `/api/doctors` | Public | List doctors |
| GET | `/api/records/<id>` | Doctor | Patient records |

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'cv2'"
```bash
pip install opencv-python-headless
```

### "Can't connect to MySQL"
```bash
# Check MySQL is running
sudo systemctl status mysql

# Verify credentials
mysql -u hospital_user -p -h localhost hospital_management
```

### "Face detection not working"
```bash
# Check if DNN models were downloaded
ls -la face_encodings/
# Should show: deploy.prototxt and res10_300x300_ssd_iter_140000_fp16.caffemodel
```

### "Gunicorn fails to start"
```bash
# Check logs
sudo journalctl -u hospital -n 50 --no-pager

# Verify environment file
sudo systemctl cat hospital
```

---

## 📝 License

MIT License — Free to use and modify.