# ============================================================
# FILE: central_server/server.py
# TUJUAN: Server pusat yang menerima sinkronisasi dari cabang-cabang
# ============================================================

import socket
import threading
import json
from database import simpan_transaksi_dari_cabang, test_koneksi

# Kunci mutex untuk database pusat
db_lock = threading.Lock()

# ---- Konfigurasi ----
HOST = '0.0.0.0'
PORT = 9001

DB_CONFIG_PUSAT = {
    'host':     'localhost',
    'user':     'root',
    'password': 'g-artyone',
    'database': 'kasir_pusat',
    'charset':  'utf8mb4'
}

def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG_PUSAT)
    except mysql.connector.Error as e:
        print(f"[PUSAT ERROR] Koneksi DB gagal: {e}")
        return None

def handle_cabang(conn, alamat):
    """Tangani satu koneksi masuk dari server cabang."""
    print(f"[PUSAT] Cabang terhubung dari {alamat}")
    try:
        data_mentah = conn.recv(65536)
        if not data_mentah:
            return

        data = json.loads(data_mentah.decode('utf-8'))
        aksi = data.get('aksi')

        if aksi == 'SYNC_DATA':
            kode_cabang    = data.get('kode_cabang')
            transaksi_list = data.get('transaksi', [])
            hasil = simpan_transaksi_dari_cabang(kode_cabang, transaksi_list)
            conn.send(json.dumps(hasil).encode('utf-8'))
        else:
            conn.send(json.dumps({
                'sukses': False, 'pesan': f"Aksi '{aksi}' tidak dikenal"
            }).encode('utf-8'))

    except Exception as e:
        print(f"[PUSAT] Error: {e}")
        try:
            conn.send(json.dumps({'sukses': False, 'pesan': str(e)}).encode('utf-8'))
        except:
            pass
    finally:
        conn.close()


def jalankan_server_pusat():
    print("=" * 50)
    print("  SERVER PUSAT")
    print(f"  Port: {PORT}")
    print("=" * 50)

    if not test_koneksi():
        print("\n❌ Server tidak bisa dimulai — database bermasalah!")
        print("   Pastikan database 'kasir_pusat' sudah dibuat.")
        return

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(10)

    print(f"\n[PUSAT] ✅ Siap menerima sinkronisasi di port {PORT}")
    print("[PUSAT] Tekan Ctrl+C untuk hentikan\n")

    try:
        while True:
            conn, alamat = srv.accept()
            t = threading.Thread(target=handle_cabang, args=(conn, alamat), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[PUSAT] Server dihentikan")
    finally:
        srv.close()

if __name__ == "__main__":
    jalankan_server_pusat()