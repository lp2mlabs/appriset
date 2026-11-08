# WebImage Studio — revisi 2

Pengembang Dr, Muhamad · [muhamad@iprija.ac.id](mailto:muhamad@iprija.ac.id)

Tampilan menggunakan tema abu-abu dan hitam. Tombol simpan laporan sudah dihapus.

Aplikasi Windows 10/11 64-bit untuk kompresi gambar website. Berjalan offline, tanpa akun dan tanpa Python di komputer pemakai.

## Memulai

1. Buka `WebImage Studio.exe` di folder `release`.
2. Tarik gambar/folder ke area hijau, atau tekan **Pilih gambar**. Tombol **+ Folder** juga menyertakan subfolder.
3. Pilih format **Otomatis**, **WebP**, **AVIF**, atau **Tetap ekstensi semula**. Mode otomatis mengodekan AVIF/WebP dan memilih hasil terkecil pada pengaturan kualitas yang dipilih. Angka kualitas antarformat bukan ukuran kualitas visual yang identik.
4. Pilih resolusi, orientasi, dan mode resize. Folder hasil selalu terlihat di panel kanan, di atas tombol kompres. Default-nya adalah subfolder **WebImage Studio** di folder **Gambar/Pictures** Windows (termasuk jika Pictures diarahkan ke OneDrive). Gunakan **Ubah folder hasil…** untuk memilih lokasi lain pada sesi ini. Folder dibuat saat kompresi dimulai.
5. Tekan **Kompres semua gambar**. Pilih baris untuk melihat gambar asli dan hasil, lalu **Buka hasil** untuk membuka folder.

## Ukuran, orientasi, dan resolusi

- Orientasi: **Landscape**, **Portrait**, **Persegi**, serta lebar/tinggi kustom hingga 12000 px per sisi.
- Preset: HD 1280×720, Full HD 1920×1080, 2K DCI 2048×1080, QHD 2560×1440, 4K UHD 3840×2160, Website 1600×900, dan Sosial 1350×1080 (landscape) / 1080×1350 (portrait).
- **Muat seluruh gambar**: mempertahankan seluruh isi dan proporsi. Kotak yang dipilih merupakan batas maksimum, bukan jaminan ukuran persis. Contoh: sumber 3000×2000 dengan kotak 1920×1080 menghasilkan 1620×1080.
- **Potong tengah**: memotong bagian tengah agar mengikuti proporsi/ukuran pilihan. Periksa pratinjau karena bagian tepi dapat terbuang.
- **Izinkan memperbesar** secara bawaan mati. Sumber kecil tidak diperbesar. Jika mode potong membutuhkan sumber lebih besar, ukuran kotak diperkecil secara proporsional (dapat selisih 1 piksel akibat pembulatan).
- Pilih **Asli · tanpa resize** untuk mempertahankan resolusi setelah koreksi orientasi EXIF.
- Resolusi memakai piksel; DPI cetak tidak menentukan ukuran gambar di website.

## Kualitas dan target KB

- **Tetap ekstensi semula** mempertahankan format dan ekstensi setiap sumber, termasuk `.jpeg`, `.tif`, serta huruf besar/kecil. Ini adalah pengodean ulang dalam format yang sesuai, bukan mengganti nama file AVIF/WebP. Masukan campuran tetap memiliki format masing-masing.
- Pada mode tersebut, JPEG memakai optimasi kualitas/progressive, PNG memakai optimasi lossless, TIFF memakai deflate lossless, WebP/AVIF mengikuti kualitas pilihan. BMP tidak memiliki kompresi efisien; pengurangan ukurannya terutama berasal dari resize.

- Kualitas 25–100, bawaan 80. Nilai tinggi umumnya menghasilkan file lebih besar.
- Target KB opsional (1 KB = 1024 byte). Untuk JPEG/WebP/AVIF, aplikasi mencari kualitas tertinggi yang diuji dan memenuhi target, antara 25 dan kualitas maksimum pilihan. PNG/TIFF dioptimasi lossless; BMP disimpan pada resolusi hasil. Resolusi tidak dikurangi lagi oleh target KB.
- Jika target tidak mungkin dicapai dalam rentang itu, hasil terkecil yang diuji tetap disimpan dan ditandai **Target belum tercapai**. Turunkan resolusi atau naikkan target, lalu proses lagi.
- Penghematan dihitung dari byte asli dan byte hasil. Nilai negatif berarti hasil lebih besar daripada sumber. Hasil konversi tetap disimpan pada format pilihan.
- Tidak ada persentase penghematan yang dijamin; hasil bergantung pada isi, format awal, resolusi, dan kualitas.
- Angka kualitas 100 bukan jaminan lossless untuk semua format. WebP pada kualitas 100 memakai lossless; AVIF memakai encoder kualitas 100.

## Perlindungan file dan privasi

- Hasil diberi nama `nama-web-LEBARxTINGGI` dengan ekstensi sesuai pilihan: AVIF/WebP atau ekstensi semula. Jika sudah ada, angka ditambahkan. File asli dan hasil sebelumnya tidak ditimpa.
- Transparansi dipertahankan; gambar dengan profil warna dikonversi ke sRGB. EXIF/GPS tidak disalin ke hasil.
- Antrean dapat dibatalkan. Pembatalan menunggu satu pekerjaan encoder aktif selesai; file yang sudah selesai tetap tersimpan. Jika sedang memproses, tunggu pembatalan selesai sebelum menutup jendela.
- Setelah selesai, status menampilkan lokasi hasil. Gunakan **Buka hasil** untuk membuka foldernya.
- Pilihan **Bersihkan** dan **Hapus pilihan** membersihkan antrean, bukan menghapus file pada disk.
- Seluruh proses lokal. Aplikasi tidak mengunggah file atau membuat koneksi jaringan.

## Format dan batasan

Masukan: JPG/JPEG, PNG, WebP, AVIF, BMP, TIFF statis. Animasi dan gambar multihalaman ditolak dengan keterangan. HEIC, RAW, SVG, dan GIF belum didukung. Batas sumber 80 megapiksel. Masukan HDR/bit depth tinggi diproses menjadi RGB/RGBA 8-bit untuk penggunaan web.

## Source dan build ulang

Source lengkap ada bersama proyek, termasuk `app.py`, `engine.py`, dan pengujian.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Build memakai PyInstaller. Jalankan `build.ps1` dari Windows 64-bit dengan Python 3.12+ dan paket requirements. Tidak perlu memasang dependensi pada komputer pengguna aplikasi EXE. Dependensi build dapat diunduh sekali; aplikasi hasil build berjalan offline.

Lihat `THIRD-PARTY-NOTICES.md` dan folder lisensi untuk komponen pihak ketiga.
