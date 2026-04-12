# ============================================================
# FILE: branch_server/server.py
# TUJUAN: Server lokal cabang — menerima koneksi dari kasir
# 
# Analogi: Ini seperti "kepala toko" yang:
# - Duduk di kantor belakang
# - Menunggu laporan dari kasir-kasir
# - Proses setiap laporan
# - Simpan ke database lokal
# - Kirim ke pusat kalau ada koneksi
# ============================================================

import socket        # Untuk komunikasi jaringan
import threading     # Untuk handle banyak kasir sekaligus
import json          # Untuk kirim/terima data dalam format JSON
import time          # Untuk delay/sleep
import sys           # Untuk info sistem
import os            # Untuk akses file/folder

# Import fungsi-fungsi database yang sudah kita buat
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import (
    login_kasir,
    cari_produk_by_barcode,
    get_semua_produk,
    simpan_transaksi,
    get_transaksi_pending,
    tandai_sudah_sync
)

# ============================================================
# KONFIGURASI SERVER
# ============================================================
HOST = '0.0.0.0'   # '0.0.0.0' = terima koneksi dari mana saja di jaringan lokal
PORT = 9000         # Nomor pintu (port) yang dibuka
                    # Kasir akan konek ke port ini

# Konfigurasi server PUSAT (untuk sinkronisasi)
PUSAT_HOST = 'localhost'  # ← Ganti dengan IP server pusat kalau sudah ada
PUSAT_PORT = 9001
KODE_CABANG = 'JKT-001'   # ← Ganti sesuai kode cabang ini


# ============================================================
# FUNGSI HANDLE SETIAP KASIR
# Fungsi ini dipanggil di THREAD TERPISAH untuk setiap kasir
# ============================================================

def handle_kasir(conn_kasir, alamat_kasir):
    """
    Menangani satu koneksi kasir.
    
    Setiap kasir yang konek ke server ini akan ditangani
    oleh satu thread terpisah.
    
    Analogi: Bayangkan ada 3 loket bank.
    Setiap nasabah dilayani di loket sendiri secara bersamaan.
    Tidak perlu antri! Setiap loket = satu thread.
    
    Parameter:
        conn_kasir  : Objek koneksi socket ke kasir
        alamat_kasir: Tuple (IP, port) kasir
    """
    print(f"\n[SERVER] Kasir baru terhubung dari {alamat_kasir}")
    
    kasir_info = None  # Menyimpan info kasir yang sedang login
    
    try:
        while True:  # Loop terus, melayani request dari kasir ini
            
            # -----------------------------------------------
            # TERIMA DATA DARI KASIR
            # -----------------------------------------------
            data_mentah = conn_kasir.recv(4096)
            # recv(4096) = terima data maksimal 4096 byte
            # Ini seperti "mendengarkan" apa yang kasir kirimkan
            
            if not data_mentah:
                # Kalau data kosong, kasir sudah disconnect
                print(f"[SERVER] Kasir dari {alamat_kasir} disconnect")
                break
            
            # Decode: ubah bytes → string → dictionary Python
            data = json.loads(data_mentah.decode('utf-8'))
            # json.loads = "JSON to Python object"
            # .decode('utf-8') = ubah bytes jadi string
            
            aksi = data.get('aksi')  # Apa yang diminta kasir?
            print(f"[SERVER] Terima aksi '{aksi}' dari {alamat_kasir}")
            
            # -----------------------------------------------
            # PROSES BERDASARKAN AKSI
            # -----------------------------------------------
            
            if aksi == 'LOGIN':
                # Kasir minta login
                hasil = proses_login(data)
                if hasil['sukses']:
                    kasir_info = hasil['kasir']
                kirim_response(conn_kasir, hasil)
            
            elif aksi == 'GET_PRODUK':
                # Kasir minta daftar semua produk
                hasil = proses_get_produk()
                kirim_response(conn_kasir, hasil)
            
            elif aksi == 'SCAN_BARCODE':
                # Kasir scan barcode
                hasil = proses_scan_barcode(data)
                kirim_response(conn_kasir, hasil)
            
            elif aksi == 'TRANSAKSI':
                # Kasir minta simpan transaksi
                if not kasir_info:
                    kirim_response(conn_kasir, {
                        'sukses': False,
                        'pesan': 'Kasir belum login!'
                    })
                else:
                    hasil = proses_transaksi(data, kasir_info)
                    kirim_response(conn_kasir, hasil)
            
            elif aksi == 'LOGOUT':
                # Kasir logout
                print(f"[SERVER] Kasir '{kasir_info['username'] if kasir_info else '?'}' logout")
                kirim_response(conn_kasir, {'sukses': True, 'pesan': 'Logout berhasil'})
                break  # Keluar dari loop
            
            else:
                # Aksi tidak dikenal
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
        conn_kasir.close()  # Pastikan koneksi ditutup
        print(f"[SERVER] Koneksi dengan {alamat_kasir} ditutup")


# ============================================================
# FUNGSI-FUNGSI PEMROSES AKSI
# ============================================================

def proses_login(data):
    """Proses request login dari kasir."""
    username = data.get('username', '')
    password = data.get('password', '')
    
    kasir = login_kasir(username, password)
    
    if kasir:
        return {
            'sukses': True,
            'pesan': f"Selamat datang, {kasir['nama_lengkap']}!",
            'kasir': kasir
        }
    else:
        return {
            'sukses': False,
            'pesan': 'Username atau password salah!'
        }


def proses_get_produk():
    """Proses request daftar produk."""
    produk_list = get_semua_produk()
    return {
        'sukses': True,
        'produk': produk_list
    }


def proses_scan_barcode(data):
    """Proses request scan barcode."""
    barcode = data.get('barcode', '')
    produk = cari_produk_by_barcode(barcode)
    
    if produk:
        return {
            'sukses': True,
            'produk': produk
        }
    else:
        return {
            'sukses': False,
            'pesan': f"Produk dengan barcode '{barcode}' tidak ditemukan!"
        }


def proses_transaksi(data, kasir_info):
    """Proses penyimpanan transaksi baru."""
    items     = data.get('items', [])
    uang_bayar = data.get('uang_bayar', 0)
    
    if not items:
        return {'sukses': False, 'pesan': 'Tidak ada barang!'}
    
    id_trx = simpan_transaksi(
        kasir_id=kasir_info['id'],
        items=items,
        uang_bayar=uang_bayar
    )
    
    if id_trx:
        total = sum(i['harga'] * i['jumlah'] for i in items)
        return {
            'sukses': True,
            'id_transaksi': id_trx,
            'total': total,
            'kembalian': uang_bayar - total,
            'pesan': 'Transaksi berhasil!'
        }
    else:
        return {'sukses': False, 'pesan': 'Gagal simpan transaksi!'}


def kirim_response(conn, data):
    """
    Kirim response ke kasir dalam format JSON.
    
    Analogi: Seperti kasir yang menjawab pertanyaan pelanggan.
    """
    try:
        pesan = json.dumps(data, default=str)
        # json.dumps = "Python object to JSON string"
        # default=str = kalau ada tipe data aneh (datetime dll), ubah ke string
        
        conn.send(pesan.encode('utf-8'))
        # .encode('utf-8') = ubah string ke bytes (yang bisa dikirim lewat jaringan)
    except Exception as e:
        print(f"[ERROR] Gagal kirim response: {e}")


# ============================================================
# THREAD SINKRONISASI
# Berjalan di background, cek dan kirim data ke pusat secara berkala
# ============================================================

def thread_sinkronisasi():
    """
    Thread yang berjalan terus di background.
    Setiap 30 detik, coba kirim data pending ke server pusat.
    
    Analogi: Seperti pegawai yang setiap 30 menit
    cek apakah ada laporan yang perlu dikirim ke kantor pusat.
    Kalau ada dan koneksi tersedia, langsung kirim.
    Kalau tidak ada koneksi, tunggu sampai ada.
    """
    print("[SYNC] Thread sinkronisasi dimulai")
    
    while True:
        try:
            time.sleep(30)  # Tunggu 30 detik sebelum cek lagi
            
            # Ambil semua transaksi yang belum disync
            pending = get_transaksi_pending()
            
            if not pending:
                print("[SYNC] Tidak ada data pending")
                continue  # Lanjut ke iterasi berikutnya (tidur 30 detik lagi)
            
            print(f"[SYNC] Ada {len(pending)} transaksi pending, mencoba kirim ke pusat...")
            
            # Coba konek ke server pusat
            try:
                sock_pusat = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # AF_INET = IPv4
                # SOCK_STREAM = TCP (koneksi yang andal)
                
                sock_pusat.settimeout(10)  # Timeout 10 detik
                sock_pusat.connect((PUSAT_HOST, PUSAT_PORT))
                
                # Kirim data ke pusat
                data_kirim = {
                    'aksi': 'SYNC_DATA',
                    'kode_cabang': KODE_CABANG,
                    'transaksi': pending
                }
                
                pesan = json.dumps(data_kirim, default=str)
                sock_pusat.send(pesan.encode('utf-8'))
                
                # Terima konfirmasi dari pusat
                response_raw = sock_pusat.recv(4096)
                response = json.loads(response_raw.decode('utf-8'))
                
                if response.get('sukses'):
                    # Tandai semua transaksi yang berhasil di-sync
                    for trx in pending:
                        tandai_sudah_sync(trx['id_transaksi'])
                    print(f"[SYNC] ✅ {len(pending)} transaksi berhasil disync!")
                else:
                    print(f"[SYNC] ❌ Sync gagal: {response.get('pesan')}")
                
                sock_pusat.close()
                
            except (ConnectionRefusedError, socket.timeout):
                print("[SYNC] ⚠️  Server pusat tidak tersedia (mode offline)")
                # Tidak perlu panik, data aman di database lokal
                # Akan dicoba lagi 30 detik kemudian
                
        except Exception as e:
            print(f"[SYNC] Error: {e}")


# ============================================================
# FUNGSI UTAMA — Jalankan Server
# ============================================================

def jalankan_server():
    """
    Jalankan server lokal cabang.
    
    Yang terjadi di sini:
    1. Buka socket (buka "pintu" untuk kasir)
    2. Mulai thread sinkronisasi di background
    3. Loop terus: tunggu kasir, spawn thread baru per kasir
    """
    print("=" * 50)
    print("  SERVER LOKAL CABANG")
    print(f"  Kode Cabang : {KODE_CABANG}")
    print(f"  Host        : {HOST}")
    print(f"  Port        : {PORT}")
    print("=" * 50)
    
    # Buat socket server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # SO_REUSEADDR = izinkan pakai ulang port yang sama
    # (berguna saat server direstart, port tidak perlu tunggu lama)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Ikat socket ke HOST dan PORT
    server_socket.bind((HOST, PORT))
    
    # Mulai mendengarkan koneksi masuk
    # backlog=5 = maksimal 5 koneksi yang antri
    server_socket.listen(5)
    
    print(f"\n[SERVER] Siap menerima koneksi di port {PORT}")
    print("[SERVER] Tekan Ctrl+C untuk hentikan server\n")
    
    # Mulai thread sinkronisasi di background
    # daemon=True = thread ini akan ikut mati kalau program utama ditutup
    sync_thread = threading.Thread(target=thread_sinkronisasi, daemon=True)
    sync_thread.start()
    
    try:
        while True:  # Loop utama: terus terima koneksi kasir baru
            
            # Tunggu kasir konek (ini BLOCKING = program berhenti di sini
            # sampai ada kasir yang konek)
            conn_kasir, alamat_kasir = server_socket.accept()
            
            # Kasir konek! Buat thread baru khusus untuk kasir ini
            # Analogi: Buka loket baru khusus untuk pelanggan ini
            thread_kasir = threading.Thread(
                target=handle_kasir,      # Fungsi yang dijalankan thread ini
                args=(conn_kasir, alamat_kasir),  # Parameter fungsi
                daemon=True
            )
            thread_kasir.start()
            
            # Langsung kembali ke loop untuk tunggu kasir berikutnya
            # Thread kasir tadi berjalan sendiri di background!
            
    except KeyboardInterrupt:
        # Ctrl+C ditekan
        print("\n[SERVER] Menghentikan server...")
    finally:
        server_socket.close()
        print("[SERVER] Server dihentikan")


# Jalankan server kalau file ini dieksekusi langsung
if __name__ == "__main__":
    jalankan_server()