"""CP4 — Graceful shutdown (draining).

Khi bạn deploy phiên bản mới, orchestrator (Docker, Railway, Cloud Run, K8s)
gửi **SIGTERM** rồi đợi vài chục giây trước khi SIGKILL. Nếu app bỏ qua tín
hiệu đó, mọi request đang xử lý dở bị cắt giữa chừng — user thấy lỗi 502 mỗi
lần bạn deploy.

Ứng xử đúng gọi là *draining*: nhận SIGTERM → báo "tôi sắp tắt" qua health
check để load balancer ngừng đẩy traffic mới vào → xử lý nốt request đang
chạy → thoát.
"""

from __future__ import annotations

import signal


class ShutdownGuard:
    """Giữ trạng thái vòng đời của process."""

    def __init__(self) -> None:
        self.draining = False
        # Handler đã được đăng ký trước ta (của uvicorn) — xem arm()
        self._previous: dict = {}

    def start_draining(self, signum=None, frame=None) -> None:
        """Signal handler: đánh dấu process đang tắt dần.

        1. Bật cờ draining — /healthz sẽ trả 503 → LB ngừng gửi traffic mới
        2. Gọi lại handler cũ (của uvicorn) — quan trọng:
           Mỗi tín hiệu chỉ có một handler. Đăng ký handler của mình là ghi
           đè handler của uvicorn. Không gọi lại nó thì app bật cờ "đang tắt"
           rồi chạy tiếp mãi mãi — đúng cái graceful shutdown định tránh.

        Handler chạy xen giữa bytecode → chỉ làm việc rất nhẹ (chỉ bật cờ,
        không gọi mạng, không ghi file).
        """
        self.draining = True
        previous = self._previous.get(signum)
        if callable(previous):
            previous(signum, frame)

    def arm(self) -> None:
        """Đăng ký handler cho SIGTERM và SIGINT, nhớ lại handler cũ.

        Với mỗi tín hiệu: getsignal() trước → ghi nhớ → signal() ghi đè.
        Thứ tự quan trọng: phải ghi nhớ handler cũ TRƯỚC khi ghi đè.
        """
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._previous[sig] = signal.getsignal(sig)   # nhớ handler cũ
            signal.signal(sig, self.start_draining)        # rồi mới ghi đè


# Một instance dùng chung cho cả app
shutdown_guard = ShutdownGuard()
