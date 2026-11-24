# Dataset card Korpus QA Bencana BNPB

## Tujuan dan komposisi

Korpus pengetahuan berbahasa Indonesia untuk membangun dan mengevaluasi dua sistem tugas kuliah: QA tanpa LLM dan QA dengan RAG serta LLM lokal. Dokumen acuan kelompok adalah `Acuan_Kelompok_QA_Bencana_BNPB_v1_1.docx`. Paket ini merealisasikan tahap persiapan korpus; pilihan ukuran chunk merupakan konfigurasi awal yang masih dapat diuji pada dev.

Sumber tunggal: **Buku Saku Tanggap Tangkas Tangguh Menghadapi Bencana**, diterbitkan Pusat Data, Informasi dan Komunikasi Kebencanaan BNPB. Salinan 98 halaman PDF berasal dari [domain resmi BNPB](https://bnpb.go.id/storage/app/media/Buku%20BNPB/Buku%20Saku%20Bencana%20BNPB.pdf), diambil 24 November 2026. SHA256 dan identitasnya ada pada `configs/source.json`.

Halaman kredit mencatat riwayat cetakan hingga Maret 2019, sedangkan isi memuat perkembangan pada 2020. Paket tidak menetapkan salinan ini sebagai edisi terbaru atau memberi satu tahun edisi yang tidak dapat dipastikan. Bahasa adalah Indonesia, dengan beberapa istilah dan label bahasa Inggris.

## Cakupan

| Topik | Halaman buku | Halaman PDF |
|---|---|---|
| Gempa bumi | 14–17 | 16–19 |
| Tsunami | 18–24 | 20–26 |
| Erupsi gunungapi | 25–31 | 27–33 |
| Banjir | 32–39 | 34–41 |
| Tanah longsor | 40–44 | 42–46 |
| Puting beliung | 45–48 | 47–50 |
| Kekeringan | 49–52 | 51–54 |
| Kebakaran hutan dan lahan | 53–56 | 55–58 |
| Pandemi COVID-19 | 57–60 | 59–62 |

Materi pendukung meliputi ancaman geologi dan hidrometeorologi, kelembagaan, posko, kesiapsiagaan umum, disabilitas, vegetasi, hewan peliharaan, B3, rambu, aplikasi, kontak, dan singkatan. Topik pendukung diberi `hazard_tags=["UMUM"]` dan `material_tags` tersendiri. Tidak semua risiko yang disebut sekilas menjadi bab bencana tambahan.

Seluruh 98 halaman diarsipkan; 79 halaman dipilih sebagai pengetahuan. Peta tanpa narasi, halaman pembatas, sampul, pengantar, kredit, formulir identitas kosong, dan lembar catatan tidak menjadi unit faktual. Nomor buku dan PDF disimpan bersamaan. Hubungan +2 hanya dipakai pada bagian buku yang berpenomoran, bukan pada semua halaman secara membabi buta.

## Pemrosesan dan anotasi

Ekstraksi memakai PyMuPDF 1.26.6 pada tingkat halaman, baris, dan kata. Proses tidak memanggil LLM. Teks sumber disimpan sebelum normalisasi. NFKC merapikan ligatur dan spasi, sementara angka, negasi, satuan, kondisi, dan isi sumber dipertahankan. Nama kategori dan label konteks adalah anotasi yang terpisah dari teks buku.

Halaman kompleks menggunakan recipe koordinat yang telah diperiksa terhadap tampilannya. Contohnya tabel hujan, status gunungapi, KRB, tas siaga, disabilitas, kebutuhan hewan, B3, rambu, aplikasi, dan kontak. Transkripsi atau perbaikan urutan baca tercatat melalui `text_override` dan `note`; fragmen sumber tetap tersedia.

Unit dapat berupa paragraf, butir daftar, daftar dengan syarat, baris tabel, atau label infografik. Unit bukan selalu satu kalimat atau satu klaim atomik. Beberapa daftar dipertahankan bersama supaya syarat dan hubungan tidak hilang. Chunk RAG menggabungkan unit utuh hanya dalam halaman, fase, konteks, subbagian, dan kelompok flag yang sama. Tidak ada overlap pada build awal; ini pilihan baseline, bukan klaim paling optimal.

Tokenizer E5 dibundel tanpa bobot model, pada revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Panjang diperiksa atas `passage: ` + `retrieval_text`, termasuk special tokens, tanpa truncation. Apabila sebuah unit sendiri terlalu panjang, kode mempertahankannya, memberi flag budget, dan menolak release sampai ditangani. GPU tidak diperlukan.

## Status review dan kualitas

Build awal berisi 455 unit dan 128 chunk bertokenizer. Seluruh unit masih `pending_group_review`. Inspeksi tata letak, pemeriksaan integritas, dan uji regresi kode tidak menggantikan review manusia atau pengujian QA. Tidak ada nama reviewer kelompok yang dibuat atau persetujuan yang diasumsikan.

Masalah sumber yang diketahui:

- Beberapa angka atau istilah pada halaman buku 26 dan 43 diragukan dan diberi `DUBIOUS_SOURCE`; isi tidak dikoreksi diam-diam.
- Rentang kualitas udara pada halaman buku 54 beririsan pada nilai batas. Semua baris dipertahankan dan diberi `SOURCE_AMBIGUOUS`; kode tidak membuat klasifikator batas numerik.
- Butir 11 pencegahan COVID-19 pada halaman buku 60 berakhir dengan kalimat tidak lengkap. Diberi `INCOMPLETE_SOURCE`, tanpa melengkapi kelanjutannya.
- Karhutla tidak mempunyai subbagian pascabencana tersendiri. COVID-19 berfokus pada pencegahan dan tidak mempunyai subbagian saat/pasca tersendiri. Metadata tidak menciptakan fase yang tidak ada.
- Nomor telepon, alamat, aplikasi, peraturan, dan panduan kesehatan adalah isi salinan buku. Keberadaannya tidak membuktikan keaktifan atau kesesuaiannya saat ini.

Korpus ditujukan untuk QA atas isi buku tetap, dengan sumber halaman. Tidak mewakili informasi bencana terkini, kondisi lapangan, peringatan langsung, atau pengetahuan medis terbaru. Pernyataan tentang vegetasi tidak boleh diperluas menjadi jaminan perlindungan mutlak.

## Evaluasi dan kebocoran

Korpus pengetahuan tidak dibagi menjadi train/dev/test. Pertanyaan evaluasi dan gold answer nantinya yang dibagi sesuai protokol kelompok. Jawaban yang berasal dari buku memang berada dalam knowledge corpus; hal itu adalah fungsi retrieval. Kunci QA yang ditulis untuk evaluasi tidak boleh dimasukkan sebagai dokumen pengetahuan baru. Tidak ada QA sintetis atau fine tuning pada paket ini.

Kualitas retrieval, ketepatan jawaban, dan pengaruh ukuran chunk belum diukur. Verifikasi otomatis hanya memeriksa struktur, provenance, referensi ID, cakupan topik, penomoran halaman, checksum, dan aturan fase/chunk.

## Hak dan pemeliharaan

Hak atas buku tetap pada pemilik sumber. Lisensi redistribusi buku tidak ditentukan dari salinan ini; paket tidak menyatakan buku berlisensi MIT atau mengubah atribusinya. Informasi MIT pada snapshot tokenizer merujuk model card E5, bukan buku BNPB.

Kelompok bertanggung jawab memeriksa unit, mencatat reviewer dan keputusan, mengelola versi, serta memperbarui acuan ketika sumber atau metode berubah. Perubahan `configs`, recipe, keputusan review, versi ekstraktor, atau konfigurasi chunk menghasilkan identitas korpus baru. Hash output memungkinkan anggota memastikan mereka memakai artefak yang sama.
