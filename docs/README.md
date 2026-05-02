# Sistem Kasir Multi Cabang

Aplikasi kasir berbasis desktop (Tkinter) yang terhubung ke server lokal cabang dan server pusat. Dirancang untuk digunakan di lingkungan multi-cabang dengan sinkronisasi data otomatis.

---

## Cara Menjalankan

### 1. Jalankan Server Pusat

Server pusat menerima data sinkronisasi dari semua cabang. Jalankan ini **paling pertama**.

```bash
cd central_server
python server.py
```

Server akan berjalan di port `9001`. Biarkan jendela terminal ini tetap terbuka.

---

### 2. Jalankan Server Lokal (di komputer cabang)

Server lokal menjadi perantara antara aplikasi kasir dan server pusat.

```bash
cd branch_server
python server.py
```

Server akan berjalan di port `9000`. Biarkan jendela terminal ini tetap terbuka.

> **Catatan:** Sebelum menjalankan, sesuaikan `PUSAT_HOST` di `branch_server/server.py` dengan IP server pusat, dan `KODE_CABANG` dengan kode cabang yang sesuai.

---

### 3. Jalankan Aplikasi Kasir

Setelah kedua server di atas sudah berjalan, buka aplikasi kasir:

```bash
cd cashier_app
python main.py
```

Jendela login akan muncul. Masukkan username dan password kasir untuk mulai bertransaksi.

---

## Struktur Folder

```
kasir_project/
├── central_server/      # Server pusat (sinkronisasi data)
│   ├── server.py
│   └── database.py
├── branch_server/       # Server lokal cabang
│   ├── server.py
│   └── database.py
├── cashier_app/         # Aplikasi kasir (GUI)
│   └── main.py
├── database/            # Script SQL untuk setup database
└── docs/
    └── README.md
```

---

## Konfigurasi Database

- **Server lokal** menggunakan database `kasir_lokal`
- **Server pusat** menggunakan database `kasir_pusat`

Sesuaikan host, username, dan password MySQL di file `database.py` masing-masing folder.

---

## Urutan Setup Awal

1. Install dependensi: `pip install -r requirements.txt`
2. Buat database MySQL sesuai script di folder `database/`
3. Jalankan server pusat
4. Jalankan server lokal cabang
5. Jalankan aplikasi kasir
