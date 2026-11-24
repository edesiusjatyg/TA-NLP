# Catatan validasi kode

Dijalankan pada 24 November 2026 dengan Python 3.12.14, PyMuPDF 1.26.6, transformers 4.57.6, tokenizers 0.22.2, dan sentencepiece 0.2.3. Sistem target Fedora milik kelompok belum diuji langsung; petunjuk dijalankan melalui lingkungan Python terpisah.

## Hasil

- Seluruh **42 uji unittest lulus**. Uji menggunakan PDF nyata dan beberapa kondisi kegagalan yang disengaja.
- Source PDF cocok SHA256 yang dikunci dan berjumlah 98 halaman.
- Inventaris memuat 98 halaman, dengan 79 halaman pengetahuan dan sembilan topik utama.
- Hasil bertokenizer memuat 455 unit aktif dan 128 chunk.
- Hitungan token dihitung ulang secara independen atas setiap input embedding. Jumlahnya cocok dengan `token_count` dalam seluruh record.
- Panjang chunk minimum 23 token, maksimum 348 token, dan rata-rata 110,59 token. Batas konfigurasi 350 token mencakup prefix `passage: ` serta special tokens.
- Build bertokenizer diulang ke folder sementara. Seluruh berkas output identik byte demi byte dengan hasil yang disertakan.
- Verifikasi checksum dan referensi unit dalam chunk lulus.

## Hal yang diuji

Uji meliputi penolakan PDF berbeda hash; pengarsipan seluruh halaman; cakupan topik; pengecualian halaman nonpengetahuan; ketiadaan fase pascabencana buatan untuk karhutla dan COVID-19; pasangan level-status gunungapi; tabel hujan; pemisahan kolom disabilitas; infografik tas siaga; perbaikan glyph terpisah; kelengkapan baris akhir isi; penandaan sumber bermasalah tanpa koreksi fakta; pasangan nama-kontak; label rambu dan nomor yang terpisah; cakupan unit dalam chunk; unit panjang yang tidak dipotong; penolakan release sebelum review; review kadaluarsa; pemeliharaan negasi/angka; reproduksi hasil; dan deteksi perubahan output.

Pesan `ERROR` pada keluaran uji deteksi perubahan file adalah kondisi negatif yang disengaja. Uji tersebut berhasil jika CLI menolak file yang telah diubah. Hasil akhir suite tetap `OK`.

## Batas bukti

Lulus uji tidak berarti seluruh isi telah disetujui kelompok atau benar menurut pengetahuan terkini. Review semantik manusia masih tertunda. Belum ada pengukuran akurasi jawaban, retrieval, faithfulness, atau performa LLM. Nilai panjang token bukan ukuran kualitas jawaban.
