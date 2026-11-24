# Korpus bersama QA Bencana BNPB

Versi kode **0.1.1** telah diaudit; lihat `docs/AUDIT_BUG_v0_1_1.md` untuk bug yang diperbaiki dan hasil pengujiannya.

Paket ini berisi **kode pembentukan korpus dan hasil build yang sudah dijalankan** untuk kelompok Tugas Akhir Pemrosesan Bahasa Alami. Satu salinan buku BNPB digunakan bersama oleh QA tanpa LLM dan QA RAG. Tidak ada model generatif, pelatihan model, atau kunci jawaban evaluasi yang disisipkan ke korpus.

**Mulai dengan membuka `outputs/corpus.md` atau `outputs/review.html`.** Untuk integrasi program, gunakan `outputs/classic_passages.jsonl` dan `outputs/rag_chunks.jsonl`.

## Hasil yang tersedia

- Seluruh **98 halaman PDF** diarsipkan dalam hasil ekstraksi mentah.
- **79 halaman pengetahuan** digunakan; sampul, pengantar, kredit, halaman pembatas, formulir, peta tanpa narasi, halaman kosong, dan catatan tidak masuk indeks pengetahuan.
- **455 unit bukti** dengan nomor PDF, nomor buku, topik, fase, ID, provenance, dan status review.
- Build bertokenizer E5 yang disertakan menghasilkan **128 chunk**; seluruhnya berada dalam batas **350 token**, termasuk label konteks, prefix `passage: `, dan special tokens.
- Sembilan topik utama dan materi pendukung, termasuk disabilitas, vegetasi, hewan, B3, rambu, aplikasi, kontak, dan singkatan.
- Pemeriksaan otomatis dan **42 uji otomatis** tersedia.

Angka chunk dapat berubah ketika parameter atau kurasi berubah. Statistik aktual selalu ada pada `outputs/validation_report.json`.

**Status: korpus pengembangan.** Pemeriksaan struktur dan perbaikan tata letak sudah dilakukan. Seluruh unit masih berstatus `pending_group_review`; belum ada persetujuan manusia atas nama anggota kelompok. Skor QA dan kualitas retrieval belum diukur. Ini bukan korpus final yang telah direview kelompok.

## Menjalankan di Fedora Linux

Ekstrak ZIP, buka terminal, lalu masuk ke folder yang berisi `corpus.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-tokenizer.txt
python corpus.py build --tokenizer data/tokenizers/multilingual-e5-small --local-only --max-tokens 350
python corpus.py verify
python -m unittest discover -s tests -v
```

Python minimal 3.10. Build korpus menggunakan CPU; RTX 4060, Ollama, dan LLM tidak diperlukan pada tahap ini. Instalasi dependensi memerlukan internet. PDF dan tokenizer yang cocok sudah disertakan, sehingga build di atas tidak perlu mengunduh sumber atau bobot model. Tokenizer bukan embedding model; paket ini **tidak** menyertakan bobot E5 atau Qwen.

Jika hanya ingin mencoba ekstraksi tanpa dependensi tokenizer:

```bash
python -m pip install -r requirements.txt
python corpus.py build --out outputs_word_budget --max-words 160
```

Build tersebut memakai jumlah kata, sehingga `token_limit_verified=false`. Hasilnya tidak boleh diklaim sudah memenuhi batas token E5. Build awal yang ada dalam `outputs/` memakai tokenizer asli.

## Berkas yang dipakai setiap peran

| Kebutuhan | Berkas | Fungsi |
|---|---|---|
| Memeriksa sumber | `data/raw/buku_saku_bnpb.pdf` | Salinan asli dengan SHA256 dikunci |
| Membaca korpus | `outputs/corpus.md` | Teks bersih dan metadata untuk review |
| Membaca teks sederhana | `outputs/corpus.txt` | Ekspor praktis dengan penanda sumber |
| Audit hasil ekstraksi | `outputs/pages_raw.jsonl` | Seluruh halaman, teks mentah, baris, kata, koordinat |
| Dasar pengetahuan bersama | `outputs/evidence_units.jsonl` | Seluruh unit, termasuk status dan provenance |
| QA tanpa LLM | `outputs/classic_passages.jsonl` | Unit aktif untuk indexing dan ekstraksi jawaban |
| QA RAG | `outputs/rag_chunks.jsonl` | Chunk dari unit yang sama, tanpa melintasi fase atau halaman |
| Koordinasi kurasi | `outputs/review_queue.csv` | Daftar tugas pemeriksaan, dapat dibuka di spreadsheet |
| Inventaris buku | `outputs/page_inventory.csv` | Keputusan penggunaan setiap halaman |
| Audit build | `outputs/build_manifest.json` | Versi, parameter, identitas tokenizer, checksum hasil |

`clean_text` menyimpan teks sumber yang sudah dirapikan. `retrieval_text` menambahkan label konteks terpisah agar unit seperti manfaat bakau tidak kehilangan nama tanamannya. Label ini adalah anotasi, bukan kutipan baru dari buku. CSV bukan sumber utama program karena array dan metadata bersarang lebih mudah dijaga dalam JSONL.

## Perintah praktis

```bash
python corpus.py stats
python corpus.py inspect --page 29
python corpus.py inspect --contains "tas"
python corpus.py render-pages --pages 29,30,67,69 --dpi 150
python corpus.py fetch-source
```

`fetch-source` menggunakan satu URL resmi yang sudah dikunci, tidak menimpa PDF yang berbeda, dan menolak unduhan dengan hash berbeda. Gunakan kembali PDF yang disertakan bila versi di situs sudah berubah.

`verify` memeriksa hasil **dan input pembentuknya**: PDF, konfigurasi, recipe, keputusan review, tokenizer lokal, serta kode. Perubahan pada salah satunya membuat hasil dianggap kedaluwarsa sampai dibangun ulang. Tokenizer lokal yang ditulis dengan path relatif selalu dicari dari root proyek, sehingga CLI bisa dipanggil dari folder terminal lain.

## Mengoreksi korpus

1. Temukan unit melalui `inspect` atau `review_queue.csv`.
2. Bandingkan dengan halaman PDF, terutama angka, negasi, syarat, kolom, dan pasangan label-nilai.
3. Untuk mengubah ekstraksi, edit `data/curation/recipes.json`; untuk mengubah kategori halaman atau fase, edit `configs/page_plan.json`.
4. `text_override` hanya untuk perbaikan transkripsi yang jelas, wajib disertai `note`. Jangan mengisi informasi yang tidak ada pada sumber.
5. Build ulang dengan perintah tokenizer di atas. Versi korpus berubah otomatis.
6. Catat keputusan review atas ID hasil terbaru.

Contoh berikut memakai placeholder `ID_UNIT` dan `Nama Reviewer`; ganti dengan ID dan reviewer sebenarnya setelah pemeriksaan:

```bash
python corpus.py review --unit-id ID_UNIT --decision approved --reviewer "Nama Reviewer" --note "Teks, fase, angka, dan halaman cocok dengan PDF"
python corpus.py build --tokenizer data/tokenizers/multilingual-e5-small --local-only --max-tokens 350
```

Jika bagian sumber tidak layak digunakan, gunakan `--decision excluded` dengan alasan. Unit tetap ada di arsip bukti tetapi tidak diekspor ke passage aktif atau chunk. Jika reviewer mempertahankan unit berflag kritis, jelaskan perlakuannya dalam `--note` dan sebutkan flag melalui `--accept-flags`. Persetujuan terikat hash isi dan metadata: perubahan teks, konteks, fase, flag, atau provenance membatalkan penggunaan review lama.

Setelah seluruh keputusan review lengkap:

```bash
python corpus.py build --tokenizer data/tokenizers/multilingual-e5-small --local-only --max-tokens 350 --release --out release
```

Perintah release menolak unit yang belum direview, flag kritis yang belum ditangani, hilangnya salah satu dari sembilan topik, atau chunk yang tidak lolos token budget. Penolakan pada paket awal memang diharapkan karena review kelompok belum dilakukan.

**Jangan mengedit `outputs/` secara langsung.** Hasil di sana akan dibentuk ulang. Koreksi dilakukan melalui recipe dan keputusan review agar perubahan dapat direproduksi. Jangan menjalankan beberapa penulisan `reviews.json` bersamaan; gabungkan perubahan anggota melalui Git atau satu koordinator, lalu build ulang.

Unit `excluded` dikeluarkan dari semua ekspor pengetahuan, termasuk Markdown dan TXT. Arsip `evidence_units.jsonl`, antrean CSV, dan halaman HTML review tetap menyimpannya beserta status agar keputusan dapat diaudit. Build disiapkan di folder sementara; kegagalan penulisan tidak mencampurkan berkas lama dan baru. Folder input dan folder lain yang bukan hasil build dilindungi dari penimpaan.

## Batas cakupan implementasi

Tahap ini membangun korpus, bukan keseluruhan aplikasi QA. Tim QA klasik masih perlu membuat analisis pertanyaan, retrieval, extractor, dan fallback. Tim RAG masih perlu menghitung embedding, membuat retrieval, menyusun prompt, dan menjalankan LLM lokal. Kelompok juga perlu menyusun pertanyaan dev/test beserta gold answer secara terpisah.

Jangan mengindeks semua file proyek secara rekursif: masukkan hanya file passage/chunk yang telah dipilih. `docs/`, `tests/`, `DATASET_CARD.md`, `review_queue.csv`, dan kunci QA bukan sumber jawaban tambahan.

Lihat `docs/RISET_FORMAT_KORPUS.md` untuk alasan pemilihan format, prinsip isi yang baik, dan referensi; `docs/SCHEMA.md` untuk kontrak data; serta `DATASET_CARD.md` untuk cakupan dan keterbatasan sumber.
