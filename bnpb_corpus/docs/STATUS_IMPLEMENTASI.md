# Status implementasi

## Yang sudah dikerjakan

Pipeline Python telah dijalankan pada PDF sumber yang SHA256-nya cocok. Paket berisi hasil build aktual, bukan file kosong atau kerangka ekstraksi. Data mencakup seluruh sembilan topik utama dan materi pendukung dengan pemetaan sumber. Ekstraksi dan kurasi tidak memanggil LLM.

Kasus layout yang ditangani meliputi tabel pola hujan, organogram posko sebagai daftar label, paragraf BMKG yang terpotong antarblok, glyph awal/akhir kata terpisah, tabel status gunungapi dan KRB, indikator kualitas udara, infografik pencegahan, tas siaga, kolom disabilitas, kebutuhan hewan, kelas B3, label rambu, label aplikasi, tabel kontak, dan singkatan yang terpisah antarblok.

Jumlah hasil build bertokenizer adalah 455 unit dan 128 chunk. Semua chunk lolos batas 350 token E5 yang dihitung bersama prefix dan special tokens. Ukuran dan jumlah ini merupakan konfigurasi awal yang belum dibandingkan pada dev. Cakupan arsip 98 halaman dan pengetahuan 79 halaman. Empat puluh dua uji otomatis mencakup integritas dan regresi layout.

## Yang masih harus dikerjakan kelompok

Review manusia atas isi masih tertunda. Anggota perlu membagi tugas pemeriksaan melalui `review_queue.csv`, menyelesaikan flag sumber, mencatat kontribusi, dan membekukan versi. Kode tidak mengisi nama penanggung jawab atau mengklaim review yang belum terjadi.

Pipeline belum menghitung embedding, belum membangun TF-IDF, belum membuat extractor jawaban, dan belum menjalankan Qwen. Hal-hal itu adalah tahap sistem QA sesudah korpus. Tidak ada skor akurasi, faithfulness, retrieval, atau latency QA yang diklaim.

Data pertanyaan dan gold answer harus dibuat terpisah dengan kontribusi anggota. Sesudah data dev tersedia, kelompok dapat menilai pilihan retrieval dan ukuran chunk. Final test dilakukan pada konfigurasi yang sudah dibekukan.

## Titik awal yang disarankan

Koordinator membagikan rentang halaman untuk review. Penanggung jawab QA klasik mencoba memuat `classic_passages.jsonl`. Penanggung jawab RAG mencoba memuat `rag_chunks.jsonl` dan menggunakan snapshot tokenizer yang sama. Keduanya menyimpan ID dan versi korpus di hasilnya. Ketika ada koreksi, perbaiki recipe bersama dan build ulang sebelum melanjutkan evaluasi.
