# Phiếu Phản Ánh — K4 Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay dòng `> *Câu trả lời của bạn*` bằng câu trả lời.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Trần Văn Thị  Mã học viên: 2A202601548

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `api_token` không có giá trị mặc định nên app chết ngay khi
khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà việc
"chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

> Nếu để mặc định `api_token = "changeme"`, app vẫn khởi động bình thường dù
> biến môi trường `API_TOKEN` chưa được set trên cloud. Kịch bản xảy ra: team
> deploy phiên bản mới lên Railway lúc 2h sáng, quên không set `API_TOKEN`
> trong dashboard. App chạy, healthcheck xanh, nhưng bất kỳ ai biết token mặc
> định đều gọi API được — và hóa đơn LLM chạy. Với không mặc định, app chết
> ngay lúc khởi động, Railway báo đỏ ngay, team thấy lỗi và sửa trước khi có
> traffic vào. Fail fast tốt hơn fail silently.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/chat` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

> Một dòng log JSON thực tế thu được:
> `{"event": "chat_completed", "client_id": "sv01", "prompt_tokens": 12, "completion_tokens": 35, "usd_cost": 0.0000226, "timestamp": "2026-08-10T08:30:00Z"}`
>
> Hai việc làm được mà `print` không làm được:
> 1. **Lọc và tìm kiếm tự động**: với log JSON, có thể dùng `jq`, Grafana Loki
>    hoặc Datadog để query `usd_cost > 0.01` hay `client_id == "sv01"` trong
>    hàng triệu dòng log — không thể làm với chuỗi tự do của print.
> 2. **Cảnh báo tự động**: hệ thống monitoring đọc JSON, phát hiện pattern bất
>    thường (ví dụ `completion_tokens > 1000` liên tục) và gửi alert Slack/PagerDuty.
>    Print chỉ hiện chữ, không có schema để máy đọc hiểu.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t chat:single .
docker build -t chat:multi .
docker images | grep chat
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu) | ~180 MB |
| Multi-stage | ~160 MB |

> Image multi-stage nhỏ hơn vì stage `builder` bị bỏ đi sau khi compile xong.
> Phần chênh lệch chính là: các build tool (gcc, pip cache, header C), file tạm
> của quá trình cài thư viện, và metadata của pip. Stage `runtime` chỉ copy
> thư viện Python đã cài vào `/usr/local` — không mang theo trình biên dịch hay
> cache. Với dự án phức tạp hơn (thư viện C extension như numpy, pillow), phần
> chênh lệch có thể lên tới 500MB–1GB.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

> Với Dockerfile hiện tại (COPY requirements.txt → RUN pip install → COPY app):
> - Sửa `app/main.py` → các layer trước `COPY app ./app` vẫn được cache (bao
>   gồm cả layer pip install nặng). Chỉ layer `COPY app ./app` trở đi phải
>   chạy lại. Build lại chỉ mất vài giây.
>
> Nếu đặt `COPY . .` trước `RUN pip install`:
> - Mỗi lần sửa bất kỳ file nào (kể cả README.md), Docker thấy context thay đổi
>   → invalidate cache từ dòng COPY đó → phải chạy lại toàn bộ pip install.
>   Mỗi lần build mất 2–5 phút thay vì vài giây. Đây là lý do thứ tự COPY
>   requirements.txt → pip install → COPY source rất quan trọng.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

> Chuỗi sự kiện nếu chạy root:
> 1. Code Python có lỗ hổng (ví dụ: path traversal, deserialization không an toàn)
> 2. Kẻ tấn công khai thác lỗ hổng, thực thi lệnh shell bên trong container
> 3. Vì process chạy là root (uid=0), kẻ tấn công có toàn quyền trong container
> 4. Docker namespace cô lập nhưng kernel vẫn dùng chung. Nếu container có
>    volume mount (như `/var/run/docker.sock`) hoặc có lỗ hổng kernel, root
>    trong container = root trên host → đọc/xóa file host, chạy container mới,
>    chiếm toàn bộ máy chủ.
>
> Lệnh `USER appuser` cắt đứt tại bước 3: process chạy với uid=10001, không có
> quyền ghi vào system directory, không thể escalate privilege. Kẻ tấn công có
> shell nhưng không làm được gì nhiều — thiệt hại bị giới hạn trong phạm vi
> user thường.

---

### Câu 6 — Bearer token (CP3)

Vì sao 401 phải kèm header `WWW-Authenticate: Bearer`? Và vì sao ta trả **cùng
một** thông báo lỗi cho cả ba trường hợp (thiếu header, sai scheme, sai token)
thay vì nói rõ sai ở đâu cho người dùng dễ sửa?

> `WWW-Authenticate: Bearer` theo chuẩn HTTP/RFC 6750 — đây là cách server
> "quảng cáo" phương thức xác thực nó chấp nhận. Client (thư viện HTTP, curl,
> Postman) đọc header này để biết cần gửi Bearer token, không phải Basic auth
> hay Digest. Thiếu header này vi phạm chuẩn, một số client tự động retry sẽ
> không biết cách retry đúng.
>
> Trả cùng một thông báo cho cả 3 trường hợp là bảo mật chủ ý: nếu phân biệt
> "thiếu header" vs "sai token", kẻ tấn công brute-force biết token đã tồn tại
> (chỉ bị sai), thu hẹp không gian tìm kiếm. Thông báo mơ hồ "invalid or
> missing token" buộc kẻ tấn công không biết mình đang sai ở bước nào — đây là
> nguyên tắc "security through ambiguity" đúng chỗ.

---

### Câu 7 — Token bucket (CP3)

Với `capacity=10`, `refill_per_minute=10`: một client im lặng 10 phút rồi gửi
liên tiếp. Nó gửi được bao nhiêu request trước khi bị 429? Nếu bỏ đoạn
`min(capacity, ...)` trong `available()` thì con số đó thành bao nhiêu, và tại sao?

> Với `min(capacity, ...)`: im lặng 10 phút → tích được 10×10=100 token lý
> thuyết, nhưng `min(10, 100) = 10` → xô chỉ có 10 token. Gửi được 10 request
> liên tiếp, request thứ 11 bị 429. Đây là hành vi đúng: xô đầy là giới hạn
> tối đa.
>
> Nếu bỏ `min(capacity, ...)`: im lặng 10 phút → tích 100 token không bị giới
> hạn. Gửi được 100 request trước khi bị 429. Client học được cách "tích điểm"
> bằng cách im lặng rồi xả burst cực lớn — bộ rate limiter mất tác dụng. Hệ
> thống bị tấn công burst 100 request cùng lúc thay vì tối đa 10.

---

### Câu 8 — Ngân sách theo ngày (CP3)

So sánh hạn mức $30/tháng với hạn mức $1/ngày cho cùng một client. Giả sử có sự
cố khiến một client gọi liên tục từ 2h sáng. Với mỗi cách, thiệt hại tối đa là
bao nhiêu và service tự hồi phục khi nào?

> **$30/tháng**: sự cố từ 2h sáng đến 7h sáng (5 tiếng) có thể tiêu hết $30
> toàn bộ ngân sách tháng. Service bị block đến đầu tháng sau (tối đa 30 ngày).
> Thiệt hại: $30, downtime tiềm năng 30 ngày.
>
> **$1/ngày**: sự cố từ 2h sáng → đến khi tiêu hết $1 → bị block. Lúc 0h UTC
> ngày hôm sau, key Redis tự expire, ngân sách reset về $0, service tự hồi phục
> mà không cần ai can thiệp. Thiệt hại tối đa: $1/ngày × số ngày sự cố kéo dài.
> Một sự cố 1 ngày chỉ mất $1 thay vì $30. Đây là lý do hạn mức theo ngày tốt
> hơn theo tháng cho môi trường production.

---

### Câu 9 — /healthz khác /readyz (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> Thứ tự sự kiện nếu gộp và kiểm tra Redis:
> 1. Redis mất kết nối (giây 0)
> 2. Load balancer gọi `/healthz` mỗi 10 giây → gọi Redis → timeout/fail
> 3. Endpoint trả 503 (giây ~10)
> 4. Load balancer đánh dấu cả 3 container là unhealthy
> 5. Orchestrator (Docker/K8s) nhận signal unhealthy → **restart tất cả 3 container**
> 6. Các request đang xử lý trong 3 container bị cắt ngang → user thấy lỗi 502
> 7. Sau 30 giây Redis phục hồi, nhưng các container vừa restart xong → cần
>    thêm thời gian warmup
>
> Với thiết kế tách biệt: Redis chết → `/readyz` trả 503 → LB ngừng gửi traffic
> mới → nhưng `/healthz` vẫn 200 → container KHÔNG bị restart → sau 30 giây
> Redis phục hồi, LB thấy `/readyz` xanh → tự động routing lại. Không restart,
> không downtime, không mất request đang chạy.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> Lỗi gặp phải: Khi mới deploy lên Railway, container bị crash liên tục với thông báo
> `Error: Invalid value for '--port': '$PORT' is not a valid integer.` trong Deploy Logs.
>
> Nguyên nhân: Railway tự động cấp biến `$PORT` động cho container, nhưng lệnh `startCommand`
> trong `railway.toml` gọi uvicorn trực tiếp khiến chuỗi `$PORT` không được shell giải mã
> thành số cổng thực tế mà bị truyền dưới dạng chuỗi thô "$PORT".
>
> Cách sửa: Cập nhật `railway.toml` sửa `startCommand` thành `sh -c 'uvicorn app.main:app --host 0.0.0.0 --port $PORT'`
> để shell thực thi và giải mã biến `$PORT` thành số cổng trước khi truyền vào uvicorn.
