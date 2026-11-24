# DEPLOYMENT GUIDE

## Local (XAMPP)
1. `mysql -u root < database.sql`
2. `python migrations/run_migrations.py`
3. `pip install -r requirements.txt`
4. Copy `.env.example` → `.env`, fill secrets
5. `python app.py` → http://localhost:5000

## Production (Linux / Gunicorn / Nginx)
```bash
# python 3.12+
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# database
mysql -u root < database.sql
python migrations/run_migrations.py

# env
cp .env.example .env   # edit SECRET_KEY, DB_*, GROQ_API_KEY, ADMIN_*, DOCTOR defaults

# run
gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

Nginx reverse proxy (force HTTPS + security headers):
```nginx
server {
  listen 80; server_name hospital.example.com;
  return 301 https://$host$request_uri;
}
server {
  listen 443 ssl http2; server_name hospital.example.com;
  ssl_certificate /etc/letsencrypt/live/hospital.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/hospital.example.com/privkey.pem;
  client_max_body_size 8M;

  location / { proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Real-IP $remote_addr; }
}
```
- FLASK_DEBUG=0 sets `SESSION_COOKIE_SECURE=True` automatically.
- Use `--preload` only if you initialize heavy InsightFace models once.
- Real-time events use the built-in polling bus (`/api/realtime/events`); no extra worker required.

## Storage / backups
- Back up MySQL daily: `mysqldump -u root --single-transaction hospital_management | gzip > bk_$(date +%F).sql.gz`
- Back up `face_encodings/` and `static/uploads/` (biometric templates — encrypt them).
- Retention: keep backups per hospital policy; disable `ON DELETE CASCADE` reliance for audit history.

## Hardware
- Face enrollment/recognition needs a camera (kiosk). Camera index via `CAMERA_INDEX` env.
- QR display/scanning: patient phone + reception webcam; no extra hardware.
- SMS/email require Fast2SMS + SMTP credentials (optional).
