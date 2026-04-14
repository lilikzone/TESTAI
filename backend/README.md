# Backend — AI Cloud Operator

FastAPI backend yang mengorkestrasikan alur dari natural language input hingga eksekusi AWS dan formatting response.

---

## Struktur Folder

```
backend/
├── main.py               # Entry point — FastAPI app & route definitions
├── services/
│   ├── ai_service.py     # Gemini API integration (translate + format)
│   ├── cli_executor.py   # AWS CLI / Boto3 execution layer
│   └── security.py       # Guardrail — validasi & approval flow
└── utils/
    ├── logger.py         # Audit logging
    └── parser.py         # Response parsing helpers
```

---

## Komponen

### `main.py`
Entry point aplikasi. Mendefinisikan FastAPI instance, middleware, dan semua route endpoint.

```python
POST /api/execute     # Main endpoint — terima query, jalankan full pipeline
GET  /api/health      # Health check
GET  /docs            # Swagger UI (auto-generated)
```

Bertanggung jawab untuk:
- Menerima request dari frontend / CLI
- Memanggil pipeline: security → translate → execute → format
- Mengembalikan response ke user

---

### `services/ai_service.py`
Integrasi dengan Google Gemini API. Menangani dua tugas utama:

**Translate** — Mengubah natural language menjadi AWS CLI command:
```python
async def translate(query: str, context: dict) -> TranslateResult:
    # Kirim query ke Gemini dengan prompt translator
    # Return: { command, service, action, risk_level, confidence }
```

**Format** — Merangkum raw AWS output menjadi insight:
```python
async def format_output(raw: dict, original_query: str) -> FormatResult:
    # Kirim raw JSON ke Gemini dengan prompt formatter
    # Return: { summary, recommendations, resource_count }
```

Konfigurasi:
```
GEMINI_API_KEY   → wajib diset di .env
Model default    → gemini-1.5-pro
Timeout          → 30 detik per request
```

---

### `services/cli_executor.py`
Mengeksekusi AWS CLI command menggunakan Boto3 SDK. Hanya menerima command yang sudah divalidasi oleh `security.py`.

```python
async def execute(command: str, region: str) -> ExecuteResult:
    # Parse command string → Boto3 API call
    # Return: { raw_output, status, duration_ms }
```

Bertanggung jawab untuk:
- Parsing command string ke Boto3 method call
- Menerapkan timeout per eksekusi (default: 60 detik)
- Menangani AWS error codes dan mengembalikan pesan yang informatif
- Tidak pernah menerima command langsung dari user — selalu via pipeline

Error yang ditangani:

| AWS Error Code | Response ke User |
|---------------|-----------------|
| `UnauthorizedOperation` | "Akses ditolak. Cek IAM permission." |
| `NoSuchBucket` | "Resource tidak ditemukan." |
| `ThrottlingException` | Retry otomatis dengan exponential backoff |
| `RequestExpired` | "Cek konfigurasi waktu sistem." |

---

### `services/security.py`
Implementasi Guardrail Agent. Setiap command wajib melewati layer ini sebelum dieksekusi.

```python
async def validate(query: str, command: str, risk_level: str) -> ValidationResult:
    # Cek hard blocklist
    # Klasifikasikan risk level
    # Return: { allowed, requires_confirmation, reason, audit_log_id }
```

Risk levels:

| Level | Aksi |
|-------|------|
| `READ_ONLY` | Auto-approve |
| `MODIFY` | Approve + enhanced logging |
| `DESTRUCTIVE` | Tahan — tunggu konfirmasi user |
| `BLOCKED` | Hard block — tidak bisa dieksekusi |

---

### `utils/logger.py`
Audit logging untuk setiap eksekusi. Log bersifat append-only.

```python
def log(event: AuditEvent) -> str:
    # Tulis ke audit log
    # Return: audit_log_id
```

Setiap log entry menyimpan: `timestamp`, `user_id`, `query`, `command`, `risk_level`, `allowed`, `duration_ms`.

---

### `utils/parser.py`
Helper untuk parsing dan normalisasi response dari AWS dan Gemini.

```python
def parse_aws_response(raw: dict) -> dict   # Normalisasi struktur JSON AWS
def parse_gemini_output(text: str) -> dict  # Ekstrak command dari Gemini response
```

---

## Flow Lengkap

```
POST /api/execute  { "query": "tampilkan EC2 yang running" }
         │
         ▼
    main.py
         │
         ▼
    security.py ──── BLOCKED? ──→ Return error ke user
         │
       SAFE
         │
         ▼
    ai_service.py (translate)
    Gemini → "aws ec2 describe-instances --filters ..."
         │
         ▼
    security.py (re-validate command)
         │
         ▼
    cli_executor.py
    Boto3 → AWS API → raw JSON
         │
         ▼
    ai_service.py (format)
    Gemini → "Ditemukan 3 EC2 instance running: ..."
         │
         ▼
    logger.py → audit log
         │
         ▼
    Response ke user
    { "summary": "...", "recommendations": [...] }
```

---

## Setup & Menjalankan

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env: isi GEMINI_API_KEY dan pastikan AWS credentials terkonfigurasi

# Jalankan server
uvicorn backend.main:app --reload --port 8000

# Akses Swagger UI
open http://localhost:8000/docs
```

Pastikan AWS credentials sudah dikonfigurasi via `aws configure` atau environment variables:
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-southeast-3
```

---

## Environment Variables

| Variable | Wajib | Default | Deskripsi |
|----------|-------|---------|-----------|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key |
| `AWS_REGION` | ✅ | `ap-southeast-3` | AWS region target |
| `AWS_ACCESS_KEY_ID` | ✅ | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | ✅ | — | AWS credentials |
| `LOG_LEVEL` | ❌ | `INFO` | Level logging aplikasi |
| `GEMINI_MODEL` | ❌ | `gemini-1.5-pro` | Model Gemini yang digunakan |
| `EXECUTION_TIMEOUT` | ❌ | `60` | Timeout eksekusi AWS (detik) |
