# ============================================================
# FILE: central_server/server.py
# TUJUAN: Server pusat yang menerima sinkronisasi dari cabang-cabang
# ============================================================

import socket
import threading
import json
import mysql.connector
from datetime import datetime

# Kunci mutex untuk database pusat
db_lock = threading.Lock()

# ---- Konfigurasi ----
HOST = '0.0.0.0'
PORT = 9001

DB_CONFIG_PUSAT = {
    'host':     'localhost',
    'user':     'root',
    'password': 'admin123',
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
    """Tangani satu koneksi dari server cabang."""
    print(f"[PUSAT] Cabang terhubung dari {alamat}")
    try:
        data_mentah = conn.recv(65536)  # Terima sampai 64KB (data bisa besar)
        if not data_mentah:
            return

        data = json.loads(data_mentah.decode('utf-8'))
        aksi = data.get('aksi')

        if aksi == 'SYNC_DATA':
            hasil = proses_sync(data)
            conn.send(json.dumps(hasil).encode('utf-8'))
        else:
            conn.send(json.dumps({'sukses': False, 'pesan': 'Aksi tidak dikenal'}).encode('utf-8'))

    except Exception as e:
        print(f"[PUSAT ERROR] {e}")
        try:
            conn.send(json.dumps({'sukses': False, 'pesan': str(e)}).encode('utf-8'))
        except:
            pass
    finally:
        conn.close()

def proses_sync(data):
    """Simpan data transaksi dari cabang ke database pusat."""
    with db_lock:
        kode_cabang   = data.get('kode_cabang')
        transaksi_list = data.get('transaksi', [])

        db = get_connection()
        if not db:
            return {'sukses': False, 'pesan': 'Koneksi DB pusat gagal'}

        try:
            cursor = db.cursor()

            # Cari ID cabang berdasarkan kode
            cursor.execute("SELECT id FROM cabang WHERE kode_cabang = %s", (kode_cabang,))
            row = cursor.fetchone()
            if not row:
                return {'sukses': False, 'pesan': f"Cabang '{kode_cabang}' tidak ditemukan!"}

            cabang_id = row[0]
            berhasil  = 0

            for trx in transaksi_list:
                # Cek duplikat (kalau sudah pernah di-sync sebelumnya)
                cursor.execute(
                    "SELECT id FROM transaksi_pusat WHERE id_transaksi = %s AND cabang_id = %s",
                    (trx['id_transaksi'], cabang_id)
                )
                if cursor.fetchone():
                    continue  # Skip, sudah ada

                # Simpan transaksi
                cursor.execute("""
                    INSERT INTO transaksi_pusat
                        (id_transaksi, cabang_id, kasir_username,
                         total_harga, uang_bayar, kembalian, waktu_transaksi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    trx['id_transaksi'],
                    cabang_id,
                    trx.get('kasir_username', '-'),
                    trx['total_harga'],
                    trx.get('uang_bayar', 0),
                    trx.get('kembalian', 0),
                    trx['waktu_transaksi']
                ))

                # Simpan detail
                for detail in trx.get('detail', []):
                    cursor.execute("""
                        INSERT INTO detail_transaksi_pusat
                            (id_transaksi, cabang_id, nama_produk,
                             harga_satuan, jumlah, subtotal)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        trx['id_transaksi'],
                        cabang_id,
                        detail['nama_produk'],
                        detail['harga_satuan'],
                        detail['jumlah'],
                        detail['subtotal']
                    ))

                berhasil += 1

            db.commit()
            print(f"[PUSAT] ✅ Sync dari cabang {kode_cabang}: {berhasil} transaksi diterima")
            return {'sukses': True, 'pesan': f'{berhasil} transaksi berhasil disimpan'}

        except Exception as e:
            db.rollback()
            print(f"[PUSAT ERROR] {e}")
            return {'sukses': False, 'pesan': str(e)}
        finally:
            cursor.close()
            db.close()

def jalankan_server_pusat():
    print("=" * 50)
    print("  SERVER PUSAT")
    print(f"  Port: {PORT}")
    print("=" * 50)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(10)

    print(f"[PUSAT] Siap menerima sinkronisasi di port {PORT}\n")

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