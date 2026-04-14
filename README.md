# AI Cloud Operator

> Operate AWS infrastructure using natural language — powered by Google Gemini.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)](https://ai.google.dev)
[![AWS](https://img.shields.io/badge/Cloud-AWS-yellow.svg)](https://aws.amazon.com)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

---

## Overview

AI Cloud Operator is an open-source backend system that lets you manage AWS infrastructure through natural language. Instead of memorizing CLI syntax or navigating the AWS console, you simply describe what you want — the AI figures out the rest.

```
"Show me all running EC2 instances in Jakarta"
        ↓
aws ec2 describe-instances --filters Name=instance-state-name,Values=running --region ap-southeast-3
        ↓
"Found 3 running instances: web-prod (t3.micro), api-prod (t3.small), worker-01 (t3.medium)"
```

No hardcoded commands. No static mappings. Every command is generated dynamically by AI based on your intent.

---

## Features

### Natural Language to AWS CLI
Write queries in plain English or Bahasa Indonesia. The AI translates your intent into precise AWS CLI commands with the correct parameters, filters, and output format.

### Dynamic AWS Coverage
Supports EC2, S3, Lambda, IAM, RDS, CloudWatch, and more — without any service-specific code. New AWS services are supported automatically as the AI model evolves.

### AI-Powered Insights
Raw AWS JSON output is transformed into human-readable summaries with actionable recommendations — cost optimization tips, security warnings, and resource health alerts included.

### Built-in Security Layer
Every command passes through a Guardrail agent before execution. Destructive operations require explicit confirmation. A hard blocklist prevents mass-deletion and privilege escalation commands from ever running.

### Full Audit Trail
Every query, translated command, execution result, and user confirmation is logged with timestamps and user identity — ready for compliance and incident review.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        USER                             │
│         Natural language query (EN / ID)                │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND / CLI                         │
│            REST API  ·  Web Dashboard                   │
└──────────────────────────┬──────────────────────────────┘
                           │  POST /api/execute
                           ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND  (FastAPI + Kiro)                  │
│                                                         │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
│   │  Guardrail  │  │  Translator │  │   Formatter   │  │
│   │   (block)   │  │  (NL→CLI)   │  │  (summarize)  │  │
│   └─────────────┘  └─────────────┘  └───────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │  Prompt + context
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 AI ENGINE  (Gemini)                     │
│         Translate  ·  Validate  ·  Summarize            │
└──────────────────────────┬──────────────────────────────┘
                           │  AWS CLI command
                           ▼
┌─────────────────────────────────────────────────────────┐
│              EXECUTION LAYER  (Boto3)                   │
│        EC2  ·  S3  ·  Lambda  ·  IAM  ·  RDS           │
└──────────────────────────┬──────────────────────────────┘
                           │  Raw JSON response
                           ▼
                    Formatter (Gemini)
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                        USER                             │
│              Insight + Recommendations                  │
└─────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- AWS CLI configured (`aws configure`)
- Google Gemini API key ([get one here](https://ai.google.dev))

### Installation

```bash
# Clone the repository
git clone https://github.com/lilikzone/TESTAI.git
cd TESTAI

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key_here
AWS_REGION=ap-southeast-3
```

Ensure AWS credentials are configured:

```bash
aws configure
# or set environment variables:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### Run the Server

```bash
uvicorn backend.main:app --reload --port 8000
```

API is now available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

### Quick Test

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "list all running EC2 instances"}'
```

---

## Project Structure

```
TESTAI/
├── backend/
│   ├── main.py               # FastAPI entry point
│   ├── README.md             # Backend developer docs
│   ├── services/
│   │   ├── ai_service.py     # Gemini integration
│   │   ├── cli_executor.py   # AWS execution via Boto3
│   │   └── security.py       # Guardrail & approval flow
│   └── utils/
│       ├── logger.py         # Audit logging
│       └── parser.py         # Response parsing
├── agents/
│   ├── cli-translator.md     # Translator agent spec
│   ├── formatter.md          # Formatter agent spec
│   └── guardrail.md          # Security agent spec
├── docs/
│   ├── architecture.md       # System architecture
│   ├── flow.md               # End-to-end request flow
│   └── roadmap.md            # Development roadmap
├── prompts/
│   ├── translator.txt        # Gemini prompt — NL to CLI
│   └── formatter.txt         # Gemini prompt — summarize output
├── requirements.txt
└── .env.example
```

---

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | CLI Execution — Boto3 integration, core AWS services | 🔄 In Progress |
| **Phase 2** | AI Integration — Gemini translate & format pipeline | ⏳ Planned |
| **Phase 3** | Security Layer — Guardrail, audit log, approval flow | ⏳ Planned |
| **Phase 4** | Frontend Dashboard — Chat UI, resource visualization | ⏳ Planned |
| **Phase 5** | Multi-Cloud — GCP and Azure support | ⏳ Planned |

See [docs/roadmap.md](docs/roadmap.md) for detailed milestones.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change. For major changes, open a discussion before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'feat: add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.
