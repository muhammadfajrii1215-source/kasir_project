# Fungsi-fungsi database untuk server lokal cabang

import mysql.connector
import threading
from datetime import datetime
import uuid

# mutex untuk cegah race condition saat banyak kasir transaksi bersamaan
db_lock = threading.Lock()

DB_CONFIG = {
    'host':     'localhost',
    'user':     'root',
    'password': 'g-artyone',   # sesuaikan dengan password MySQL kamu
    'database': 'kasir_lokal',
    'charset':  'utf8mb4'
}


def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal konek ke database: {e}")
        return None


def test_koneksi():
    print("=" * 50)
    print("Testing koneksi ke MySQL...")
    print("=" * 50)
    conn = get_connection()
    if conn:
        print("[OK] Berhasil terhubung ke MySQL!")
        print(f"   Host    : {DB_CONFIG['host']}")
        print(f"   Database: {DB_CONFIG['database']}")
        conn.close()
        return True
    else:
        print("[FAIL] Gagal terhubung ke MySQL!")
        print("   Pastikan:")
        print("   1. MySQL Server sudah berjalan")
        print("   2. Username dan password benar")
        print("   3. Database 'kasir_lokal' sudah dibuat")
        return False


def cari_produk_by_barcode(barcode):
    """Cari satu produk berdasarkan barcode. Return dict produk atau None."""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM produk WHERE barcode = %s", (barcode,))
        return cursor.fetchone()
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal cari produk: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_semua_produk():
    """Ambil semua produk, diurutkan A-Z."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM produk ORDER BY nama_produk")
        return cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal ambil produk: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def kurangi_stok(produk_id, jumlah):
    """
    Kurangi stok produk dengan mutex — aman untuk banyak kasir sekaligus.
    Contoh: stok 5, kasir A dan B beli bersamaan → hasilnya 3, bukan 4.
    """
    with db_lock:
        conn = get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT stok FROM produk WHERE id = %s", (produk_id,))
            hasil = cursor.fetchone()
            if not hasil:
                print(f"[ERROR] Produk ID {produk_id} tidak ditemukan!")
                return False
            stok_sekarang = hasil[0]
            if stok_sekarang < jumlah:
                print(f"[ERROR] Stok tidak cukup! Stok: {stok_sekarang}, Diminta: {jumlah}")
                return False
            cursor.execute(
                "UPDATE produk SET stok = stok - %s WHERE id = %s",
                (jumlah, produk_id)
            )
            conn.commit()
            print(f"[INFO] Stok produk ID {produk_id} dikurangi {jumlah}")
            return True
        except mysql.connector.Error as e:
            conn.rollback()
            print(f"[ERROR] Gagal kurangi stok: {e}")
            return False
        finally:
            cursor.close()
            conn.close()


def buat_id_transaksi():
    """Buat ID transaksi unik. Format: TRX-YYYYMMDD-XXXXXXXX"""
    tanggal = datetime.now().strftime('%Y%m%d')
    unik = str(uuid.uuid4())[:8]
    return f"TRX-{tanggal}-{unik}"


def simpan_transaksi(kasir_id, items, uang_bayar):
    """
    Simpan satu transaksi lengkap ke database.
    Pakai mutex agar transaksi bersifat atomik — semua berhasil atau semua batal.
    """
    with db_lock:
        conn = get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            total = sum(item['harga'] * item['jumlah'] for item in items)
            kembalian = uang_bayar - total
            id_trx = buat_id_transaksi()

            cursor.execute("""
                INSERT INTO transaksi
                    (id_transaksi, kasir_id, total_harga, uang_bayar, kembalian)
                VALUES
                    (%s, %s, %s, %s, %s)
            """, (id_trx, kasir_id, total, uang_bayar, kembalian))

            for item in items:
                subtotal = item['harga'] * item['jumlah']
                cursor.execute("""
                    INSERT INTO detail_transaksi
                        (id_transaksi, produk_id, nama_produk,
                         harga_satuan, jumlah, subtotal)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                """, (
                    id_trx,
                    item['produk_id'],
                    item['nama'],
                    item['harga'],
                    item['jumlah'],
                    subtotal
                ))
                cursor.execute(
                    "UPDATE produk SET stok = stok - %s WHERE id = %s",
                    (item['jumlah'], item['produk_id'])
                )

            conn.commit()
            print(f"[OK] Transaksi {id_trx} berhasil disimpan!")
            print(f"   Total   : Rp {total:,.0f}")
            print(f"   Bayar   : Rp {uang_bayar:,.0f}")
            print(f"   Kembali : Rp {kembalian:,.0f}")
            return id_trx

        except mysql.connector.Error as e:
            conn.rollback()
            print(f"[ERROR] Gagal simpan transaksi: {e}")
            return None
        finally:
            cursor.close()
            conn.close()


def get_transaksi_pending():
    """Ambil transaksi yang belum disinkronisasi ke server pusat."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                t.id_transaksi,
                t.kasir_id,
                t.total_harga,
                t.uang_bayar,
                t.kembalian,
                t.waktu_transaksi,
                k.username AS kasir_username
            FROM transaksi t
            JOIN kasir k ON t.kasir_id = k.id
            WHERE t.status_sync = 'pending'
            ORDER BY t.waktu_transaksi ASC
        """)
        transaksi_list = cursor.fetchall()

        # tambahkan detail barang untuk setiap transaksi
        for trx in transaksi_list:
            cursor.execute(
                "SELECT * FROM detail_transaksi WHERE id_transaksi = %s",
                (trx['id_transaksi'],)
            )
            trx['detail'] = cursor.fetchall()

        return transaksi_list

    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal ambil transaksi pending: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def tandai_sudah_sync(id_transaksi):
    """Ubah status transaksi menjadi 'synced' setelah berhasil dikirim ke pusat."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transaksi
            SET status_sync = 'synced'
            WHERE id_transaksi = %s
        """, (id_transaksi,))
        conn.commit()
        return True
    except mysql.connector.Error as e:
        conn.rollback()
        print(f"[ERROR] Gagal update status sync: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def login_kasir(username, password):
    """
    Cek kredensial kasir. Return dict data kasir atau None kalau gagal.
    Catatan: password masih plain text, bisa ditingkatkan pakai bcrypt nanti.
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, nama_lengkap
            FROM kasir
            WHERE username = %s
              AND password = %s
              AND aktif = 1
        """, (username, password))
        return cursor.fetchone()
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal login: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def tambah_kasir(username, password, nama_lengkap):
    """Daftarkan kasir baru. Return tuple (sukses: bool, pesan: str)."""
    conn = get_connection()
    if not conn:
        return False, "Gagal koneksi ke database"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM kasir WHERE username = %s", (username,))
        if cursor.fetchone():
            return False, f"Username '{username}' sudah terdaftar!"
        cursor.execute("""
            INSERT INTO kasir (username, password, nama_lengkap, aktif)
            VALUES (%s, %s, %s, 1)
        """, (username, password, nama_lengkap))
        conn.commit()
        print(f"[DB] Kasir baru terdaftar: {username}")
        return True, "Pendaftaran berhasil!"
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal daftar kasir: {e}")
        return False, f"Error database: {e}"
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  TEST DATABASE LOKAL")
    print("="*50 + "\n")

    if not test_koneksi():
        print("\nHentikan program. Perbaiki koneksi dulu!")
        exit()

    print()
    print("📦 Daftar Produk:")
    print("-" * 40)
    produk_list = get_semua_produk()
    if produk_list:
        for p in produk_list:
            print(f"  [{p['barcode']}] {p['nama_produk']:<25} Rp {p['harga']:>8,.0f}  Stok: {p['stok']}")
    else:
        print("  (tidak ada produk)")

    print()
    print("🔍 Test cari produk barcode '8999999001':")
    produk = cari_produk_by_barcode('8999999001')
    if produk:
        print(f"  Ketemu! → {produk['nama_produk']} - Rp {produk['harga']:,.0f}")
    else:
        print("  Tidak ketemu!")

    print()
    print("👤 Test login kasir:")
    kasir = login_kasir('kasir1', 'kasir123')
    if kasir:
        print(f"  Login berhasil! Selamat datang, {kasir['nama_lengkap']}!")
    else:
        print("  Login gagal!")

    print()
    print("🧾 Test simpan transaksi:")
    items_test = [
        {'produk_id': 1, 'nama': 'Indomie Goreng', 'harga': 3500, 'jumlah': 2},
        {'produk_id': 3, 'nama': 'Aqua 600ml',     'harga': 4000, 'jumlah': 1},
    ]
    id_trx = simpan_transaksi(kasir_id=1, items=items_test, uang_bayar=20000)
    if id_trx:
        print(f"  ID Transaksi: {id_trx}")

    print()
    print("="*50)
    print("  SEMUA TEST SELESAI!")
    print("="*50)