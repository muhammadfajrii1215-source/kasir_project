# sinkronisasi
# ============================================================
# FILE: branch_server/sync.py
# TUJUAN: Menangani sinkronisasi data dari cabang ke server pusat
# ============================================================

import socket
import json
import time
import threading
from database import get_transaksi_pending, tandai_sudah_sync

# Konfigurasi server pusat
PUSAT_HOST = 'localhost'  # Ganti dengan IP server pusat jika beda komputer
PUSAT_PORT = 9001
KODE_CABANG = 'JKT-001'

# Interval sinkronisasi (detik)
INTERVAL_SYNC = 30


def coba_kirim_ke_pusat():
    """
    Coba kirim semua transaksi pending ke server pusat.
    
    Return:
        True  → berhasil sync
        False → gagal (offline atau error)
    """
    pending = get_transaksi_pending()

    if not pending:
        print("[SYNC] Tidak ada data pending")
        return True

    print(f"[SYNC] Ada {len(pending)} transaksi pending, mencoba kirim ke pusat...")

    try:
        # Buat koneksi ke server pusat
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((PUSAT_HOST, PUSAT_PORT))

        # Kirim data
        data_kirim = {
            'aksi': 'SYNC_DATA',
            'kode_cabang': KODE_CABANG,
            'transaksi': pending
        }
        sock.send(json.dumps(data_kirim, default=str).encode('utf-8'))

        # Terima response
        response = json.loads(sock.recv(4096).decode('utf-8'))
        sock.close()

        if response.get('sukses'):
            # Tandai semua sebagai synced
            for trx in pending:
                tandai_sudah_sync(trx['id_transaksi'])
            print(f"[SYNC] ✅ {len(pending)} transaksi berhasil disync ke pusat!")
            return True
        else:
            print(f"[SYNC] ❌ Sync gagal: {response.get('pesan')}")
            return False

    except (ConnectionRefusedError, socket.timeout, OSError):
        print("[SYNC] ⚠️  Server pusat tidak tersedia (mode offline) — data aman di lokal")
        return False
    except Exception as e:
        print(f"[SYNC] ❌ Error tidak terduga: {e}")
        return False


def jalankan_sync_otomatis():
    """
    Jalankan sinkronisasi otomatis setiap INTERVAL_SYNC detik.
    Fungsi ini dijalankan di thread terpisah (background).
    
    Analogi: Seperti alarm yang bunyi setiap 30 detik,
    mengingatkan untuk cek dan kirim laporan ke kantor pusat.
    """
    print(f"[SYNC] Thread sinkronisasi dimulai (interval: {INTERVAL_SYNC} detik)")

    while True:
        time.sleep(INTERVAL_SYNC)
        try:
            coba_kirim_ke_pusat()
        except Exception as e:
            print(f"[SYNC] Error: {e}")


def mulai_thread_sync():
    """
    Mulai thread sinkronisasi di background.
    Dipanggil dari server.py saat server pertama kali dijalankan.
    """
    thread = threading.Thread(target=jalankan_sync_otomatis, daemon=True)
    thread.start()
    return thread