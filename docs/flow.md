# User Flow — AI Cloud Operator

## End-to-End Flow

Dokumen ini menjelaskan alur lengkap dari input pengguna hingga respons dikembalikan.

---

## Flow Diagram

```
User
 │
 │  "Tampilkan semua EC2 instance yang sedang running"
 ▼
┌─────────────────────────────┐
│     Frontend / CLI Input    │
│   POST /api/execute         │
│   { "query": "..." }        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│    Guardrail Agent          │
│  - Cek apakah query aman    │
│  - Blokir destructive cmd   │
│  - Validasi intent          │
└──────────────┬──────────────┘
               │ ✅ SAFE
               ▼
┌─────────────────────────────┐
│    CLI Translator Agent     │
│  - Kirim query ke Gemini    │
│  - Terima AWS CLI command   │
│  Output:                    │
│  "aws ec2 describe-instances│
│   --filters Name=instance-  │
│   state-name,Values=running"│
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│    AWS Execution            │
│  - Boto3 / AWS CLI          │
│  - Eksekusi command         │
│  - Terima raw JSON output   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│    Formatter Agent          │
│  - Kirim raw output ke AI   │
│  - Ringkas menjadi teks     │
│  Output:                    │
│  "Ditemukan 3 instance      │
│   running: i-xxx (t3.micro),│
│   i-yyy (t2.small), ..."    │
└──────────────┬──────────────┘
               │
               ▼
            User
  "Ditemukan 3 EC2 instance running..."
```

---

## Detail Setiap Step

### Step 1: User Input
Pengguna mengirim query dalam bahasa alami melalui CLI atau API endpoint `POST /api/execute`.

### Step 2: Guardrail Check
Agent `guardrail` menganalisis intent dari query:
- ✅ **ALLOW:** Query read-only (describe, list, get)
- ⚠️ **CONFIRM:** Query modifikasi (create, update, start, stop)
- ❌ **BLOCK:** Query destruktif tanpa konfirmasi (terminate, delete, purge)

### Step 3: CLI Translation
Agent `cli-translator` menggunakan Gemini untuk mengubah natural language menjadi AWS CLI command yang valid dan spesifik.

### Step 4: AWS Execution
Command dieksekusi menggunakan Boto3 SDK. Output berupa raw JSON dari AWS API.

### Step 5: Response Formatting
Agent `formatter` menggunakan Gemini untuk merangkum raw JSON menjadi teks yang mudah dipahami pengguna.

### Step 6: Response ke User
Hasil akhir dikembalikan melalui API response atau ditampilkan di CLI.

---

## Error Handling Flow

```
Error terjadi di AWS Execution
         │
         ▼
  Cek tipe error:
  ├── AuthorizationError → "Akses ditolak, cek IAM permission"
  ├── ResourceNotFound  → "Resource tidak ditemukan"
  ├── ThrottlingError   → Retry dengan exponential backoff
  └── UnknownError      → Log + return pesan generik
```
