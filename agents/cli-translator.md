# Agent: CLI Translator

## Role

Mengubah natural language input dari pengguna menjadi AWS CLI command yang valid, spesifik, dan siap dieksekusi. Agent ini adalah jembatan antara intent manusia dan sintaks teknis AWS.

Agent ini **tidak mengeksekusi** command — hanya menghasilkan string command yang kemudian divalidasi oleh Guardrail sebelum diteruskan ke Execution Layer.

---

## Input

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `query` | string | Natural language dari pengguna (ID/EN) |
| `aws_region` | string | Region target, default `ap-southeast-3` |
| `account_id` | string | AWS Account ID untuk konteks |
| `session_context` | object | Resource yang disebutkan sebelumnya dalam sesi |

**Contoh Input:**
```json
{
  "query": "tampilkan semua EC2 instance yang sedang running",
  "aws_region": "ap-southeast-3",
  "account_id": "123456789012",
  "session_context": {}
}
```

---

## Output

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `command` | string | AWS CLI command yang valid |
| `service` | string | AWS service yang digunakan |
| `action` | string | Tipe aksi (read / modify / destructive) |
| `risk_level` | string | READ_ONLY / MODIFY / DESTRUCTIVE |
| `confidence` | float | Tingkat keyakinan AI (0.0 – 1.0) |

**Contoh Output:**
```json
{
  "command": "aws ec2 describe-instances --filters Name=instance-state-name,Values=running --output json --region ap-southeast-3",
  "service": "ec2",
  "action": "describe-instances",
  "risk_level": "READ_ONLY",
  "confidence": 0.97
}
```

---

## Risk

Kesalahan translasi dapat berdampak serius jika tidak ditangani dengan benar:

| Skenario Risiko | Contoh | Dampak |
|----------------|--------|--------|
| Command terlalu luas | `terminate-instances` tanpa filter | Menghapus semua instance |
| Service salah | Query S3 diterjemahkan ke EC2 | Eksekusi gagal atau data salah |
| Parameter hilang | Lupa `--region` | Eksekusi di region yang salah |
| Typo pada resource ID | `i-0abc` vs `i-0abcd` | Resource tidak ditemukan |

Semua output dari agent ini wajib melewati **Guardrail Agent** sebelum dieksekusi.

---

## Contoh Input / Output

### Kasus 1 — Query Sederhana
```
Input:  "list semua S3 bucket"
Output: aws s3api list-buckets --output json
```

### Kasus 2 — Query dengan Filter
```
Input:  "EC2 mana yang pakai tipe t3.micro?"
Output: aws ec2 describe-instances
          --filters Name=instance-type,Values=t3.micro
          --query 'Reservations[].Instances[].{ID:InstanceId,State:State.Name}'
          --output json --region ap-southeast-3
```

### Kasus 3 — Query Multi-Parameter
```
Input:  "Lambda function mana yang runtime-nya Python dan sudah lebih dari 128MB memory?"
Output: aws lambda list-functions
          --query 'Functions[?Runtime==`python3.11` && MemorySize>`128`]'
          --output json --region ap-southeast-3
```

### Kasus 4 — Query Ambigu
```
Input:  "hapus yang lama"
Output: CLARIFY: Resource apa yang ingin dihapus? Sebutkan tipe resource
        (EC2, S3, Lambda) dan kriteria "lama" yang dimaksud (usia, tanggal, tag).
```

---

## Edge Cases

| Edge Case | Penanganan |
|-----------|-----------|
| Query tidak menyebut service spesifik | AI menginfer dari konteks, jika tidak bisa → `CLARIFY` |
| Query dalam Bahasa Indonesia campur Inggris | Tetap diproses, output selalu AWS CLI standar |
| Resource ID disebutkan sebagian | AI melengkapi jika memungkinkan, atau minta konfirmasi |
| Query meminta data dari multiple service | Dipecah menjadi beberapa command terpisah |
| Query mengandung kata destruktif tanpa ID spesifik | Otomatis di-flag sebagai `DESTRUCTIVE`, dikirim ke Guardrail |
| Confidence < 0.7 | Output disertai flag `low_confidence: true`, user diminta konfirmasi |
