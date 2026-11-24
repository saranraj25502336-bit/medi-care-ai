"""
Script to seed hospital information training data into the chatbot_training table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import add_training_data

hospital_info = [
    # Bed Availability
    {
        'keywords': 'bed availability, bed, available beds, hospital beds, ward, ICU bed',
        'question': 'Is there bed availability in the hospital?',
        'answer': '🏥 **Bed Availability at MediCare AI Hospital**\n\n• General Ward: 50+ beds available (₹1,500/day)\n• Semi-Private: 25 beds available (₹3,000/day)\n• Private Room: 15 beds available (₹5,000/day)\n• ICU Beds: 10 beds available (₹8,000/day)\n• NICU: 8 beds available\n• Emergency Beds: 20 beds available\n\nFor bed booking, please contact our admission desk at +91-1800-123-4567 or visit the front office.',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Ambulance
    {
        'keywords': 'ambulance, emergency vehicle, ambulance service, medical transport, 108',
        'question': 'What are your ambulance services?',
        'answer': '🚑 **Ambulance Services at MediCare AI**\n\n• Emergency Ambulance: 24/7 available - Call +91-1800-123-4567\n• ICU Ambulance: Fully equipped with ventilator support\n• Patient Transport: For non-emergency transfers\n• Charges: Free for emergency cases within 10km\n• Average Response Time: Under 15 minutes\n\nFor immediate ambulance dispatch, call our 24/7 helpline at +91-1800-123-4567.',
        'category': 'hospital',
        'urgency': 'high'
    },
    # Pharmacy
    {
        'keywords': 'pharmacy, medicine, drug, prescription, medical store, chemist',
        'question': 'Tell me about the pharmacy',
        'answer': '💊 **Pharmacy at MediCare AI**\n\n• Location: Ground Floor, Near Main Entrance\n• Timings: Open 24/7 (24 hours)\n• Services:\n  - All prescription medicines available\n  - Over-the-counter medicines\n  - Surgical supplies\n  - Ayurvedic and herbal products\n  - Baby care products\n• Home Delivery: Available for registered patients\n• Discount: 10% off for senior citizens\n• Insurance: All major insurance cards accepted\n• Contact: +91-1800-123-4568',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Visiting Hours
    {
        'keywords': 'visiting hours, visitor, visiting time, visiting, see patient, meet patient',
        'question': 'What are the hospital visiting hours?',
        'answer': '⏰ **Visiting Hours at MediCare AI**\n\n• General Wards: 5:00 PM - 7:00 PM (Daily)\n• Semi-Private Rooms: 4:00 PM - 7:00 PM (Daily)\n• Private Rooms: 3:00 PM - 8:00 PM (Flexible)\n• ICU: 30 minutes per visitor, 2 visitors at a time\n  - Morning: 10:00 AM - 11:00 AM\n  - Evening: 5:00 PM - 6:00 PM\n• NICU: Parents only, 24/7 access\n\n**Visitor Rules:**\n• Maximum 2 visitors per patient\n• Children under 12 not allowed in ICU/NICU\n• Please sanitize hands before entering\n• No outside food allowed in patient areas',
        'category': 'hospital',
        'urgency': 'low'
    },
    # OPD Timings
    {
        'keywords': 'OPD, outpatient, clinic timings, doctor timings, consultation hours, OPD timing',
        'question': 'What is the OPD timing?',
        'answer': '🕐 **OPD (Outpatient Department) Timings**\n\n**General OPD:**\n• Monday - Saturday: 9:00 AM - 5:00 PM\n• Sunday: 9:00 AM - 1:00 PM (Emergency only)\n\n**Specialist OPD:**\n• Cardiology: Mon/Wed/Fri - 10:00 AM - 2:00 PM\n• Neurology: Tue/Thu - 10:00 AM - 1:00 PM\n• Orthopedic: Mon-Sat - 11:00 AM - 3:00 PM\n• Pediatrics: Mon-Sat - 9:00 AM - 4:00 PM\n• Dermatology: Mon/Wed/Fri - 2:00 PM - 5:00 PM\n\n**Registration:** Opens at 8:00 AM\n**Emergency:** 24/7 - No appointment needed',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Blood Bank
    {
        'keywords': 'blood bank, blood, blood donation, blood group, blood test, blood availability',
        'question': 'Tell me about blood bank services',
        'answer': '🩸 **Blood Bank at MediCare AI**\n\n• Location: Basement Floor, Block B\n• Timings: 24/7 Emergency Service\n\n**Blood Inventory (Currently Available):**\n• A+ : Available\n• A- : Limited\n• B+ : Available\n• B- : Available\n• AB+ : Available\n• AB- : Limited\n• O+ : Available\n• O- : Scarce (Donors needed!)\n\n**Services:**\n• Blood donation camp every 1st Saturday\n• Free blood grouping\n• Cross-matching\n• Blood component separation\n\n**Donate Blood:**\n• Be a hero - donate blood! Call +91-1800-123-4569',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Billing & Insurance
    {
        'keywords': 'billing, bill, payment, insurance, cashless, claim, cost, charges, fees',
        'question': 'What are the billing and insurance options?',
        'answer': '💰 **Billing & Insurance at MediCare AI**\n\n**Payment Methods:**\n• Cash\n• Credit/Debit Cards (Visa, Mastercard, RuPay)\n• UPI (Google Pay, PhonePe, Paytm)\n• Net Banking\n• Digital Wallets\n\n**Insurance Partners:**\n• Star Health Insurance\n• ICICI Lombard\n• HDFC ERGO\n• New India Assurance\n• United India Insurance\n• Acko General Insurance\n\n**Cashless Treatment:**\n• Pre-authorization required for cashless\n• Submit insurance card at admission desk\n• 50+ insurance companies empanelled\n\n**Billing Counter:** Ground Floor, Open 7:00 AM - 9:00 PM',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Lab Services
    {
        'keywords': 'lab, lab services, diagnostic, test, x-ray, MRI, CT scan, blood test, pathology',
        'question': 'What are the lab and diagnostic services?',
        'answer': '🔬 **Lab & Diagnostic Services at MediCare AI**\n\n**Pathology Lab:**\n• Blood tests: CBC, Blood Sugar, Lipid Profile, etc.\n• Urine tests\n• Thyroid tests\n• Liver & Kidney function tests\n• COVID-19 testing\n\n**Radiology:**\n• X-Ray (Digital)\n• MRI Scan (1.5T & 3T)\n• CT Scan (128 slice)\n• Ultrasound / Sonography\n• Mammography\n• Bone Density Test\n\n**Timing:**\n• Lab: 7:00 AM - 8:00 PM (Daily)\n• Emergency lab: 24/7\n\n**Reports:** Digital copies available within 2 hours for routine tests.',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Emergency
    {
        'keywords': 'emergency, emergency services, urgent, emergency care, accident, trauma',
        'question': 'Do you have emergency services?',
        'answer': '🚨 **Emergency Services at MediCare AI - 24/7**\n\n**Emergency Department:**\n• Open 24 hours a day, 365 days a year\n• No appointment needed - walk in anytime\n\n**Services:**\n• Trauma Care\n• Cardiac Emergency\n• Stroke Management\n• Poisoning Treatment\n• Accident & Injury Care\n• Obstetric Emergencies\n• Pediatric Emergencies\n\n**Emergency Contact:**\n📞 +91-1800-123-4567\n📱 Emergency Helpline: 108\n\n**Average Response Time:** Under 10 minutes\n**Ambulance:** Free pickup within 10km radius',
        'category': 'hospital',
        'urgency': 'high'
    },
    # Address & Contact
    {
        'keywords': 'address, location, contact, map, reach, how to reach, hospital address',
        'question': 'What is the hospital address and contact?',
        'answer': '📍 **MediCare AI Hospital - Contact Information**\n\n**Address:**\n123 Healthcare Avenue, Medical District,\nNew Delhi - 110001\n\n**Phone Numbers:**\n• Emergency: +91-1800-123-4567\n• Appointment Booking: +91-1800-123-4566\n• Pharmacy: +91-1800-123-4568\n• Blood Bank: +91-1800-123-4569\n• Ambulance: 108\n\n**Email:** info@medicareai.com\n\n**How to Reach:**\n• Nearest Metro: Central Hospital Station (500m)\n• Nearest Bus Stop: Medical College Stop\n• Parking: Free parking available for 200+ cars\n\n**Landmarks:** Near Central Mall, Opposite City Park',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Health Checkup Packages
    {
        'keywords': 'health checkup, checkup package, health package, full body checkup, medical checkup',
        'question': 'Tell me about health checkup packages',
        'answer': '📋 **Health Checkup Packages at MediCare AI**\n\n**Basic Package - ₹999**\n• Complete Blood Count (CBC)\n• Blood Sugar (Fasting)\n• Urine Analysis\n• BMI Check\n• Doctor Consultation\n\n**Gold Package - ₹2,499**\n• All Basic tests +\n• Lipid Profile\n• Liver Function Test\n• Kidney Function Test\n• Thyroid (TSH)\n• Chest X-Ray\n• ECG\n\n**Platinum Package - ₹5,999**\n• All Gold tests +\n• Stress Test (TMT)\n• Echocardiography\n• Ultrasound Abdomen\n• Vitamin D & B12\n• Dental Checkup\n• Eye Checkup\n\n**Book Now:** Call +91-1800-123-4566 or visit the hospital',
        'category': 'hospital',
        'urgency': 'low'
    },
    # Appointment
    {
        'keywords': 'appointment, book appointment, schedule, doctor appointment, consultation',
        'question': 'I need to book an appointment',
        'answer': '📅 **Book an Appointment at MediCare AI**\n\n**Ways to Book:**\n1. 📞 Call: +91-1800-123-4566\n2. 🌐 Online: www.medicareai.com/book\n3. 📱 Mobile App: MediCare AI (Google Play)\n4. 🏥 Walk-in: Registration counter (Ground Floor)\n\n**Appointment Slots:**\n• Morning: 9:00 AM - 12:00 PM\n• Afternoon: 12:00 PM - 3:00 PM\n• Evening: 3:00 PM - 5:00 PM\n\n**Documents Needed:**\n• Previous medical records (if any)\n• Insurance card (if applicable)\n• Government ID (Aadhaar/DL/Passport)\n\n**Register on our website first to book online!**',
        'category': 'hospital',
        'urgency': 'moderate'
    },
]

print("Adding hospital information training data...")
count = 0
for item in hospital_info:
    try:
        add_training_data(
            keywords=item['keywords'],
            answer=item['answer'],
            question=item['question'],
            category=item['category'],
            urgency=item['urgency']
        )
        count += 1
        print(f"  [OK] Added: {item['question'][:40]}...")
    except Exception as e:
        print(f"  [ERR] Error adding {item['question'][:30]}: {e}")

print(f"\n[OK] Successfully added {count} hospital information training items!")
print("Restart the Flask app to see the changes take effect.")
