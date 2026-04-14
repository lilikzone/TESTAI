# Agent: Formatter

## Overview

`formatter` adalah agent yang bertanggung jawab mengubah raw output dari AWS (biasanya JSON verbose) menjadi teks ringkas dan mudah dipahami oleh pengguna non-teknis.

---

## Fungsi Utama

- Menerima raw JSON output dari eksekusi AWS CLI / Boto3
- Mengidentifikasi informasi penting yang relevan dengan query awal
- Merangkum output menjadi kalimat natural yang informatif
- Menyajikan data dalam format tabel jika diperlukan

---

## Input / Output

**Input:**
```json
{
  "raw_output": {
    "Reservations": [
      {
        "Instances": [
          {
            "InstanceId": "i-0abc123",
            "InstanceType": "t3.micro",
            "State": { "Name": "running" },
            "PublicIpAddress": "13.250.x.x"
          }
        ]
      }
    ]
  },
  "original_query": "tampilkan EC2 yang running"
}
```

**Output:**
```json
{
  "summary": "Ditemukan 1 EC2 instance yang sedang running:\n- i-0abc123 (t3.micro) — IP: 13.250.x.x",
  "format": "text"
}
```

---

## Prompt yang Digunakan

Lihat: [`../prompts/formatter.txt`](../prompts/formatter.txt)

---

## Format Output yang Didukung

| Format | Kapan Digunakan |
|--------|----------------|
| `text` | Default, untuk semua response |
| `table` | Ketika output berupa list resource |
| `json` | Ketika user meminta raw data |
| `count` | Ketika query berupa pertanyaan jumlah |

---

## Contoh Formatting

**Raw AWS Output:**
```json
{ "Buckets": [{"Name": "my-bucket-1"}, {"Name": "my-bucket-2"}] }
```

**Formatted Output:**
```
Ditemukan 2 S3 bucket:
1. my-bucket-1
2. my-bucket-2
```

---

## Prinsip Formatting

- Gunakan bahasa yang sama dengan query pengguna (Indonesia/Inggris)
- Tampilkan hanya informasi yang relevan dengan query
- Sertakan jumlah resource jika berupa list
- Highlight informasi kritis (status error, resource tidak ditemukan)
