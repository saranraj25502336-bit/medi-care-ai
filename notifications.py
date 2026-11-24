# ============================================
# NOTIFICATIONS MODULE
# Handles Email and SMS notifications
# ============================================

import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
from database import save_notification, get_patient_by_id

class NotificationService:
    """Service for sending notifications via Email and SMS"""
    
    def __init__(self):
        self.email_enabled = Config.EMAIL_ENABLED
        self.sms_enabled = Config.SMS_ENABLED
    
    def send_appointment_confirmation(self, patient_id, appointment_data):
        """Send notification when appointment is booked"""
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        
        message = f"""
        Dear {patient['name']},
        
        Your appointment has been successfully booked!
        
        Details:
        - Doctor: {appointment_data.get('doctor_name', 'N/A')}
        - Date: {appointment_data.get('appointment_date', 'N/A')}
        - Time: {appointment_data.get('appointment_time', 'N/A')}
        - Status: Pending Approval
        
        You will receive a notification once your appointment is confirmed.
        
        Thank you for choosing our hospital.
        
        Regards,
        Hospital Management System
        """
        
        # Send email
        if self.email_enabled and patient.get('email'):
            self._send_email(
                patient['email'],
                'Appointment Booked Successfully',
                message
            )
        
        # Send SMS
        if self.sms_enabled and patient.get('phone'):
            sms_message = f"Appointment booked with Dr. {appointment_data.get('doctor_name', 'N/A')} on {appointment_data.get('appointment_date', 'N/A')} at {appointment_data.get('appointment_time', 'N/A')}. Status: Pending."
            self._send_sms(patient['phone'], sms_message)
        
        # Save notification log
        save_notification(
            patient_id,
            'appointment_booked',
            message.strip(),
            'email' if self.email_enabled else 'sms'
        )
        
        return True
    
    def send_appointment_status_update(self, appointment):
        """Send notification when appointment status changes"""
        patient = get_patient_by_id(appointment['patient_id'])
        if not patient:
            return False
        
        status = appointment['status'].upper()
        
        if status == 'APPROVED':
            message = f"""
            Dear {patient['name']},
            
            Great news! Your appointment has been APPROVED!
            
            Details:
            - Doctor: {appointment.get('doctor_name', 'N/A')}
            - Date: {appointment.get('appointment_date', 'N/A')}
            - Time: {appointment.get('appointment_time', 'N/A')}
            
            Please arrive 15 minutes before your scheduled time.
            
            Regards,
            Hospital Management System
            """
        elif status == 'REJECTED':
            message = f"""
            Dear {patient['name']},
            
            We regret to inform you that your appointment has been REJECTED.
            
            Details:
            - Doctor: {appointment.get('doctor_name', 'N/A')}
            - Date: {appointment.get('appointment_date', 'N/A')}
            - Time: {appointment.get('appointment_time', 'N/A')}
            
            Please book a new appointment with a different date/time.
            
            Regards,
            Hospital Management System
            """
        else:
            return False
        
        # Send email
        if self.email_enabled and patient.get('email'):
            self._send_email(
                patient['email'],
                f'Appointment {status}',
                message
            )
        
        # Send SMS
        if self.sms_enabled and patient.get('phone'):
            sms_message = f"Your appointment with Dr. {appointment.get('doctor_name', 'N/A')} on {appointment.get('appointment_date', 'N/A')} has been {status}."
            self._send_sms(patient['phone'], sms_message)
        
        # Save notification log
        save_notification(
            appointment['patient_id'],
            f'appointment_{appointment["status"]}',
            message.strip(),
            'email' if self.email_enabled else 'sms'
        )
        
        return True
    
    def send_prescription_notification(self, patient_id, prescription_data):
        """Send notification when prescription is added"""
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        
        message = f"""
        Dear {patient['name']},
        
        Your doctor has added a new prescription for you.
        
        Prescription Details:
        - Doctor: {prescription_data.get('doctor_name', 'N/A')}
        - Diagnosis: {prescription_data.get('diagnosis', 'N/A')}
        - Prescription: {prescription_data.get('prescription', 'N/A')}
        
        Please follow the prescribed medication as directed.
        If you experience any side effects, contact your doctor immediately.
        
        Regards,
        Hospital Management System
        """
        
        # Send email
        if self.email_enabled and patient.get('email'):
            self._send_email(
                patient['email'],
                'New Prescription Added',
                message
            )
        
        # Send SMS
        if self.sms_enabled and patient.get('phone'):
            sms_message = f"New prescription added by Dr. {prescription_data.get('doctor_name', 'N/A')}. Check your patient portal for details."
            self._send_sms(patient['phone'], sms_message)
        
        # Save notification log
        save_notification(
            patient_id,
            'prescription_added',
            message.strip(),
            'email' if self.email_enabled else 'sms'
        )
        
        return True
    
    def _send_email(self, to_email, subject, body):
        """Send email using Gmail SMTP"""
        if not self.email_enabled:
            print("Email service is disabled. Enable it in config.py")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_ADDRESS
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to Gmail SMTP server
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def _send_sms(self, phone_number, message):
        """Send SMS using Fast2SMS API"""
        if not self.sms_enabled:
            print("SMS service is disabled. Enable it in config.py")
            return False
        
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            
            payload = {
                'sender_id': Config.SMS_SENDER_ID,
                'message': message,
                'language': 'english',
                'route': 'v3',
                'numbers': phone_number
            }
            
            headers = {
                'authorization': Config.SMS_API_KEY,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            
            if response.status_code == 200:
                print(f"SMS sent successfully to {phone_number}")
                return True
            else:
                print(f"Error sending SMS: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False
    
    # ------------------------------------------------------------------
    # Smart check-in & queue notifications (writes delivery logs)
    # ------------------------------------------------------------------
    def _deliver(self, patient, ntype, subject, message, sms_message):
        try:
            from database import log_notification_delivery
        except Exception:
            log_notification_delivery = None
        channel = 'none'
        if self.email_enabled and patient.get('email'):
            try:
                self._send_email(patient['email'], subject, message)
                channel = 'email'
            except Exception as e:
                print(f'Email notify error: {e}')
        if self.sms_enabled and patient.get('phone'):
            try:
                self._send_sms(patient['phone'], sms_message)
                channel = channel if channel != 'none' else 'sms'
            except Exception as e:
                print(f'SMS notify error: {e}')
        save_notification(patient['patient_id'], ntype, message.strip(), channel)
        if log_notification_delivery:
            try:
                log_notification_delivery(ntype, 'patient', patient['patient_id'],
                                          channel, 'sent')
            except Exception:
                pass
        return channel != 'none'

    def send_checkin_notification(self, patient_id, data):
        """Check-in confirmation with department + token."""
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        message = (f"Dear {patient['name']},\n\nYou have been checked in successfully.\n\n"
                   f"- Department: {data.get('department', 'N/A')}\n"
                   f"- Token: {data.get('token_code', 'N/A')}\n"
                   f"- Queue: {data.get('queue_category', 'regular')}\n"
                   f"- Estimated wait: {data.get('est_wait_min', 0)} minutes "
                   f"(approximate)\n\nPlease watch the display screens for your turn.\n"
                   f"Regards,\nHospital Management System")
        sms = (f"Check-in OK. Dept: {data.get('department', '')}, "
               f"Token: {data.get('token_code', '')}. "
               f"Est wait {data.get('est_wait_min', 0)} min (approx).")
        return self._deliver(patient, 'checkin_confirmed',
                             'Check-in Confirmation', message, sms)

    def send_patient_called_notification(self, patient_id, token_code):
        """Notify patient that their token is being called."""
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        message = (f"Dear {patient['name']},\n\nYour turn has arrived. "
                   f"Token {token_code} is now being called. "
                   f"Please report to the doctor immediately.\nRegards,\nHospital")
        sms = f"Your turn now! Token {token_code} is being called. Please proceed."
        return self._deliver(patient, 'token_called',
                             'Your Turn - Token Called', message, sms)

    def send_followup_reminder(self, patient_id, followup):
        """Remind patient about an upcoming follow-up visit."""
        patient = get_patient_by_id(patient_id)
        if not patient:
            return False
        message = (f"Dear {patient['name']},\n\nThis is a reminder for your follow-up "
                   f"visit on {followup.get('followup_date', 'N/A')} with Dr. "
                   f"{followup.get('doctor_name', 'N/A')}.\nRegards,\nHospital")
        sms = (f"Follow-up reminder: {followup.get('followup_date', 'N/A')} with "
               f"Dr. {followup.get('doctor_name', 'N/A')}.")
        return self._deliver(patient, 'followup_reminder',
                             'Follow-up Reminder', message, sms)

    def send_test_email(self):
        """Send a test email to verify configuration"""
        if not self.email_enabled:
            return "Email is not enabled. Set EMAIL_ENABLED = True in config.py"
        
        try:
            msg = MIMEText("This is a test email from the Hospital Management System.")
            msg['Subject'] = 'Test Email - Hospital Management System'
            msg['From'] = Config.EMAIL_ADDRESS
            msg['To'] = Config.EMAIL_ADDRESS
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            return "Test email sent successfully!"
        except Exception as e:
            return f"Error: {str(e)}"