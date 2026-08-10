# ═══════════════════════════════════════════════════════════════════
# CP2 — Containerization (production-ready)
#
# Multi-stage build: stage builder cài dependency, stage runtime
# chỉ copy kết quả → image nhỏ hơn (~300MB so với ~1.8GB bản đầy đủ).
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ────────────────────────────────────────────────
# Stage này được phép nặng (cài compiler, build tools) vì nó bị bỏ đi sau.
FROM python:3.11-slim AS builder

WORKDIR /build

# COPY requirements.txt TRƯỚC source code — Docker cache theo layer.
# Sửa một dòng code không phải cài lại thư viện (layer pip install được cache).
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ────────────────────────────────────────────────
# Chỉ copy KẾT QUẢ từ builder sang — không mang theo compiler, pip, cache.
FROM python:3.11-slim AS runtime

# Copy thư viện đã cài ở stage builder
COPY --from=builder /install /usr/local

# Tạo user thường — container chạy root biến mọi lỗ hổng thành root trên host
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Copy source code — SAU khi pip install để tận dụng Docker cache
COPY app ./app
COPY utils ./utils

# Chuyển sang user thường
USER appuser

# Health check — gọi vào /healthz; fail → Docker đánh dấu unhealthy
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()" || exit 1

# 0.0.0.0 — bind vào tất cả interface, không phải chỉ localhost
# ${PORT:-8000} — Railway/Render/Cloud Run tự gán PORT; dùng 8000 làm fallback
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
