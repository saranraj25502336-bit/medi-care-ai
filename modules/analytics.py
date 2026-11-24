# -*- coding: utf-8 -*-
"""Live analytics - every number is computed from real database rows."""
from datetime import date, timedelta
from database import Database


def _one(query, params=None):
    db = Database()
    row = db.fetch_one(query, params or ())
    return row['c'] if row else 0


def summary():
    today = date.today().isoformat()
    return {
        'total_patients': _one('SELECT COUNT(*) AS c FROM patients'),
        'today_appointments': _one(
            "SELECT COUNT(*) AS c FROM appointments WHERE appointment_date = %s", (today,)),
        'today_checkins': _one(
            "SELECT COUNT(*) AS c FROM checkins WHERE DATE(checkin_time) = CURRENT_DATE()"),
        'waiting_patients': _one(
            "SELECT COUNT(*) AS c FROM queue_tokens WHERE status = 'waiting' "
            "AND DATE(created_at) = CURRENT_DATE()"),
        'completed_consultations': _one(
            "SELECT COUNT(*) AS c FROM queue_tokens WHERE status = 'completed' "
            "AND DATE(created_at) = CURRENT_DATE()"),
        'walkins_today': _one(
            "SELECT COUNT(*) AS c FROM queue_tokens WHERE queue_category = 'walkin' "
            "AND DATE(created_at) = CURRENT_DATE()"),
        'active_doctors': _one("SELECT COUNT(*) AS c FROM doctors WHERE is_active = 1"),
        'cancelled_today': _one(
            "SELECT COUNT(*) AS c FROM appointments WHERE status = 'cancelled' "
            "AND appointment_date = %s", (today,)),
    }


def department_workload():
    db = Database()
    rows = db.fetch_all(
        "SELECT dep.department_id, dep.name, dep.capacity_per_day, "
        "COUNT(DISTINCT qt.token_id) AS today_tokens, "
        "SUM(CASE WHEN qt.status = 'waiting' THEN 1 ELSE 0 END) AS waiting, "
        "SUM(CASE WHEN qt.status = 'completed' THEN 1 ELSE 0 END) AS completed "
        "FROM departments dep "
        "LEFT JOIN queue_tokens qt ON qt.department_id = dep.department_id "
        "AND DATE(qt.created_at) = CURRENT_DATE() "
        "GROUP BY dep.department_id, dep.name, dep.capacity_per_day "
        "ORDER BY dep.name"
    )
    for r in rows or []:
        r['today_tokens'] = int(r['today_tokens'] or 0)
        r['waiting'] = int(r['waiting'] or 0)
        r['completed'] = int(r['completed'] or 0)
        r['load_pct'] = round(r['today_tokens'] / max(1, r['capacity_per_day']) * 100, 1)
    return rows


def checks_over_days(days=7):
    db = Database()
    rows = db.fetch_all(
        "SELECT DATE(checkin_time) AS d, COUNT(*) AS c FROM checkins "
        "WHERE checkin_time >= DATE_SUB(CURRENT_DATE(), INTERVAL %s DAY) "
        "GROUP BY DATE(checkin_time) ORDER BY d",
        (days,),
    )
    out = []
    for r in rows or []:
        out.append({'date': str(r['d']), 'count': int(r['c'])})
    return out


def appointments_over_days(days=7):
    db = Database()
    rows = db.fetch_all(
        "SELECT appointment_date AS d, COUNT(*) AS c FROM appointments "
        "WHERE appointment_date >= DATE_SUB(CURRENT_DATE(), INTERVAL %s DAY) "
        "GROUP BY appointment_date ORDER BY d",
        (days,),
    )
    out = []
    for r in rows or []:
        out.append({'date': str(r['d']), 'count': int(r['c'])})
    return out


def call_stats(days=7):
    db = Database()
    row = db.fetch_one(
        "SELECT AVG(TIMESTAMPDIFF(MINUTE, created_at, called_at)) AS avg_call_wait, "
        "AVG(TIMESTAMPDIFF(MINUTE, called_at, completed_at)) AS avg_consult_min "
        "FROM queue_tokens "
        "WHERE called_at IS NOT NULL AND created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL %s DAY)",
        (days,),
    )
    return {
        'avg_call_wait_min': round(float(row['avg_call_wait'] or 0), 1) if row else 0,
        'avg_consult_min': round(float(row['avg_consult_min'] or 0), 1) if row else 0,
    }
