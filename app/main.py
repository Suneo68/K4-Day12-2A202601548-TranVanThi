"""Chat service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /chat:

    client ──► verify_bearer_token ──► token bucket ──► cost guard
                                                            │
                                    store.history ◄─────────┘
                                          │
                                   generate_reply
                                          │
                              store.add_turn × 2 ──► guard.record ──► emit
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from utils.mock_llm import generate_reply

from .auth import verify_bearer_token
from .config import get_settings
from .cost_guard import CostGuard
from .lifecycle import shutdown_guard
from .logging_utils import emit
from .rate_limiter import TokenBucket
from .store import ChatStore, get_redis_client

SERVICE_NAME = "day12-chat-service"
SERVICE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ChatStore:
    return ChatStore(get_redis_client())


@lru_cache(maxsize=1)
def get_bucket() -> TokenBucket:
    settings = get_settings()
    return TokenBucket(
        get_redis_client(),
        capacity=settings.bucket_capacity,
        refill_per_minute=settings.refill_per_minute,
    )


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().daily_budget_usd)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    shutdown_guard.arm()
    emit("service_started", service=SERVICE_NAME, version=SERVICE_VERSION)
    yield
    emit("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Chat Service", version=SERVICE_VERSION, lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# ─────────────────────────────────────────────────────────────
# Health & readiness
# ─────────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    """Liveness probe — process còn sống không?

    - Đang tắt dần (shutdown_guard.draining) → 503 {"status": "draining"}
    - Bình thường → 200 {"status": "ok", "service": ..., "version": ...}

    Endpoint này KHÔNG gọi Redis, không query DB — chỉ trả lời
    "có cần restart container này không?". Nếu nó phụ thuộc Redis,
    Redis chết một nhịp là cả cụm container bị restart theo.
    """
    if shutdown_guard.draining:
        return JSONResponse(status_code=503, content={"status": "draining"})
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/readyz")
def readyz(store: ChatStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    - Đang tắt dần → 503 {"status": "draining"}
    - store.ping() False → 503 {"status": "not ready", "redis": False}
    - Ngược lại → 200 {"status": "ready", "redis": True}

    Khác /healthz ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency.
    Load balancer dùng nó để quyết định có đẩy request vào instance này không.
    503 ở đây → LB ngừng gửi traffic, KHÔNG restart container.
    """
    if shutdown_guard.draining:
        return JSONResponse(status_code=503, content={"status": "draining"})
    if not store.ping():
        err = getattr(store, "last_error", None)
        content = {"status": "not ready", "redis": False}
        if err:
            content["error"] = err
        return JSONResponse(
            status_code=503,
            content=content,
        )
    return {"status": "ready", "redis": True}


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/chat")
def chat(
    payload: ChatRequest,
    client_id: str = Depends(verify_bearer_token),
    store: ChatStore = Depends(get_store),
    bucket: TokenBucket = Depends(get_bucket),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Gửi một tin nhắn tới service.

    Thứ tự xử lý (quan trọng — chặn TRƯỚC khi gọi LLM):
      1. bucket.consume()  → 429 nếu gọi quá nhanh
      2. guard.check()     → 402 nếu hết ngân sách ngày
      3. Lấy lịch sử
      4. Gọi LLM (mock)
      5. Ghi lịch sử × 2
      6. Ghi chi phí
      7. Log
      8. Trả response

    client_id do verify_bearer_token trả về, nên request không có
    token hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    # 1. Rate limit — chặn trước khi tốn tiền
    bucket.consume(client_id)

    # 2. Cost guard — chặn trước khi tốn tiền
    guard.check(client_id)

    # 3. Lấy lịch sử hội thoại
    history = store.history(client_id)

    # 4. Gọi mock LLM
    result = generate_reply(payload.message, history)

    # 5. Ghi lịch sử (user + assistant)
    store.add_turn(client_id, "user", payload.message)
    store.add_turn(client_id, "assistant", result["text"])

    # 6. Ghi chi phí
    guard.record(client_id, result["usd_cost"])

    # 7. Log structured JSON
    emit(
        "chat_completed",
        client_id=client_id,
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        usd_cost=result["usd_cost"],
    )

    # 8. Trả response
    return {
        "reply": result["text"],
        "client_id": client_id,
        "turns_before": len(history),
        "usd_cost": result["usd_cost"],
        "usage": {
            "prompt": result["prompt_tokens"],
            "completion": result["completion_tokens"],
        },
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
