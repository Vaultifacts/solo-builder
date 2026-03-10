"""Request body validators for Solo Builder API (TASK-327 / SE-030 to SE-035).

Provides a single reusable helper used by POST endpoints to enforce:
  - Content-Type / JSON parseability
  - Required field presence
  - Type safety (required string fields must be strings)
  - Maximum field length (prevents oversized payloads from reaching business logic)

Usage
-----
    from .validators import require_string_fields

    @bp.post("/add_task")
    def add_task():
        err = require_string_fields(("spec",))
        if err:
            return err
        data = request.get_json(force=True, silent=True) or {}
        spec = data["spec"].strip()
        ...
"""
from __future__ import annotations

from typing import Sequence

from flask import jsonify, request

MAX_FIELD_LEN = 4096  # characters; protects against oversized payloads


def require_string_fields(
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> tuple | None:
    """Validate the JSON request body against a set of required string fields.

    Parameters
    ----------
    required:
        Field names that must be present and non-empty strings.
    optional:
        Field names that, if present, must also be strings.

    Returns
    -------
    A Flask ``(response, status_code)`` tuple on validation failure, or
    ``None`` when the body is valid.
    """
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "reason": "Request body must be a JSON object."}), 400

    for field in required:
        val = data.get(field)
        if val is None:
            return jsonify({"ok": False, "reason": f"Missing required field '{field}'."}), 400
        if not isinstance(val, str):
            return jsonify({"ok": False, "reason": f"Field '{field}' must be a string."}), 400
        if len(val) > MAX_FIELD_LEN:
            return jsonify({"ok": False,
                            "reason": f"Field '{field}' exceeds maximum length of {MAX_FIELD_LEN}."}), 400
        if not val.strip():
            return jsonify({"ok": False, "reason": f"Field '{field}' must not be blank."}), 400

    for field in optional:
        val = data.get(field)
        if val is not None:
            if not isinstance(val, str):
                return jsonify({"ok": False, "reason": f"Field '{field}' must be a string."}), 400
            if len(val) > MAX_FIELD_LEN:
                return jsonify({"ok": False,
                                "reason": f"Field '{field}' exceeds maximum length of {MAX_FIELD_LEN}."}), 400

    return None
