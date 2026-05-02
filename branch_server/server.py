# Server lokal cabang — menerima koneksi dari aplikasi kasir

import socket
import threading
import json
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import (
    login_kasir,
    cari_produk_by_barcode,
    get_semua_produk,
    simpan_transaksi,
    get_transaksi_pending,
    tandai_sudah_sync,
    tambah_kasir
)

HOST = '0.0.0.0'
PORT = 9000

# ganti dengan IP server pusat yang sebenarnya
PUSAT_HOST = 'localhost'
PUSAT_PORT = 9001
KODE_CABANG = 'JKT-001'  # sesuaikan dengan kode cabang ini


def handle_kasir(conn_kasir, alamat_kasir):
    """Tangani satu sesi koneksi dari kasir. Berjalan di thread terpisah."""
    print(f"\n[SERVER] Kasir baru terhubung dari {alamat_kasir}")
    kasir_info = None

    try:
        while True:
            data_mentah = conn_kasir.recv(4096)
            if not data_mentah:
                print(f"[SERVER] Kasir dari {alamat_kasir} disconnect")
                break

            data = json.loads(data_mentah.decode('utf-8'))
            aksi = data.get('aksi')
            print(f"[SERVER] Terima aksi '{aksi}' dari {alamat_kasir}")

            if aksi == 'LOGIN':
                hasil = proses_login(data)
                if hasil['sukses']:
                    kasir_info = hasil['kasir']
                kirim_response(conn_kasir, hasil)

            elif aksi == 'GET_PRODUK':
                kirim_response(conn_kasir, proses_get_produk())

            elif aksi == 'SCAN_BARCODE':
                kirim_response(conn_kasir, proses_scan_barcode(data))

            elif aksi == 'REGISTER':
                kirim_response(conn_kasir, proses_register(data))

            elif aksi == 'TRANSAKSI':
                if not kasir_info:
                    kirim_response(conn_kasir, {
                        'sukses': False,
                        'pesan': 'Kasir belum login!'
                    })
                else:
                    kirim_response(conn_kasir, proses_transaksi(data, kasir_info))

            elif aksi == 'LOGOUT':
                print(f"[SERVER] Kasir '{kasir_info['username'] if kasir_info else '?'}' logout")
                kirim_response(conn_kasir, {'sukses': True, 'pesan': 'Logout berhasil'})
                break

            else:
                kirim_response(conn_kasir, {
                    'sukses': False,
                    'pesan': f"Aksi '{aksi}' tidak dikenal"
                })

    except json.JSONDecodeError:
        print(f"[ERROR] Data dari {alamat_kasir} bukan format JSON valid")
    except ConnectionResetError:
        print(f"[INFO] Koneksi dari {alamat_kasir} terputus tiba-tiba")
    except Exception as e:
        print(f"[ERROR] Error saat handle kasir {alamat_kasir}: {e}")
    finally:
        conn_kasir.close()
        print(f"[SERVER] Koneksi dengan {alamat_kasir} ditutup")


def proses_login(data):
    username = data.get('username', '')
    password = data.get('password', '')
    kasir = login_kasir(username, password)
    if kasir:
        return {
            'sukses': True,
            'pesan': f"Selamat datang, {kasir['nama_lengkap']}!",
            'kasir': kasir
        }
    return {
        'sukses': False,
        'pesan': 'Username atau password salah!'
    }


def proses_register(data):
    username = data.get('username', '')
    password = data.get('password', '')
    nama     = data.get('nama_lengkap', '')
    if not username or not password or not nama:
        return {'sukses': False, 'pesan': 'Data tidak lengkap!'}
    sukses, pesan = tambah_kasir(username, password, nama)
    return {'sukses': sukses, 'pesan': pesan}


def proses_get_produk():
    return {'sukses': True, 'produk': get_semua_produk()}


def proses_scan_barcode(data):
    barcode = data.get('barcode', '')
    produk = cari_produk_by_barcode(barcode)
    if produk:
        return {'sukses': True, 'produk': produk}
    return {'sukses': False, 'pesan': f"Produk '{barcode}' tidak ditemukan!"}


def proses_transaksi(data, kasir_info):
    items      = data.get('items', [])
    uang_bayar = data.get('uang_bayar', 0)
    if not items:
        return {'sukses': False, 'pesan': 'Tidak ada barang!'}
    id_trx = simpan_transaksi(kasir_id=kasir_info['id'], items=items, uang_bayar=uang_bayar)
    if id_trx:
        total = sum(i['harga'] * i['jumlah'] for i in items)
        return {
            'sukses': True,
            'id_transaksi': id_trx,
            'total': total,
            'kembalian': uang_bayar - total,
            'pesan': 'Transaksi berhasil!'
        }
    return {'sukses': False, 'pesan': 'Gagal simpan transaksi!'}


def kirim_response(conn, data):
    try:
        conn.send(json.dumps(data, default=str).encode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Gagal kirim response: {e}")


def thread_sinkronisasi():
    """Cek dan kirim transaksi pending ke server pusat setiap 30 detik."""
    print("[SYNC] Thread sinkronisasi dimulai")
    while True:
        try:
            time.sleep(30)
            pending = get_transaksi_pending()
            if not pending:
                continue

            print(f"[SYNC] {len(pending)} transaksi pending, mencoba kirim ke pusat...")
            try:
                sock_pusat = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock_pusat.settimeout(10)
                sock_pusat.connect((PUSAT_HOST, PUSAT_PORT))

                data_kirim = {
                    'aksi': 'SYNC_DATA',
                    'kode_cabang': KODE_CABANG,
                    'transaksi': pending
                }
                sock_pusat.send(json.dumps(data_kirim, default=str).encode('utf-8'))

                response = json.loads(sock_pusat.recv(4096).decode('utf-8'))
                if response.get('sukses'):
                    for trx in pending:
                        tandai_sudah_sync(trx['id_transaksi'])
                    print(f"[SYNC] {len(pending)} transaksi berhasil disync!")
                else:
                    print(f"[SYNC] Sync gagal: {response.get('pesan')}")

                sock_pusat.close()

            except (ConnectionRefusedError, socket.timeout):
                print("[SYNC] Server pusat tidak tersedia, akan dicoba lagi nanti")

        except Exception as e:
            print(f"[SYNC] Error: {e}")


def jalankan_server():
    print("=" * 50)
    print("  SERVER LOKAL CABANG")
    print(f"  Kode Cabang : {KODE_CABANG}")
    print(f"  Host        : {HOST}")
    print(f"  Port        : {PORT}")
    print("=" * 50)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f"\n[SERVER] Siap menerima koneksi di port {PORT}")
    print("[SERVER] Tekan Ctrl+C untuk hentikan server\n")

    # thread sinkronisasi berjalan di background
    sync_thread = threading.Thread(target=thread_sinkronisasi, daemon=True)
    sync_thread.start()

    try:
        while True:
            conn_kasir, alamat_kasir = server_socket.accept()
            thread_kasir = threading.Thread(
                target=handle_kasir,
                args=(conn_kasir, alamat_kasir),
                daemon=True
            )
            thread_kasir.start()

    except KeyboardInterrupt:
        print("\n[SERVER] Menghentikan server...")
    finally:
        server_socket.close()
        print("[SERVER] Server dihentikan")


if __name__ == "__main__":
    jalankan_server()