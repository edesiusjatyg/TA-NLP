# Kontrak data korpus

## Empat representasi yang berbeda

`pages_raw.jsonl` adalah arsip hasil ekstraksi semua halaman. `evidence_units.jsonl` adalah unit pengetahuan bersama dengan provenance dan status review. `classic_passages.jsonl` serta `rag_chunks.jsonl` merupakan turunan untuk masing-masing sistem. `corpus.md`, `corpus.txt`, dan `review.html` adalah tampilan untuk manusia, bukan berkas yang diedit sebagai sumber kurasi.

JSONL berarti setiap baris adalah satu objek JSON valid. Array metadata tetap array, angka tetap angka, `null` berarti tidak ada nilai. Jangan membaca seluruh JSONL memakai `json.load`; baca per baris dengan `json.loads`.

## Unit bukti

| Field | Makna |
|---|---|
| `evidence_unit_id` | ID yang menggabungkan hash sumber, halaman, urutan, dan hash teks |
| `content_sha256` | Identitas isi dan metadata penting untuk mengikat keputusan review |
| `corpus_version` | Identitas seluruh konfigurasi build dan kurasi |
| `document_id`, `source_sha256` | Buku dan salinan PDF yang tepat |
| `pdf_page_start`, `pdf_page_end` | Nomor halaman PDF berbasis satu |
| `book_page_start`, `book_page_end` | Nomor tercetak pada buku |
| `section`, `subsection`, `context_label` | Bab, bagian, dan konteks tambahan |
| `hazard_tags`, `material_tags` | Topik bencana dan kategori materi pendukung |
| `phase_tags` | Array berisi `PRA`, `SAAT`, `PASCA`, atau `UMUM` |
| `clean_text` | Isi sumber yang dinormalisasi, bukan jawaban model |
| `retrieval_text` | Label konteks ditambah isi untuk indexing |
| `unit_type` | Paragraf, item, tabel, infografik, kontak, atau istilah |
| `table_cells` | Pasangan field dan nilai bila sumber diserialisasi sebagai tabel |
| `source_fragments` | ID baris, koordinat, dan teks asal yang menyusun unit |
| `annotation_type`, `transformation_notes` | Cara dan alasan pemrosesan |
| `source_quality_flag` | Array penanda masalah sumber atau konteks historis |
| `review_status`, `review` | Status dan catatan pemeriksaan manusia |

Koordinat `bbox=[x0,y0,x1,y1]` menggunakan point pada halaman PDF dengan origin kiri atas. Fragmen region dapat berupa sebagian baris sumber karena seleksi dilakukan atas pusat kata. `raw_text` pada fragmen region adalah kata terpilih sebelum normalisasi. Arsip halaman menyimpan teks mentah asli dan seluruh baris agar perbedaannya dapat diperiksa.

`UMUM` berarti isi pengenalan/lintas fase atau tidak dinyatakan sebagai fase spesifik. Ini tidak menyatakan bahwa isi otomatis berlaku pada semua fase. Fase mengikuti struktur sumber; sistem pertanyaan tetap harus membaca konteksnya.

## Chunk RAG

Setiap chunk menyimpan `chunk_id`, daftar `evidence_unit_ids`, sumber halaman, topik, fase, teks, status review, dan flag. `clean_text` persis gabungan teks unit dalam urutan yang tercatat. `retrieval_text` juga memiliki label konteks.

`token_count` bernilai angka hanya bila tokenizer asli digunakan; nilainya mencakup prefix embedding dan special tokens. Pada build berbasis kata, nilainya `null`, sementara `word_count` tetap tersedia. `exceeds_budget=true` berarti tidak boleh menganggap chunk aman untuk embedding tanpa penanganan. Tidak ada pemotongan diam-diam.

Saat embedding E5, gunakan `chunk['embedding_prefix'] + chunk['retrieval_text']` tepat satu kali. Saat menyusun konteks LLM, gunakan isi dan label yang sesuai; prefix embedding tidak perlu disalin sebagai instruksi. Jangan mencampur token_count E5 dengan token_count Qwen karena tokenizer keduanya berbeda.

`chunk_id` mengidentifikasi komposisi unit dan konfigurasi chunking; `corpus_version` tetap harus dipakai bersama ID. Review dan perubahan metadata dapat mengubah versi tanpa mengubah susunan ID unit.

`material_tags` dipertahankan pada unit bukti, passage klasik, dan chunk RAG. Contohnya `DISABILITAS`, `VEGETASI`, atau `HEWAN` dapat digunakan untuk menemukan materi pendukung tanpa mengubah `hazard_tags=["UMUM"]` menjadi jenis bencana baru. Manifest v0.1.1 mencatat hash seluruh input serta fingerprint isi tokenizer. Persetujuan review juga terikat pada `material_tags` dan `unit_type`.

## Contoh membaca

```python
import json
from pathlib import Path

def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

passages = read_jsonl("outputs/classic_passages.jsonl")
chunks = read_jsonl("outputs/rag_chunks.jsonl")

# Input untuk TF-IDF atau retrieval leksikal tim QA klasik.
texts_classic = [row["retrieval_text"] for row in passages]

# Input untuk encoder E5, tanpa mengubah clean_text sumber.
texts_embedding = [row["embedding_prefix"] + row["retrieval_text"] for row in chunks]

# Simpan pemetaan indeks vektor -> chunk_id -> evidence_unit_ids -> halaman.
lookup = {row["chunk_id"]: row for row in chunks}
```

Untuk persiapan development boleh memakai unit pending dengan status tersebut terlihat. Evaluasi final menggunakan versi yang review dan konfigurasinya telah dibekukan bersama kelompok. Jangan menyamakan `pending_group_review` dengan `approved`.
