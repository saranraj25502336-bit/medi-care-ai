# -*- coding: utf-8 -*-
"""Part B: doctor-only patient access control."""
import io

P = r'c:\xampp\htdocs\project\app.py'
with io.open(P, encoding='utf-8') as f:
    src = f.read()

steps = []
def rep(old, new, label):
    steps.append([old, new, label])

# H) doctor dashboard: only the logged-in doctor's patients/records/appointments
rep("""@app.route('/doctor')
@doctor_login_required
def doctor_dashboard():
    \"\"\"Doctor dashboard.\"\"\"
    doctors = get_all_doctors()
    patients = get_all_patients()
    records = get_all_medical_records()
    appointments = get_all_appointments()

    return render_template('doctor_dashboard.html',
                           doctors=doctors,
                           patients=patients,
                           records=records,
                           appointments=appointments)""",
"""@app.route('/doctor')
@doctor_login_required
def doctor_dashboard():
    \"\"\"Doctor dashboard - shows ONLY the logged-in doctor's own patients.\"\"\"
    doctor_id = session['doctor_id']
    my_patients = get_doctor_patients(doctor_id)
    my_ids = [p['patient_id'] for p in my_patients]
    records = get_records_for_patients(my_ids)
    appointments = get_doctor_appointments(doctor_id)
    my_doctor = get_doctor_by_id(doctor_id)

    return render_template('doctor_dashboard.html',
                           doctors=[my_doctor] if my_doctor else [],
                           patients=my_patients,
                           records=records,
                           appointments=appointments)""", 'doctor_dashboard')

# I) doctor patient view: authorize
rep("""@app.route('/doctor/patient/<int:patient_id>')
@doctor_login_required
def doctor_patient_view(patient_id):
    \"\"\"Doctor view specific patient.\"\"\"
    patient = get_patient_by_id(patient_id)
    if not patient:
        return redirect(url_for('doctor_dashboard'))
    records = get_patient_medical_records(patient_id)
    return render_template('doctor_patient.html',
                           patient=patient,
                           records=records)""",
"""@app.route('/doctor/patient/<int:patient_id>')
@doctor_login_required
def doctor_patient_view(patient_id):
    \"\"\"Doctor view specific patient - only patients assigned to this doctor.\"\"\"
    doctor_id = session['doctor_id']
    if not doctor_can_access_patient(doctor_id, patient_id):
        return jsonify({'success': False, 'message': 'Access denied. This patient is not assigned to you.'}), 403
    patient = get_patient_by_id(patient_id)
    if not patient:
        return redirect(url_for('doctor_dashboard'))
    records = get_patient_medical_records(patient_id)
    return render_template('doctor_patient.html',
                           patient=patient,
                           records=records)""", 'doctor_patient_view')

# J) api patients
rep("""@app.route('/api/patients')
@doctor_login_required
def api_patients():
    \"\"\"Get all patients (doctor only).\"\"\"
    return jsonify(get_all_patients())""",
"""@app.route('/api/patients')
@doctor_login_required
def api_patients():
    \"\"\"Get the logged-in doctor's patients only.\"\"\"
    return jsonify(get_doctor_patients(session['doctor_id']))""", 'api_patients')

# K) api records: authorize
rep("""@app.route('/api/records/<int:patient_id>')
@doctor_login_required
def api_records(patient_id):
    \"\"\"Get patient records (doctor only).\"\"\"
    return jsonify(get_patient_medical_records(patient_id))""",
"""@app.route('/api/records/<int:patient_id>')
@doctor_login_required
def api_records(patient_id):
    \"\"\"Get patient records - only patients assigned to the logged-in doctor.\"\"\"
    doctor_id = session['doctor_id']
    if not doctor_can_access_patient(doctor_id, patient_id):
        return jsonify({'success': False, 'message': 'Access denied. This patient is not assigned to you.'}), 403
    return jsonify(get_patient_medical_records(patient_id))""", 'api_records')

# L) api patient details: staff/doctor branch authorization
rep("""    is_owner = session.get('patient_id') == patient_id
    is_staff = session.get('doctor_id') or session.get('admin_logged_in')
    if not (is_owner or is_staff):
        return jsonify({'success': False, 'message': 'Unauthorized. Please login.'}), 403""",
"""    is_owner = session.get('patient_id') == patient_id
    doctor_id = session.get('doctor_id')
    is_admin = bool(session.get('admin_logged_in'))
    is_staff = bool(doctor_id or is_admin)
    if doctor_id and not is_admin:
        if not doctor_can_access_patient(doctor_id, patient_id):
            return jsonify({'success': False, 'message': 'Access denied. This patient is not assigned to you.'}), 403
    if not (is_owner or is_staff):
        return jsonify({'success': False, 'message': 'Unauthorized. Please login.'}), 403""", 'api_patient_details')

# M) add prescription: force identity from session + access check + store doctor_id
rep("""@app.route('/add-prescription', methods=['POST'])
@doctor_login_required
def add_prescription():
    \"\"\"Add a prescription.\"\"\"
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        symptoms = data.get('symptoms', '')
        diagnosis = data.get('diagnosis', '')
        prescription = data.get('prescription', '')
        doctor_name = data.get('doctor_name', 'Dr. Unknown')
        doctor_notes = data.get('doctor_notes', '')

        if not patient_id:
            return jsonify({'success': False, 'message': 'Patient ID is required'})

        record_id = add_medical_record(patient_id, symptoms, diagnosis, prescription, doctor_name, doctor_notes)
        if not record_id:
            return jsonify({'success': False, 'message': 'Failed to add prescription'})""",
"""@app.route('/add-prescription', methods=['POST'])
@doctor_login_required
def add_prescription():
    \"\"\"Add a prescription (identity is taken from the session, never the client).\"\"\"
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        symptoms = data.get('symptoms', '')
        diagnosis = data.get('diagnosis', '')
        prescription = data.get('prescription', '')
        doctor_notes = data.get('doctor_notes', '')

        if not patient_id:
            return jsonify({'success': False, 'message': 'Patient ID is required'})

        doctor_id = session['doctor_id']
        doctor = get_doctor_by_id(doctor_id) or {}
        doctor_name = doctor.get('name') or 'Dr. Unknown'

        # Only this doctor's own patients (appointment / check-in routed to their department / record)
        from modules.checkin_service import doctor_can_treat_patient
        if not doctor_can_treat_patient(doctor_id, patient_id):
            return jsonify({'success': False,
                            'message': 'Access denied. This patient is not assigned to you.'}), 403

        record_id = add_medical_record(patient_id, symptoms, diagnosis, prescription, doctor_name,
                                       doctor_notes, doctor_id=doctor_id)
        if not record_id:
            return jsonify({'success': False, 'message': 'Failed to add prescription'})""", 'add_prescription')

# N) doctor update patient: authorize
rep("""        if not all([patient_id, name, age, phone, email]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        if update_patient(patient_id, name, int(age), phone, email):""",
"""        if not all([patient_id, name, age, phone, email]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        if not doctor_can_access_patient(session['doctor_id'], patient_id):
            return jsonify({'success': False, 'message': 'Access denied. This patient is not assigned to you.'}), 403

        if update_patient(patient_id, name, int(age), phone, email):""", 'doctor_update_patient')

status = []
for old, new, label in steps:
    n = src.count(old)
    if n != 1:
        status.append(f'[FAIL] {label}: anchor found {n} times')
        continue
    src = src.replace(old, new, 1)
    status.append(f'[OK]   {label}')

with io.open(P, 'w', encoding='utf-8', newline='') as f:
    f.write(src)
print('\n'.join(status))
print('all_ok=', all(s.startswith('[OK]') for s in status))
