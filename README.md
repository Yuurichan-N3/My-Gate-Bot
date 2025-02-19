# 🚀 MyGate Enhanced Bot

MyGate Enhanced Bot adalah skrip otomatisasi yang membantu login dan mengelola node di MyGate Network dengan fitur proxy, WebSocket handling, dan multi-threading.

## ✨ Fitur
- **Auto-login ke MyGate** dengan beberapa akun
- **Dukungan proxy** (manual & otomatis dari daftar online)
- **WebSocket connection handler** dengan auto-reconnect
- **Logging interaktif** menggunakan `rich`
- **Multi-threading** untuk meningkatkan kinerja

## 🛠 Instalasi & Penggunaan

### 1️⃣ Install Dependencies
Pastikan Python 3.8+ sudah terinstal, lalu jalankan:

```bash
pip install -r requirements.txt
```

### 2️⃣ Siapkan Data

data.txt → Masukkan token akun MyGate (satu token per baris).

proxy.txt (opsional) → Masukkan daftar proxy jika menggunakan proxy manual.


### 3️⃣ Jalankan Bot

```
python bot.py
```

Ikuti petunjuk di terminal untuk konfigurasi proxy dan jumlah thread.

## ⚙ Konfigurasi

Saat pertama kali berjalan, bot akan menanyakan mode proxy:

1. Gunakan proxy gratis (otomatis dari GitHub)


2. Gunakan proxy pribadi (dari proxy.txt)


3. Tanpa proxy



Kemudian, kamu bisa memilih jumlah thread (1-50) untuk menjalankan akun secara paralel.

## 📝 Catatan

Proses login dan koneksi WebSocket menggunakan sesi asinkron (aiohttp).

Pastikan proxy yang digunakan valid dan berfungsi dengan baik.

