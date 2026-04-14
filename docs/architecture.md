# System Architecture — AI Cloud Operator

## Overview

AI Cloud Operator adalah sistem berbasis AI yang memungkinkan pengguna mengoperasikan AWS menggunakan bahasa alami. Sistem ini terdiri dari beberapa layer yang bekerja secara berurutan untuk memproses input, mengeksekusi perintah, dan mengembalikan respons yang mudah dipahami.

---

## Layer Architecture

### 1. Input Layer
- **Interface:** CLI atau REST API (FastAPI)
- **Input:** Natural language dari pengguna (Bahasa Indonesia / Inggris)
- **Output:** Raw text dikirim ke Backend Layer

### 2. Backend Layer (Kiro + FastAPI)
- **Orchestrator:** Kiro mengelola alur antar agent
- **API Server:** FastAPI menerima request dan mengembalikan response
- **Responsibilities:**
  - Routing request ke agent yang tepat
  - Mengelola session dan context
  - Error handling dan logging

### 3. AI Layer (Gemini)
- **Engine:** Google Gemini API
- **Agents:**
  - `cli-translator` → mengubah natural language menjadi AWS CLI command
  - `formatter` → merangkum output AWS menjadi teks yang mudah dibaca
  - `guardrail` → memvalidasi command sebelum dieksekusi
- **Input:** Natural language + context
- **Output:** AWS CLI command yang valid dan aman

### 4. Execution Layer (AWS)
- **SDK:** Boto3 (Python AWS SDK)
- **CLI:** AWS CLI untuk eksekusi langsung
- **Services yang didukung:**
  - EC2 (compute)
  - S3 (storage)
  - Lambda (serverless)
  - IAM (identity & access)
  - CloudWatch (monitoring)

### 5. Response Layer
- Output dari AWS diproses oleh `formatter` agent
- Hasil dikembalikan ke user dalam format yang ringkas dan informatif

---

## Diagram Komponen

```
┌─────────────────────────────────────────────────────┐
│                    INPUT LAYER                      │
│              CLI / REST API (FastAPI)               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  BACKEND LAYER                      │
│           Kiro Orchestrator + FastAPI               │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Guardrail  │  │Translator│  │   Formatter   │  │
│  │   Agent     │  │  Agent   │  │    Agent      │  │
│  └─────────────┘  └──────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   AI LAYER                          │
│              Google Gemini API                      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                EXECUTION LAYER                      │
│            AWS CLI / Boto3 SDK                      │
│         EC2 | S3 | Lambda | IAM | CW               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 RESPONSE LAYER                      │
│         Formatted Output → User                     │
└─────────────────────────────────────────────────────┘
```

---

## Security Considerations

- Semua command divalidasi oleh `guardrail` agent sebelum dieksekusi
- AWS credentials tidak pernah dikirim ke Gemini API
- Principle of least privilege diterapkan pada IAM role
- Destructive commands (terminate, delete) memerlukan konfirmasi eksplisit
