# Audit bug versi 0.1.1

Audit dilakukan pada 24 November 2026. Perbaikan ditujukan pada integritas korpus, proses review, pemrosesan chunk, dan penggunaan CLI. Isi faktual buku tidak dikoreksi atau ditambah melalui audit kode ini.

## Bug yang ditemukan dan diperbaiki

| Masalah | Dampak sebelumnya | Perbaikan |
|---|---|---|
| Verifikasi hanya memeriksa file hasil | PDF, recipe, konfigurasi, atau review bisa berubah sementara `verify` masih sukses | Manifest menyimpan fingerprint input; verifikasi menolak artefak yang kedaluwarsa |
| Review tidak memeriksa perubahan recipe atau konfigurasi | Keputusan bisa dicatat atas hasil yang belum dibangun ulang | Input dan output diperiksa sebelum review; beberapa keputusan review tetap dapat dicatat sebelum build berikutnya |
| Unit excluded masih muncul di Markdown dan TXT | Dokumen pengetahuan bisa memuat isi yang telah ditolak | Semua ekspor pengetahuan menyaring excluded; arsip bukti dan halaman review tetap mempertahankannya |
| Cakupan chunk memakai set | Pengulangan chunk atau unit tidak terdeteksi | ID chunk dan frekuensi unit diperiksa; satu unit aktif harus terwakili tepat sekali |
| Metadata materi pendukung hilang di passage/chunk | Filter seperti DISABILITAS dan VEGETASI tidak tersedia di turunan kedua sistem | `material_tags` diteruskan secara konsisten |
| Path tokenizer relatif terhadap working directory terminal | CLI gagal ketika dipanggil dari folder lain | Path lokal diselesaikan dari root proyek |
| Identitas tokenizer remote/lokal belum sepenuhnya mengikat isi backend | Perubahan tokenizer berpotensi tidak tercermin pada versi korpus | Fingerprint backend, special tokens, batas model, dan revision snapshot dicatat; identitas tidak bergantung lokasi absolut checkout |
| Penulisan output langsung ke folder hasil | Kegagalan tulis berpotensi meninggalkan gabungan berkas lama dan baru | Ekspor disiapkan di folder sementara, diverifikasi, lalu folder hasil diganti; tersedia rollback pada kegagalan penggantian |
| Perlindungan output hanya membandingkan direktori yang persis sama | Subfolder raw/config/kurasi atau folder tak terkait dapat dipilih sebagai output | Lokasi input, kode, tokenizer, ancestor, dan folder non-build dilindungi |
| Manifest ikut menghitung berkas pribadi lain sebagai hasil generator | Perubahan catatan pribadi mengganggu verifikasi | Manifest hanya memuat sepuluh file hasil yang didefinisikan; file lain tetap dipertahankan |
| Salah ketik status review, fase, atau flag tidak ditolak | Metadata keliru dapat masuk korpus atau melemahkan pengecekan flag kritis | Nilai metadata dan struktur review divalidasi; hash persetujuan mengikat kategori materi serta jenis unit |
| Link PDF pada HTML diasumsikan selalu satu tingkat folder | Review HTML rusak pada output bertingkat atau PDF pada lokasi lain | Link dihitung relatif terhadap lokasi PDF dan output sebenarnya |
| Halaman nol pada inspect dianggap tidak ada filter | Perintah tanpa sengaja menampilkan semua halaman | Halaman di luar 1–98 ditolak |
| Render tidak memeriksa hash sumber | Review visual dapat menggunakan salinan buku yang berbeda | Render menolak PDF yang tidak cocok dengan sumber terkunci |

## Bukti pengujian

Suite berisi **42 pengujian yang seluruhnya lulus**, terdiri atas 20 pengujian sebelumnya dan 22 pengujian audit tambahan. Dua pengujian audit memakai dependensi tokenizer opsional yang benar-benar terpasang saat audit.

Kasus awal telah direproduksi: perubahan konfigurasi masih menghasilkan exit code sukses pada verify/review; unit excluded masih ada dalam TXT/Markdown; dan validator menerima chunk duplikat. Uji regresi baru memastikan ketiganya ditolak atau ditangani sesuai kontrak.

Pengujian tambahan mencakup kegagalan penulisan yang disimulasikan setelah sebagian file disiapkan, pemeliharaan snapshot build lama, folder output yang keliru, perubahan PDF/review, typo metadata, kategori materi pendukung, serta pemanggilan CLI dari working directory berbeda dengan tokenizer lokal.

Kegagalan tulis yang disimulasikan tidak mengubah satu byte pun dari hasil sebelumnya. Uji tersebut tidak menyimulasikan kerusakan perangkat keras atau pemadaman sistem.

## Dampak pada data

Dengan keputusan review kelompok tetap kosong, korpus masih memuat **455 unit, 128 chunk bertokenizer, dan sembilan topik utama**. Versi dan ID chunk berubah karena fingerprint konfigurasi tokenizer diperkuat; anggota harus membangun ulang indeks dari paket baru dan menyimpan versi korpus yang baru bersama hasilnya.

Metadata yang disetujui manusia pada versi lama perlu diperiksa ulang bila hash isinya berubah. Paket yang disertakan tetap tidak mengklaim persetujuan anggota kelompok. Review semantik manusia dan pengujian sistem QA berada di luar bukti lulusnya suite kode ini.
