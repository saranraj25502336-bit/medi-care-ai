# -*- coding: utf-8 -*-
"""Real-time event bus (polling-based; SocketIO-grade without extra workers).

Front-end pages poll `/api/realtime/events?after=<seq>` every few seconds.
Optionally, if Flask-SocketIO is installed it can be wired later.
"""
import itertools
import time
from collections import deque

_buffer = deque(maxlen=500)
_seq = itertools.count(1)


def emit(event_type, data=None, department_id=None):
    sid = next(_seq)
    _buffer.append({
        'seq': sid,
        'event_type': event_type,
        'data': data or {},
        'department_id': department_id,
        'ts': time.time(),
    })
    return sid


def events_since(after=0, department_id=None):
    out = []
    for item in _buffer:
        if item['seq'] <= after:
            continue
        if department_id is not None and item.get('department_id') is not None \
                and item.get('department_id') != department_id:
            continue
        out.append(item)
    return out
