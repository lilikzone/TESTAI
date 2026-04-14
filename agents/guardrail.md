# Agent: Guardrail

## Role

Memvalidasi setiap query dan command sebelum dieksekusi. Guardrail adalah lapisan keamanan wajib yang tidak bisa di-bypass — semua request harus melewati agent ini tanpa pengecualian.

Agent ini bertugas memastikan bahwa tidak ada operasi berbahaya, destruktif, atau tidak sah yang lolos ke Execution Layer, sekaligus menjaga audit trail yang lengkap untuk setiap aktivitas.

---

## Input

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `original_query` | string | Query natural language dari pengguna |
| `translated_command` | string | AWS CLI command hasil translasi |
| `risk_level` | string | Risk level dari CLI Translator |
| `user_id` | string | Identitas pengguna yang mengirim request |

**Contoh Input:**
```json
{
  "original_query": "hapus semua EC2 instance",
  "translated_command": "aws ec2 terminate-instances --instance-ids $(aws ec2 describe-instances --query 'Reservations[].Instances[].InstanceId' --output text)",
  "risk_level": "DESTRUCTIVE",
  "user_id": "user-001"
}
```

---

## Output

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `allowed` | boolean | Apakah command boleh dieksekusi |
| `risk_level` | string | Klasifikasi risiko final |
| `reason` | string | Alasan jika diblokir (null jika allowed) |
| `requires_confirmation` | boolean | Apakah perlu konfirmasi eksplisit |
| `suggestion` | string | Saran alternatif yang lebih aman |
| `audit_log_id` | string | ID log untuk tracking |

**Contoh Output (BLOCKED):**
```json
{
  "allowed": false,
  "risk_level": "DESTRUCTIVE",
  "reason": "Command ini akan menghapus SEMUA EC2 instance tanpa filter spesifik. Operasi ini tidak dapat dibatalkan.",
  "requires_confirmation": false,
  "suggestion": "Sebutkan instance ID spesifik yang ingin dihapus, contoh: 'hapus EC2 instance i-0abc123'",
  "audit_log_id": "audit-20240101-0042"
}
```

**Contoh Output (ALLOWED):**
```json
{
  "allowed": true,
  "risk_level": "READ_ONLY",
  "reason": null,
  "requires_confirmation": false,
  "suggestion": null,
  "audit_log_id": "audit-20240101-0043"
}
```

---

## Klasifikasi Risiko

| Level | Deskripsi | Aksi |
|-------|-----------|------|
| `READ_ONLY` | describe, list, get, query | ✅ Auto-execute |
| `MODIFY` | create, update, start, stop, reboot | ⚠️ Execute + audit log |
| `DESTRUCTIVE` | delete, terminate, remove, purge, drop | ❌ Require explicit confirmation |
| `BLOCKED` | Command dalam hard blocklist | 🚫 Hard block, tidak bisa dieksekusi dalam kondisi apapun |

---

## Hard Blocklist

Command berikut selalu diblokir tanpa pengecualian, bahkan dengan konfirmasi:

```
# IAM — mencegah privilege escalation
aws iam delete-account
aws iam attach-user-policy --policy-arn *AdministratorAccess*
aws iam create-login-profile (tanpa MFA requirement)

# EC2 — mencegah mass termination
aws ec2 terminate-instances (tanpa --instance-ids spesifik)
aws ec2 delete-security-group sg-default

# S3 — mencegah data loss massal
aws s3 rb --force (hapus bucket beserta seluruh isinya)
aws s3 rm s3:// --recursive (tanpa path spesifik)

# Organizations — mencegah account deletion
aws organizations delete-organization
aws organizations remove-account-from-organization

# Wildcard destruktif
Semua command yang menggunakan wildcard (*) pada operasi delete/terminate
```

---

## Approval Flow

### Flow untuk READ_ONLY
```
Request masuk
     │
     ▼
Guardrail: risk = READ_ONLY
     │
     ▼
✅ Auto-approve → Execution Layer
     │
     ▼
Audit log: ALLOWED (READ_ONLY)
```

### Flow untuk MODIFY
```
Request masuk
     │
     ▼
Guardrail: risk = MODIFY
     │
     ▼
⚠️  Execute dengan enhanced logging
     │
     ▼
Execution Layer
     │
     ▼
Audit log: ALLOWED (MODIFY) + detail perubahan
```

### Flow untuk DESTRUCTIVE
```
Request masuk
     │
     ▼
Guardrail: risk = DESTRUCTIVE
     │
     ▼
❌ Tahan eksekusi
     │
     ▼
Kirim konfirmasi ke user:
"Anda akan menghapus [resource]. Operasi ini tidak dapat dibatalkan.
 Ketik CONFIRM untuk melanjutkan atau CANCEL untuk membatalkan."
     │
     ├── User ketik CONFIRM
     │        │
     │        ▼
     │   Execution Layer
     │        │
     │        ▼
     │   Audit log: ALLOWED (DESTRUCTIVE) + konfirmasi user
     │
     └── User ketik CANCEL / timeout 60 detik
              │
              ▼
         Dibatalkan
         Audit log: CANCELLED by user
```

### Flow untuk BLOCKED
```
Request masuk
     │
     ▼
Guardrail: command ada di hard blocklist
     │
     ▼
🚫 Hard block — tidak ada flow lanjutan
     │
     ▼
Return error ke user + saran alternatif
     │
     ▼
Audit log: BLOCKED (HARD) + alert ke admin
```

---

## Contoh Input / Output

### Kasus 1 — Query Aman
```
Input:  "tampilkan semua S3 bucket"
Command: aws s3api list-buckets

Output: { "allowed": true, "risk_level": "READ_ONLY" }
```

### Kasus 2 — Query Destruktif dengan ID Spesifik
```
Input:  "hapus EC2 instance i-0abc123"
Command: aws ec2 terminate-instances --instance-ids i-0abc123

Output: {
  "allowed": false,
  "risk_level": "DESTRUCTIVE",
  "requires_confirmation": true,
  "reason": "Operasi ini akan menghapus instance i-0abc123 secara permanen.",
  "suggestion": "Ketik CONFIRM untuk melanjutkan."
}
```

### Kasus 3 — Hard Block
```
Input:  "hapus semua EC2"
Command: aws ec2 terminate-instances --instance-ids $(...)

Output: {
  "allowed": false,
  "risk_level": "BLOCKED",
  "reason": "Mass termination tanpa filter spesifik tidak diizinkan.",
  "suggestion": "Sebutkan instance ID spesifik yang ingin dihapus."
}
```

---

## Edge Cases

| Edge Case | Penanganan |
|-----------|-----------|
| Command valid tapi query terlihat berbahaya | Evaluasi berdasarkan command, bukan query |
| User mencoba bypass dengan bahasa tidak biasa | Pattern matching pada command string, bukan intent |
| Command menggunakan subshell `$()` pada operasi destruktif | Otomatis BLOCKED — subshell pada destructive command tidak diizinkan |
| Timeout konfirmasi (user tidak respons > 60 detik) | Otomatis dibatalkan, dicatat sebagai TIMEOUT |
| User mengirim CONFIRM tanpa ada pending confirmation | Diabaikan, tidak ada eksekusi |
| Command valid tapi resource tidak ada | Diizinkan — AWS akan mengembalikan error sendiri |
| Audit log service down | Eksekusi ditahan sampai logging tersedia kembali |
