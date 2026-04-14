# AI Cloud Operator

AI yang bisa mengoperasikan AWS menggunakan natural language. Cukup ketik perintah seperti "list semua EC2 instance yang running" dan sistem akan menerjemahkan, mengeksekusi, dan merangkum hasilnya secara otomatis.

---

## Arsitektur

```
User Input (Natural Language)
        ↓
   Frontend / CLI
        ↓
   Backend (Kiro + FastAPI)
        ↓
   AI Engine (Gemini)
        ↓
   AWS CLI / Boto3
        ↓
   AWS Cloud (EC2, S3, Lambda, dll)
        ↓
   Formatted Response → User
```

---

## Tools yang Digunakan

| Tool | Fungsi |
|------|--------|
| **Kiro** | Backend orchestration & agent management |
| **Gemini** | AI engine untuk natural language processing |
| **AWS** | Cloud execution target (EC2, S3, Lambda, dll) |
| **FastAPI** | REST API layer |
| **Boto3** | AWS SDK untuk Python |

---

## Cara Menjalankan Project

> **Prerequisites:** Python 3.10+, AWS CLI configured, Gemini API Key

```bash
# 1. Clone repository
git clone https://github.com/lilikzone/TESTAI.git
cd TESTAI

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment variables
cp .env.example .env
# Edit .env dan isi GEMINI_API_KEY dan AWS credentials

# 4. Jalankan server
uvicorn backend.main:app --reload

# 5. Akses API
# http://localhost:8000/docs
```

---

## Struktur Folder

```
TESTAI/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── flow.md
│   └── roadmap.md
├── agents/
│   ├── cli-translator.md
│   ├── formatter.md
│   └── guardrail.md
├── backend/
│   └── main.py
└── prompts/
    ├── translator.txt
    └── formatter.txt
```

---

## Lisensi

MIT License
