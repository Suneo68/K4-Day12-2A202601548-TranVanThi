"""CP1 — Structured logging.

`print("client abc hỏi gì đó")` là log cho người đọc. Cloud (Railway, Render,
Cloud Run, Datadog...) đọc log bằng máy: một dòng = một JSON object thì mới
lọc/đếm/cảnh báo được. Đây là khác biệt lớn giữa localhost và production.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """CHO SẴN — thời điểm hiện tại theo ISO-8601, múi giờ UTC."""
    return datetime.now(timezone.utc).isoformat()


def emit(event: str, severity: str = "INFO", **fields) -> str:
    """Ghi một dòng log JSON ra stdout.

    Tạo dict gồm tối thiểu 3 khóa:
        - "event"    : tên sự kiện
        - "severity" : mức log, VIẾT HOA — Google Cloud Logging hiểu khóa này
        - "ts"       : UTC ISO-8601
    rồi gộp thêm mọi cặp key/value trong ``**fields``.

    In chuỗi JSON đó ra stdout trên một dòng duy nhất
    (``json.dumps(..., ensure_ascii=False)``, không dùng ``indent``) và
    trả về chính chuỗi đó.

    Ví dụ:
        >>> emit("chat_completed", client_id="sv01", usd_cost=0.0001)
        '{"event": "chat_completed", "severity": "INFO", "ts": "...", ...}'
    """
    record = {
        "event": event,
        "severity": severity.upper(),
        "ts": utc_now_iso(),
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    return line
