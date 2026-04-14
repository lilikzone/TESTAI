# Agent: Guardrail

## Overview

`guardrail` adalah agent keamanan yang memvalidasi setiap query dan command sebelum dieksekusi. Agent ini memastikan tidak ada operasi berbahaya, destruktif, atau tidak sah yang lolos ke layer eksekusi.

---

## Fungsi Utama

- Menganalisis intent dari natural language query
- Mengklasifikasikan tingkat risiko setiap command
- Memblokir command yang masuk daftar hitam
- Meminta konfirmasi untuk operasi berisiko tinggi
- Mencatat semua aktivitas ke audit log

---

## Risk Classification

| Level | Deskripsi | Aksi |
|-------|-----------|------|
| `READ_ONLY` | describe, list, get | ✅ Auto-execute |
| `MODIFY` | create, update, start, stop | ⚠️ Execute dengan logging |
| `DESTRUCTIVE` | delete, terminate, purge | ❌ Require explicit confirmation |
| `BLOCKED` | Command dalam blocklist | 🚫 Hard block, tidak bisa dieksekusi |

---

## Blocklist (Hard Block)

Command berikut selalu diblokir tanpa pengecualian:

```
- aws iam delete-account
- aws organizations delete-organization
- aws ec2 terminate-instances (tanpa filter spesifik)
- aws s3 rb --force (hapus bucket beserta isinya)
- aws iam attach-user-policy (attach AdministratorAccess)
- Semua command yang mengandung "--no-confirm" pada operasi destruktif
```

---

## Input / Output

**Input:**
```json
{
  "query": "hapus semua EC2 instance",
  "translated_command": "aws ec2 terminate-instances --instance-ids $(aws ec2 describe-instances --query 'Reservations[].Instances[].InstanceId' --output text)"
}
```

**Output (BLOCKED):**
```json
{
  "allowed": false,
  "risk_level": "DESTRUCTIVE",
  "reason": "Command ini akan menghapus SEMUA EC2 instance. Operasi ini tidak dapat dibatalkan.",
  "suggestion": "Sebutkan instance ID spesifik yang ingin dihapus, contoh: 'hapus EC2 instance i-0abc123'"
}
```

**Output (ALLOWED):**
```json
{
  "allowed": true,
  "risk_level": "READ_ONLY",
  "reason": null,
  "audit_log_id": "log-20240101-001"
}
```

---

## Audit Logging

Setiap eksekusi dicatat dengan format:

```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "user_query": "...",
  "translated_command": "...",
  "risk_level": "READ_ONLY",
  "allowed": true,
  "executed_by": "system"
}
```

---

## Prinsip Keamanan

1. **Default Deny** — Jika ragu, blokir dan minta klarifikasi
2. **Least Privilege** — Hanya eksekusi yang diminta, tidak lebih
3. **Audit Everything** — Semua aktivitas dicatat
4. **No Wildcards on Destructive** — Operasi hapus harus spesifik
5. **Immutable Logs** — Audit log tidak bisa dimodifikasi
