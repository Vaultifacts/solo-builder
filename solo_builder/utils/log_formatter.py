"""JSON log formatter for machine-readable Solo Builder log output (TASK-326 / OM-011).

Usage
-----
    from solo_builder.utils.log_formatter import JsonLogFormatter

    handler.setFormatter(JsonLogFormatter())

Output format (one JSON object per line)::

    {"ts": "2026-03-10T04:00:00", "level": "INFO", "logger": "solo_builder",
     "msg": "sdk_dispatch step=10 jobs=['A1']", "step": 10, "jobs": ["A1"]}

Fields
------
ts          ISO-8601 UTC timestamp (seconds precision)
level       Log level name (DEBUG / INFO / WARNING / ERROR / CRITICAL)
logger      Logger name
msg         Formatted log message
exc         Exception traceback string (only present if an exception was logged)
"""
from __future__ import annotations

import json
import logging
import traceback


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()
        return json.dumps(entry, ensure_ascii=False)
