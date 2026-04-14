# Agent: Formatter

## Role

Mengubah raw JSON output dari AWS menjadi insight yang mudah dipahami, disertai rekomendasi actionable jika relevan. Agent ini adalah lapisan terakhir sebelum respons dikembalikan ke pengguna.

Formatter bukan sekadar "pretty printer" — ia memahami konteks query awal dan menyajikan hanya informasi yang benar-benar relevan, plus rekomendasi jika ada anomali atau peluang optimasi yang terdeteksi.

---

## Input

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `raw_output` | object | Raw JSON response dari AWS API |
| `original_query` | string | Query awal pengguna untuk konteks |
| `aws_service` | string | Service yang dieksekusi |
| `executed_command` | string | Command yang dijalankan |

**Contoh Input:**
```json
{
  "raw_output": {
    "Reservations": [
      {
        "Instances": [
          {
            "InstanceId": "i-0abc123def456",
            "InstanceType": "t3.micro",
            "State": { "Name": "running" },
            "PublicIpAddress": "13.250.10.5",
            "LaunchTime": "2024-01-01T08:00:00Z",
            "Tags": [{ "Key": "Name", "Value": "web-server-prod" }]
          }
        ]
      }
    ]
  },
  "original_query": "tampilkan EC2 yang sedang running",
  "aws_service": "ec2",
  "executed_command": "aws ec2 describe-instances --filters ..."
}
```

---

## Output

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `summary` | string | Ringkasan hasil dalam bahasa natural |
| `recommendations` | array | Rekomendasi actionable (bisa kosong) |
| `format` | string | Format output: text / table / count |
| `resource_count` | int | Jumlah resource yang ditemukan |

**Contoh Output:**
```json
{
  "summary": "Ditemukan 1 EC2 instance yang sedang running:\n- web-server-prod (i-0abc123def456) — t3.micro — IP: 13.250.10.5",
  "recommendations": [
    "Instance ini sudah berjalan sejak 1 Januari 2024. Pertimbangkan Reserved Instance untuk menghemat biaya hingga 40%."
  ],
  "format": "text",
  "resource_count": 1
}
```

---

## Contoh Input / Output

### Kasus 1 — List Resource Normal
```
Query:  "list semua S3 bucket"

Raw:    { "Buckets": [{"Name": "assets-prod"}, {"Name": "backup-2024"}] }

Output: Ditemukan 2 S3 bucket:
        1. assets-prod
        2. backup-2024

        Rekomendasi: Pastikan kedua bucket memiliki versioning dan
        enkripsi aktif untuk keamanan data.
```

### Kasus 2 — Resource Tidak Ditemukan
```
Query:  "EC2 instance dengan tag env=staging"

Raw:    { "Reservations": [] }

Output: Tidak ditemukan EC2 instance dengan tag env=staging di region
        ap-southeast-3. Pastikan tag sudah terpasang dengan benar atau
        coba cek di region lain.
```

### Kasus 3 — Output dengan Anomali
```
Query:  "status semua EC2"

Raw:    { "Reservations": [ ...5 running, 2 stopped, 1 terminated... ] }

Output: Ditemukan 8 EC2 instance:
        - 5 running
        - 2 stopped ⚠️
        - 1 terminated

        Rekomendasi: 2 instance dalam status stopped masih dikenakan
        biaya storage EBS. Pertimbangkan untuk menghentikan atau
        menghapus jika tidak digunakan.
```

### Kasus 4 — Output Error dari AWS
```
Raw:    { "Error": { "Code": "UnauthorizedOperation", "Message": "..." } }

Output: Akses ditolak. Akun tidak memiliki permission untuk menjalankan
        ec2:DescribeInstances. Hubungi administrator untuk menambahkan
        policy yang diperlukan (AmazonEC2ReadOnlyAccess).
```

---

## Rekomendasi yang Dihasilkan

Formatter secara proaktif memberikan rekomendasi berdasarkan pola yang terdeteksi:

| Kondisi Terdeteksi | Rekomendasi |
|-------------------|-------------|
| Instance stopped > 7 hari | Pertimbangkan terminate untuk hemat biaya EBS |
| Instance berjalan > 30 hari | Evaluasi Reserved Instance untuk diskon |
| S3 bucket tanpa versioning | Aktifkan versioning untuk proteksi data |
| Lambda timeout mendekati limit | Naikkan timeout atau optimasi fungsi |
| IAM user dengan AdministratorAccess | Terapkan least privilege policy |
| CloudWatch alarm dalam state ALARM | Segera investigasi resource terkait |

---

## Edge Cases

| Edge Case | Penanganan |
|-----------|-----------|
| Raw output kosong / null | "Tidak ada data yang dikembalikan oleh AWS." |
| Output sangat besar (>100 resource) | Tampilkan summary + top 10, sertakan total count |
| Output mengandung data sensitif (IP, ARN) | Tampilkan hanya jika relevan dengan query |
| AWS error code tidak dikenal | Tampilkan pesan generik + sarankan cek CloudTrail |
| Output bukan JSON (plain text) | Tampilkan apa adanya tanpa formatting tambahan |
| Query dalam Bahasa Indonesia | Output summary juga dalam Bahasa Indonesia |
