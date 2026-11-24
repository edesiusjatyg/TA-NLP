# Riset dan keputusan format korpus kelompok

Tanggal penelusuran 24 November 2026. Dokumen ini membedakan prinsip yang didukung referensi dari pilihan implementasi proyek. Angka konfigurasi awal bukan hasil eksperimen QA.

## Jawaban utama

Untuk proyek ini, gunakan **PDF asli sebagai bukti, JSONL sebagai data utama program, Markdown sebagai tampilan review, dan TXT sebagai ekspor sederhana**. Tidak ada satu ekstensi yang otomatis menghasilkan korpus berkualitas. Kualitas bergantung pada kecocokan sumber dengan pertanyaan, ketepatan ekstraksi, terjaganya konteks, konsistensi metadata, serta pemeriksaan yang dapat ditelusuri.

Hugging Face Datasets mendukung beberapa format, termasuk JSON, teks, CSV, dan Parquet. Dokumentasinya menyebut format JSON dengan satu objek per baris sebagai bentuk yang efisien untuk pemuatan baris data [R1]. Ini mendukung pemilihan JSONL untuk kebutuhan teknis kelompok; bukan kewajiban universal semua proyek RAG.

## Apa yang dimaksud korpus pada tugas ini

Korpus adalah kumpulan isi pengetahuan buku yang dapat dicari sistem. Contohnya definisi, penyebab, lembaga berwenang, tindakan pada fase tertentu, daftar perlengkapan, dan istilah yang benar-benar tersedia pada buku. Korpus tidak perlu diubah seluruhnya menjadi pasangan pertanyaan-jawaban.

Pisahkan tiga hal: korpus pengetahuan, indeks pencarian, dan dataset evaluasi QA. Korpus berisi isi buku; indeks berisi representasi untuk mencari isi itu; dataset QA berisi pertanyaan, gold answer, fakta wajib, dan sumber untuk menilai sistem. Embedding adalah representasi turunan, sehingga mengganti model embedding tidak mengharuskan mengganti isi buku. Kunci evaluasi tidak menjadi sumber pengetahuan tambahan.

Korpus untuk retrieval juga tidak otomatis menjadi dataset untuk melatih atau fine tune LLM. Pada tahap ini buku diproses dan diindeks, tanpa pelatihan model.

## Perbandingan format

| Format | Kelebihan untuk kelompok | Keterbatasan | Keputusan |
|---|---|---|---|
| PDF | Menyimpan tata letak, gambar, tabel, nomor halaman, dan bukti asli | Urutan teks hasil ekstraksi bisa berbeda dari urutan visual | Disimpan utuh dan dikunci hash |
| Markdown | Judul, daftar, penanda sumber, dan isi mudah dibaca atau dibandingkan | Tidak memaksa schema; metadata dapat ditulis tidak konsisten | Tampilan review yang dihasilkan dari data utama |
| TXT UTF-8 | Sangat sederhana, mudah dibuka dan diproses | Struktur dan metadata perlu aturan tambahan | Ekspor praktis dengan penanda sumber |
| JSONL UTF-8 | Setiap unit membawa field, array, angka, dan identitas sumber; mudah diproses per baris | Kurang nyaman untuk membaca paragraf panjang | Data utama untuk integrasi program |
| CSV | Mudah dibuka dalam spreadsheet dan dibagi sebagai daftar review | Array, provenance, dan teks multiline lebih rumit | Inventaris dan antrean review |
| Parquet | Dapat menjadi format tabel yang efisien pada skala lebih besar | Menambah kebutuhan tooling untuk pemeriksaan sederhana | Tidak diperlukan untuk satu buku ini |

Keputusan ini merupakan desain proyek. Kita tidak perlu menambah database vektor, Parquet, atau layanan cloud hanya untuk membentuk korpus awal. Format file tidak membatasi pilihan retrieval tim QA klasik maupun RAG.

## Bagaimana isi yang baik

### Relevan dan mencakup ruang lingkup

Kelompok telah menetapkan seluruh sembilan topik bencana pada buku. Karena itu cakupan diperiksa per topik dan materi pendukung; jumlah halaman semata bukan indikator cukup. Definisi, tindakan, fase, istilah, dan lembaga perlu tersedia sesuai isi buku. Menambahkan dokumen lain tanpa koordinasi mengubah eksperimen sumber tunggal.

### Setia pada sumber

Pembersihan merapikan representasi, bukan menulis ulang fakta. Pertahankan angka, satuan, negasi, kondisi, tempat, dan urutan yang relevan. Kalimat “jangan kembali sebelum keadaan dinyatakan aman oleh pihak berwenang” kehilangan makna jika kata “jangan”, “sebelum”, atau syarat otoritas dibuang sebagai stopword.

Untuk konteks LLM, simpan bahasa alami yang utuh. Jika tim leksikal membutuhkan lowercase, alias, stemming, atau normalisasi khusus, buat representasi tambahan dan pertahankan `clean_text` sumber. Normalisasi tidak boleh menghapus satu-satunya versi yang dibutuhkan untuk sitasi dan pemeriksaan.

### Utuh pada satuan makna

Satu unit sebaiknya dapat dipahami dengan label konteksnya. Tidak semua baris PDF adalah unit yang baik. Potongan “yang berwenang” atau “bila tidak digunakan” membutuhkan kalimat di sekitarnya. Daftar atau syarat bisa perlu disimpan bersama, sementara beberapa topik dalam satu halaman bisa perlu dipisah.

Dokumentasi Microsoft membahas pemotongan berdasarkan struktur, kalimat, dan batas input model, termasuk mempertahankan konteks judul serta memperhatikan tabel dan bagian dokumen [R2]. Untuk buku ini, implementasinya menggunakan paragraf, butir, baris tabel, dan daftar utuh yang dikelompokkan menurut halaman dan fase. Cara ini tetap perlu diuji terhadap pertanyaan kelompok.

### Tabel tidak kehilangan pasangan

Pada halaman buku 27, “IV”, “Awas”, dan penjelasannya harus berada pada baris logis yang sama. Pada halaman buku 67, daftar prabencana tidak boleh bercampur dengan daftar pascabencana hanya karena posisi y kedua kolom berdekatan. Pada tabel kontak, nama lembaga dan nomor harus dipasangkan per baris.

PyMuPDF menjelaskan bahwa urutan ekstraksi PDF dapat mengikuti penyimpanan objek, bukan urutan baca. API menyediakan blok, kata, koordinat, dan seleksi region untuk menanganinya [R3]. Karena itu pipeline menyimpan provenance spasial dan memakai recipe khusus untuk tata letak kompleks. Mengganti ekstensi PDF menjadi TXT tidak menyelesaikan persoalan tersebut.

### Ada metadata yang berguna

Setiap unit pada paket ini memuat ID, topik, fase, halaman buku dan PDF, isi, konteks, flag kualitas, serta status review. Metadata harus punya makna konsisten. `UMUM` tidak boleh dianggap sinonim “semua fase”; `pending_group_review` tidak boleh ditafsirkan sebagai persetujuan.

Metadata anotasi juga harus dibedakan dari isi buku. Contoh label field “Puncak musim hujan” membantu serialisasi tabel, tetapi bukan alasan untuk mengklaim kalimat tambahan itu merupakan kutipan literal baru.

### Terdokumentasi dan dapat dibangun ulang

Datasheets for Datasets mengusulkan dokumentasi motivasi, komposisi, pengumpulan, dan penggunaan yang disarankan [R4]. Hugging Face menjelaskan dataset card sebagai cara memberi konteks tentang isi, bahasa, lisensi, dan penggunaan dataset [R5]. Paket ini menerapkannya melalui dataset card, inventaris halaman, recipe, status review, dan manifest.

Manifest mengikat salinan PDF, kode, konfigurasi, keputusan review, dan tokenizer. Dua anggota dapat memeriksa apakah mereka menggunakan versi yang sama. Dokumen yang berbeda hash tidak diproses memakai koordinat lama tanpa pemeriksaan ulang.

## Contoh isi Markdown dan JSONL

Berikut contoh ilustratif berdasarkan jenis isi buku. Ini menunjukkan struktur penyajian, bukan item evaluasi final atau ID nyata.

```markdown
## Tsunami
### Pascabencana

Sumber: buku halaman 23, PDF halaman 25.

Anda dapat kembali ke rumah setelah keadaan dinyatakan aman
dari pihak berwenang.
```

Versi program menyimpan hal yang sama sebagai satu objek:

```json
{
  "evidence_unit_id": "contoh_saja",
  "section": "Tsunami",
  "phase_tags": ["PASCA"],
  "book_page_start": 23,
  "pdf_page_start": 25,
  "clean_text": "Anda dapat kembali ke rumah setelah keadaan dinyatakan aman dari pihak berwenang.",
  "review_status": "pending_group_review"
}
```

Objek contoh diformat multiline supaya mudah dibaca. Dalam JSONL sebenarnya, setiap objek berada dalam satu baris, dan pemisah baris di dalam string di-escape oleh serializer JSON. Field lengkap tersedia dalam `SCHEMA.md`.

## Ukuran chunk dan overlap

Tidak ada ukuran chunk yang boleh disebut paling baik untuk kelompok sebelum diuji. Batas model merupakan syarat teknis, sedangkan ukuran yang memberi retrieval dan jawaban terbaik merupakan pertanyaan eksperimen. Kita juga perlu membedakan token embedding dari token generator.

Model card multilingual E5 meminta prefix `query: ` dan `passage: `, termasuk untuk bahasa non-Inggris, dan menunjukkan batas input 512 token [R6]. Build yang disertakan memilih anggaran 350 token total, dengan label konteks, prefix, dan special tokens ikut dihitung. Nilai ini merupakan titik awal; bukan angka yang telah memenangkan eksperimen.

Baseline tidak menggunakan overlap karena unit kecil dan utuh sudah dipertahankan. Studi Bennani dan Moslonka menguji beberapa strategi pada Natural Questions dengan SPLADE dan Mistral-8B; manfaat overlap tidak terukur dalam setup mereka [R7]. Temuan tersebut tidak membuktikan overlap selalu buruk pada buku BNPB. Ia mendukung perlunya menguji, bukan mengasumsikan persentase overlap sebagai aturan tetap.

Jika bukti sering tersebar di beberapa unit, tim dapat mencoba pengambilan unit tetangga atau perbandingan konfigurasi chunk pada dev. Jangan memecah tabel atau menghapus syarat hanya untuk mencapai angka panjang yang seragam. Unit terlalu panjang ditandai dan harus ditangani, tanpa truncation diam-diam.

## Pemeriksaan praktis kelompok

1. Buka halaman PDF dan unit hasil pada topik yang sama.
2. Periksa bahwa awal dan akhir kalimat lengkap.
3. Cocokkan angka, satuan, negasi, syarat, dan lembaga.
4. Periksa apakah judul, fase, dan label konteks benar.
5. Buka kasus tabel dan infografik; baca per baris atau per kolom sesuai sumber.
6. Catat informasi historis atau sumber yang ambigu tanpa mengarang koreksi.
7. Simpan keputusan reviewer dengan hash yang sesuai.
8. Build ulang dan periksa checksum, cakupan topik, referensi unit, dan token budget.
9. Setelah pertanyaan dev tersedia, uji apakah bukti untuk pertanyaan benar-benar dapat ditemukan.
10. Bekukan versi sebelum test dan bandingkan kedua sistem pada protokol kelompok.

Korpus yang rapi belum tentu menjamin jawaban benar. Penilaian berikutnya tetap perlu memeriksa retrieval, pemilihan bukti, pembentukan jawaban, dan sitasinya secara terpisah.

## Referensi

- **R1** Hugging Face. *Datasets — Load*, bagian Local files dan JSON. https://huggingface.co/docs/datasets/loading
- **R2** Microsoft Learn. *Chunk large documents for RAG and vector search*. https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents
- **R3** PyMuPDF. *Text recipes*, khususnya reading order, blocks, words, dan rectangle extraction. https://pymupdf.readthedocs.io/en/latest/recipes-text.html
- **R4** Gebru, T. dan rekan. *Datasheets for Datasets*, versi 2021. https://arxiv.org/abs/1803.09010
- **R5** Hugging Face. *Dataset Cards*. https://huggingface.co/docs/hub/datasets-cards
- **R6** intfloat. *multilingual-e5-small model card*. https://huggingface.co/intfloat/multilingual-e5-small
- **R7** Bennani, S. dan Moslonka, C. 2026. *A Systematic Analysis of Chunking Strategies for Reliable Question Answering*. Preprint; hasil terbatas pada setup yang diuji. https://arxiv.org/abs/2601.14123
