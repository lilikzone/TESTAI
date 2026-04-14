# Agent: CLI Translator

## Overview

`cli-translator` adalah agent yang bertanggung jawab mengubah input natural language dari pengguna menjadi AWS CLI command yang valid dan siap dieksekusi.

---

## Fungsi Utama

- Menerima query natural language (Bahasa Indonesia / Inggris)
- Mengidentifikasi AWS service yang relevan (EC2, S3, Lambda, IAM, dll)
- Menghasilkan AWS CLI command yang tepat dan lengkap dengan parameter
- Memastikan command sesuai dengan AWS CLI syntax terbaru

---

## Input / Output

**Input:**
```json
{
  "query": "tampilkan semua EC2 instance yang sedang running di region ap-southeast-3",
  "context": {
    "aws_region": "ap-southeast-3",
    "account_id": "123456789"
  }
}
```

**Output:**
```json
{
  "command": "aws ec2 describe-instances --filters Name=instance-state-name,Values=running --region ap-southeast-3",
  "service": "ec2",
  "action": "describe-instances",
  "risk_level": "read-only"
}
```

---

## Prompt yang Digunakan

Lihat: [`../prompts/translator.txt`](../prompts/translator.txt)

---

## Supported AWS Services

| Service | Actions |
|---------|---------|
| EC2 | describe, start, stop, terminate, create |
| S3 | list, get, put, delete, sync |
| Lambda | list, invoke, create, update, delete |
| IAM | list-users, list-roles, get-policy |
| CloudWatch | get-metrics, describe-alarms |
| RDS | describe, start, stop, reboot |

---

## Error Handling

- Jika query ambigu → minta klarifikasi ke user
- Jika service tidak dikenali → return error dengan saran
- Jika command tidak bisa dibuat → log dan escalate ke human

---

## Contoh Translasi

| Natural Language | AWS CLI Command |
|-----------------|----------------|
| "list semua S3 bucket" | `aws s3 ls` |
| "berapa EC2 yang running?" | `aws ec2 describe-instances --filters Name=instance-state-name,Values=running --query 'length(Reservations)'` |
| "invoke lambda function my-func" | `aws lambda invoke --function-name my-func output.json` |
