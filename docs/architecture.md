# System Architecture — AI Cloud Operator

## Overview

AI Cloud Operator adalah sistem berbasis AI yang memungkinkan pengguna mengoperasikan AWS menggunakan bahasa alami. Tidak ada command yang di-hardcode — setiap perintah dibuat secara dinamis oleh AI berdasarkan konteks dan intent pengguna.

Sistem ini dirancang dengan prinsip **AI as Decision Engine**: AI tidak hanya menerjemahkan teks, tetapi memahami konteks, menentukan service yang tepat, memilih parameter yang relevan, dan memvalidasi keamanan sebelum eksekusi.

---

## Diagram Alur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                    │
│   "Tampilkan semua EC2 instance yang running di Jakarta"        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Natural Language Input
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND LAYER                            │
│                                                                 │
│   ┌─────────────────┐          ┌──────────────────────────┐    │
│   │   Web Dashboard  │   atau   │      CLI Interface        │    │
│   │  (React/Next.js) │          │   (Terminal / Script)    │    │
│   └────────┬────────┘          └────────────┬─────────────┘    │
│            └──────────────┬─────────────────┘                  │
└───────────────────────────┼─────────────────────────────────────┘
                            │ HTTP POST /api/execute
                            │ { "query": "..." }
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND LAYER                              │
│                    FastAPI + Kiro Orchestrator                  │
│                                                                 │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│   │  Guardrail   │──▶│  Translator  │──▶│    Formatter     │  │
│   │    Agent     │   │    Agent     │   │      Agent       │  │
│   │  (security)  │   │ (NL → CLI)   │   │ (output summary) │  │
│   └──────────────┘   └──────┬───────┘   └──────────────────┘  │
└──────────────────────────────┼──────────────────────────────────┘
                               │ Prompt + Context
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AI ENGINE LAYER                           │
│                      Google Gemini API                          │
│                                                                 │
│   Input:  Natural language query + AWS context                  │
│   Output: Valid AWS CLI command (dinamis, tidak hardcoded)      │
│                                                                 │
│   Gemini memahami intent, memilih service, dan menyusun         │
│   parameter yang tepat berdasarkan query pengguna.              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ AWS CLI Command String
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION LAYER                             │
│                    AWS CLI / Boto3 SDK                          │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│   │   EC2    │  │    S3    │  │  Lambda  │  │  CloudWatch │  │
│   └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│   ┌──────────┐  ┌──────────┐                                   │
│   │   IAM    │  │   RDS    │  ... dan service AWS lainnya      │
│   └──────────┘  └──────────┘                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Raw JSON Output
                               ▼
                    Formatter Agent (Gemini)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          USER                                   │
│   "Ditemukan 3 EC2 instance running: i-0abc (t3.micro), ..."   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Penjelasan Setiap Layer

### 1. Frontend Layer

Frontend adalah titik masuk pengguna ke sistem. Tersedia dalam dua mode:

- **Web Dashboard** — Antarmuka berbasis browser dengan chat interface, history eksekusi, dan visualisasi resource AWS. Dibangun menggunakan React/Next.js.
- **CLI Interface** — Untuk pengguna teknis yang lebih nyaman bekerja di terminal. Mendukung scripting dan otomasi.

Kedua interface mengirim query ke Backend melalui REST API (`POST /api/execute`) dengan payload berupa natural language string. Frontend tidak memiliki logika AWS apapun — semua diproses di backend.

---

### 2. Backend Layer (FastAPI + Kiro)

Backend adalah inti dari sistem. Terdiri dari dua komponen utama:

**FastAPI** — REST API server yang menerima request dari frontend, mengorkestrasi alur antar agent, dan mengembalikan response ke user.

**Kiro Orchestrator** — Mengelola urutan eksekusi agent:
1. Request masuk → dikirim ke **Guardrail Agent** untuk validasi keamanan
2. Jika aman → dikirim ke **Translator Agent** untuk konversi ke AWS CLI
3. Command dieksekusi via Boto3
4. Raw output dikirim ke **Formatter Agent** untuk dirangkum
5. Response dikembalikan ke user

Backend juga menangani:
- Session management dan context per user
- Error handling dan retry logic
- Audit logging setiap eksekusi
- Rate limiting untuk mencegah abuse

---

### 3. AI Engine Layer (Google Gemini)

Gemini adalah otak dari sistem. Digunakan oleh tiga agent dengan peran berbeda:

| Agent | Peran | Input | Output |
|-------|-------|-------|--------|
| `cli-translator` | Konversi NL → AWS CLI | Natural language query | AWS CLI command string |
| `formatter` | Rangkum output AWS | Raw JSON dari AWS | Teks ringkas dan informatif |
| `guardrail` | Validasi keamanan | Query + command | Allow / Block + alasan |

Setiap agent menggunakan prompt yang telah dioptimasi (lihat folder `prompts/`) untuk memastikan output yang konsisten dan akurat.

---

### 4. Execution Layer (AWS CLI / Boto3)

Layer ini bertanggung jawab mengeksekusi command yang telah divalidasi dan diterjemahkan oleh AI. Menggunakan **Boto3** (AWS SDK untuk Python) sebagai interface utama ke AWS API.

Prinsip eksekusi:
- Command hanya dieksekusi setelah lolos validasi Guardrail
- Setiap eksekusi dicatat di audit log
- Timeout diterapkan untuk mencegah hanging request
- Error dari AWS (AuthorizationError, ThrottlingError, dll) ditangani dan dikembalikan dalam format yang mudah dipahami

---

## Konsep Kunci

### Dynamic CLI — Tidak Ada Command yang Hardcoded

Sistem ini tidak menggunakan mapping statis antara intent dan command. Tidak ada tabel seperti `"list EC2" → "aws ec2 describe-instances"` yang di-hardcode.

Sebaliknya, **setiap command dibuat secara dinamis oleh Gemini** berdasarkan:
- Intent pengguna
- Konteks sesi (region, filter, resource yang disebutkan)
- Parameter spesifik yang relevan

Ini berarti sistem dapat menangani query yang sangat spesifik dan kompleks tanpa perlu update kode, misalnya:

> "Tampilkan EC2 instance dengan tag Environment=production yang sudah berjalan lebih dari 7 hari dan tipe instancenya t3 ke atas"

Command untuk query seperti ini tidak mungkin di-hardcode, tetapi Gemini dapat menyusunnya secara dinamis.

---

### AI sebagai Decision Engine

Gemini bukan sekadar "translator teks". Dalam sistem ini, AI berperan sebagai **decision engine** yang:

1. **Memahami intent** — Membedakan antara "list" (read-only) vs "delete" (destruktif)
2. **Memilih service yang tepat** — Menentukan apakah query membutuhkan EC2, S3, Lambda, atau kombinasi beberapa service
3. **Menyusun parameter optimal** — Menambahkan filter, query, dan output format yang tepat secara otomatis
4. **Menilai risiko** — Mengidentifikasi apakah sebuah operasi berpotensi merusak atau tidak
5. **Merangkum hasil** — Mengubah JSON teknis menjadi informasi yang actionable bagi pengguna

Dengan pendekatan ini, sistem dapat berkembang mengikuti kemampuan model AI tanpa perlu perubahan arsitektur yang signifikan.

---

## Security Architecture

```
Query masuk
    │
    ▼
Guardrail Agent
    ├── READ_ONLY  → ✅ Langsung eksekusi
    ├── MODIFY     → ⚠️  Eksekusi + audit log
    ├── DESTRUCTIVE → ❌ Require explicit confirmation
    └── BLOCKED    → 🚫 Hard block, tidak bisa dieksekusi
```

Prinsip keamanan yang diterapkan:
- **Default Deny** — Jika intent tidak jelas, blokir dan minta klarifikasi
- **Least Privilege** — IAM role hanya memiliki permission yang dibutuhkan
- **Immutable Audit Log** — Setiap eksekusi dicatat dan tidak bisa dimodifikasi
- **No Wildcards on Destructive** — Operasi hapus harus menyebutkan resource ID spesifik
