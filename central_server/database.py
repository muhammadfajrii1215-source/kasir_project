# database server pusat
# ============================================================
# FILE: central_server/database.py
# TUJUAN: Semua fungsi database untuk server pusat
# ============================================================

import mysql.connector
import threading

# Mutex untuk mencegah race condition di server pusat
db_lock = threading.Lock()

DB_CONFIG = {
    'host':     'localhost',
    'user':     'root',
    'password': 'g-artyone',   # ← Sesuaikan dengan password MySQL kamu
    'database': 'kasir_pusat',
    'charset':  'utf8mb4'
}


def get_connection():
    """Buat koneksi ke database pusat."""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"[DB PUSAT] Gagal konek: {e}")
        return None


def test_koneksi():
    """Test apakah koneksi ke database pusat berhasil."""
    print("Testing koneksi ke database pusat...")
    conn = get_connection()
    if conn:
        print("[OK] Berhasil konek ke kasir_pusat!")
        conn.close()
        return True
    else:
        print("[FAIL] Gagal konek ke kasir_pusat!")
        print("   Pastikan database kasir_pusat sudah dibuat.")
        return False


def get_id_cabang(kode_cabang):
    """
    Cari ID cabang berdasarkan kode cabang.
    
    Return:
        int : ID cabang
        None: Kalau tidak ditemukan
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM cabang WHERE kode_cabang = %s",
            (kode_cabang,)
        )
        hasil = cursor.fetchone()
        return hasil[0] if hasil else None
    except Exception as e:
        print(f"[DB PUSAT] Error get_id_cabang: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def simpan_transaksi_dari_cabang(kode_cabang, transaksi_list):
    """
    Simpan daftar transaksi yang diterima dari server cabang.
    
    Parameter:
        kode_cabang    (str) : Kode cabang pengirim
        transaksi_list (list): Daftar transaksi beserta detailnya
    
    Return:
        dict: {'sukses': bool, 'pesan': str, 'jumlah': int}
    """
    with db_lock:   # Kunci mutex — hanya 1 cabang yang bisa simpan dalam satu waktu
        conn = get_connection()
        if not conn:
            return {'sukses': False, 'pesan': 'Koneksi DB pusat gagal', 'jumlah': 0}

        try:
            cursor = conn.cursor()

            # Cari ID cabang
            cabang_id = get_id_cabang(kode_cabang)
            if not cabang_id:
                return {
                    'sukses': False,
                    'pesan': f"Cabang '{kode_cabang}' tidak terdaftar!",
                    'jumlah': 0
                }

            berhasil = 0

            for trx in transaksi_list:
                # Cek duplikat — jangan simpan dua kali
                cursor.execute("""
                    SELECT id FROM transaksi_pusat
                    WHERE id_transaksi = %s AND cabang_id = %s
                """, (trx['id_transaksi'], cabang_id))

                if cursor.fetchone():
                    continue    # Sudah ada, lewati

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

                # Simpan detail barang
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

            conn.commit()
            print(f"[DB PUSAT] [OK] {berhasil} transaksi dari cabang '{kode_cabang}' disimpan")
            return {
                'sukses': True,
                'pesan': f'{berhasil} transaksi berhasil disimpan',
                'jumlah': berhasil
            }

        except mysql.connector.Error as e:
            conn.rollback()
            print(f"[DB PUSAT] Error: {e}")
            return {'sukses': False, 'pesan': str(e), 'jumlah': 0}
        finally:
            cursor.close()
            conn.close()


def get_laporan_semua_cabang():
    """
    Ambil ringkasan transaksi dari semua cabang.
    Berguna untuk melihat laporan gabungan.
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                c.nama_cabang,
                COUNT(t.id)         AS jumlah_transaksi,
                SUM(t.total_harga)  AS total_omset
            FROM transaksi_pusat t
            JOIN cabang c ON t.cabang_id = c.id
            GROUP BY c.id, c.nama_cabang
            ORDER BY total_omset DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        print(f"[DB PUSAT] Error laporan: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


# ============================================================
# Test langsung kalau file ini dijalankan sendiri
# ============================================================
if __name__ == "__main__":
    test_koneksi()

    print("\n📊 Laporan semua cabang:")
    laporan = get_laporan_semua_cabang()
    if laporan:
        for baris in laporan:
            print(f"  {baris['nama_cabang']}: "
                  f"{baris['jumlah_transaksi']} transaksi, "
                  f"Rp {baris['total_omset']:,.0f}")
    else:
        print("  (belum ada data)")