# ============================================================
# FILE: branch_server/database.py
# TUJUAN: Semua fungsi yang berhubungan dengan database lokal
# ============================================================

import mysql.connector        # Library untuk konek ke MySQL
import threading              # Untuk membuat MUTEX (kunci pengaman)
from datetime import datetime # Untuk mendapatkan waktu sekarang
import uuid                   # Untuk membuat ID transaksi yang unik

# ============================================================
# MUTEX — Kunci Pengaman dari Race Condition
# ------------------------------------------------------------
# Analogi: Bayangkan ada 1 mesin ATM, 2 orang antri.
# Mutex memastikan hanya 1 orang yang bisa pakai ATM,
# yang lain harus TUNGGU dulu sampai selesai.
# ============================================================
db_lock = threading.Lock()   # Ini adalah "kunci"-nya


# ============================================================
# KONFIGURASI DATABASE
# Ubah sesuai setting MySQL kamu!
# ============================================================
DB_CONFIG = {
    'host':     'localhost',   # Alamat server MySQL (di komputer sendiri = localhost)
    'user':     'root',        # Username MySQL
    'password': 'g-artyone',    # Password MySQL kamu
    'database': 'kasir_lokal', # Nama database yang mau dipakai
    'charset':  'utf8mb4'      # Jenis karakter (supaya bisa huruf Indonesia)
}


def get_connection():
    """
    Fungsi untuk membuat koneksi baru ke MySQL.
    
    Analogi: Seperti "membuka pintu" ke gudang data.
    Setiap kali mau akses data, kita buka pintu dulu,
    ambil datanya, lalu tutup pintunya lagi.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        # **DB_CONFIG artinya: "gunakan semua isi dictionary DB_CONFIG sebagai parameter"
        # Sama seperti menulis:
        # mysql.connector.connect(host='localhost', user='root', ...)
        return conn
    except mysql.connector.Error as e:
        # Kalau gagal konek, tampilkan pesan error yang jelas
        print(f"[ERROR] Gagal konek ke database: {e}")
        return None  # Kembalikan None (kosong) kalau gagal


def test_koneksi():
    """
    Fungsi untuk test apakah koneksi ke MySQL berhasil.
    Jalankan fungsi ini pertama kali untuk memastikan semuanya OK.
    """
    print("=" * 50)
    print("Testing koneksi ke MySQL...")
    print("=" * 50)
    
    conn = get_connection()
    
    if conn:  # Kalau conn tidak None (berhasil konek)
        print("✅ BERHASIL terhubung ke MySQL!")
        print(f"   Host    : {DB_CONFIG['host']}")
        print(f"   Database: {DB_CONFIG['database']}")
        conn.close()  # Tutup koneksi setelah selesai
        return True
    else:
        print("❌ GAGAL terhubung ke MySQL!")
        print("   Pastikan:")
        print("   1. MySQL Server sudah berjalan")
        print("   2. Username dan password benar")
        print("   3. Database 'kasir_lokal' sudah dibuat")
        return False


# ============================================================
# FUNGSI-FUNGSI PRODUK
# ============================================================

def cari_produk_by_barcode(barcode):
    """
    Cari produk berdasarkan barcode.
    
    Parameter:
        barcode (str): Kode barcode produk yang dicari
    
    Return:
        dict: Data produk kalau ketemu
        None: Kalau tidak ketemu
    
    Analogi: Seperti kasir yang scan barcode di mesin kasir,
    lalu mesin menampilkan nama dan harga produk.
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        # cursor = "jari" yang menunjuk ke data di database
        cursor = conn.cursor(dictionary=True)
        # dictionary=True artinya: kembalikan data dalam bentuk {kolom: nilai}
        # Contoh: {'id': 1, 'nama_produk': 'Indomie', 'harga': 3500}
        
        # Query SQL untuk mencari produk
        # %s = placeholder, akan diganti nilai 'barcode' secara aman
        # (ini mencegah SQL Injection / serangan hacker)
        query = "SELECT * FROM produk WHERE barcode = %s"
        cursor.execute(query, (barcode,))
        # (barcode,) = tuple dengan 1 elemen, ini format yang dibutuhkan
        
        produk = cursor.fetchone()  # Ambil 1 baris hasil pencarian
        return produk               # Kembalikan data produk (atau None kalau tidak ada)
        
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal cari produk: {e}")
        return None
    finally:
        # "finally" = SELALU dijalankan, mau berhasil atau error
        # Ini memastikan koneksi SELALU ditutup
        cursor.close()
        conn.close()


def get_semua_produk():
    """
    Ambil semua produk dari database.
    
    Return:
        list: Daftar semua produk
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # ORDER BY nama_produk = urutkan berdasarkan nama (A-Z)
        query = "SELECT * FROM produk ORDER BY nama_produk"
        cursor.execute(query)
        
        produk_list = cursor.fetchall()  # Ambil SEMUA baris hasil
        return produk_list
        
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal ambil produk: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def kurangi_stok(produk_id, jumlah):
    """
    Kurangi stok produk setelah terjual.
    
    ⚠️  FUNGSI INI MEMAKAI MUTEX!
    Kenapa? Karena kalau 2 kasir jual produk yang sama
    dalam waktu bersamaan tanpa mutex, stok bisa salah hitung!
    
    Contoh bug tanpa mutex:
    - Stok: 5
    - Kasir 1 baca stok: 5, mau kurangi 1
    - Kasir 2 baca stok: 5 (belum terupdate!), mau kurangi 1
    - Kasir 1 simpan: 5-1 = 4
    - Kasir 2 simpan: 5-1 = 4  ← HARUSNYA 3!
    
    Dengan mutex:
    - Kasir 1 dapat kunci, kurangi stok: 5→4, lepas kunci
    - Kasir 2 dapat kunci (setelah kasir 1 selesai), kurangi: 4→3 ✅
    """
    with db_lock:  # ← KUNCI DIAMBIL DI SINI, otomatis dilepas saat keluar blok "with"
        conn = get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Cek stok dulu sebelum dikurangi
            cursor.execute(
                "SELECT stok FROM produk WHERE id = %s",
                (produk_id,)
            )
            hasil = cursor.fetchone()
            
            if not hasil:
                print(f"[ERROR] Produk ID {produk_id} tidak ditemukan!")
                return False
            
            stok_sekarang = hasil[0]  # Ambil nilai stok (index 0 = kolom pertama)
            
            if stok_sekarang < jumlah:
                print(f"[ERROR] Stok tidak cukup! Stok: {stok_sekarang}, Diminta: {jumlah}")
                return False
            
            # Kurangi stok
            cursor.execute(
                "UPDATE produk SET stok = stok - %s WHERE id = %s",
                (jumlah, produk_id)
            )
            # "stok = stok - %s" artinya: ambil nilai stok sekarang, kurangi %s
            
            conn.commit()  # COMMIT = "simpan perubahan secara permanen"
            # Tanpa commit, perubahan tidak tersimpan!
            
            print(f"[INFO] Stok produk ID {produk_id} dikurangi {jumlah}")
            return True
            
        except mysql.connector.Error as e:
            conn.rollback()  # ROLLBACK = batalkan semua perubahan yang belum di-commit
            print(f"[ERROR] Gagal kurangi stok: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    # ← KUNCI OTOMATIS DILEPAS DI SINI


# ============================================================
# FUNGSI-FUNGSI TRANSAKSI
# ============================================================

def buat_id_transaksi():
    """
    Buat ID transaksi yang unik.
    Format: TRX-YYYYMMDD-XXXXXXXX
    Contoh: TRX-20240115-a3f8b2c1
    
    uuid.uuid4() menghasilkan string acak yang dijamin unik
    di seluruh dunia!
    """
    tanggal = datetime.now().strftime('%Y%m%d')  # Format: 20240115
    unik = str(uuid.uuid4())[:8]                  # 8 karakter acak
    return f"TRX-{tanggal}-{unik}"


def simpan_transaksi(kasir_id, items, uang_bayar):
    """
    Simpan transaksi lengkap ke database.
    
    Parameter:
        kasir_id  (int): ID kasir yang melayani
        items     (list): Daftar barang yang dibeli
                  Format: [
                      {'produk_id': 1, 'nama': 'Indomie', 
                       'harga': 3500, 'jumlah': 2},
                      ...
                  ]
        uang_bayar (float): Uang yang dibayarkan pelanggan
    
    Return:
        str: ID transaksi kalau berhasil
        None: Kalau gagal
    
    Fungsi ini memakai MUTEX karena:
    1. Menyimpan ke tabel transaksi
    2. Menyimpan ke tabel detail_transaksi  
    3. Mengurangi stok beberapa produk
    Semua harus dilakukan secara ATOMIK (semua berhasil atau semua dibatalkan)
    """
    with db_lock:  # ← AMBIL KUNCI
        conn = get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Hitung total harga dari semua items
            total = sum(item['harga'] * item['jumlah'] for item in items)
            # "sum(...)" = menjumlahkan semua subtotal
            # "for item in items" = untuk setiap barang di daftar belanja
            
            kembalian = uang_bayar - total
            id_trx = buat_id_transaksi()
            
            # --- SIMPAN KE TABEL transaksi ---
            cursor.execute("""
                INSERT INTO transaksi 
                    (id_transaksi, kasir_id, total_harga, uang_bayar, kembalian)
                VALUES 
                    (%s, %s, %s, %s, %s)
            """, (id_trx, kasir_id, total, uang_bayar, kembalian))
            # %s pertama = id_trx
            # %s kedua  = kasir_id
            # dst...
            
            # --- SIMPAN DETAIL SETIAP BARANG ---
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
                
                # Kurangi stok produk ini
                cursor.execute("""
                    UPDATE produk 
                    SET stok = stok - %s 
                    WHERE id = %s
                """, (item['jumlah'], item['produk_id']))
            
            # Simpan semua perubahan sekaligus
            conn.commit()
            
            print(f"✅ Transaksi {id_trx} berhasil disimpan!")
            print(f"   Total   : Rp {total:,.0f}")
            print(f"   Bayar   : Rp {uang_bayar:,.0f}")
            print(f"   Kembali : Rp {kembalian:,.0f}")
            
            return id_trx  # Kembalikan ID transaksi
            
        except mysql.connector.Error as e:
            conn.rollback()  # Batalkan SEMUA perubahan kalau ada yang error
            print(f"[ERROR] Gagal simpan transaksi: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    # ← LEPAS KUNCI


def get_transaksi_pending():
    """
    Ambil semua transaksi yang BELUM disinkronisasi ke server pusat.
    Ini dipakai saat mode online untuk kirim data ke pusat.
    
    Return:
        list: Daftar transaksi dengan status 'pending'
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Ambil transaksi + detail barangnya sekaligus
        query = """
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
        """
        # JOIN = gabungkan 2 tabel
        # "t.kasir_id = k.id" = cocokkan ID kasir di kedua tabel
        # "WHERE status_sync = 'pending'" = hanya yang belum sync
        # "ORDER BY ... ASC" = urutkan dari yang terlama (kirim yang lama dulu)
        
        cursor.execute(query)
        transaksi_list = cursor.fetchall()
        
        # Untuk setiap transaksi, ambil juga detail barangnya
        for trx in transaksi_list:
            cursor.execute("""
                SELECT * FROM detail_transaksi 
                WHERE id_transaksi = %s
            """, (trx['id_transaksi'],))
            trx['detail'] = cursor.fetchall()
            # Tambahkan key 'detail' ke setiap transaksi
        
        return transaksi_list
        
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal ambil transaksi pending: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def tandai_sudah_sync(id_transaksi):
    """
    Ubah status transaksi dari 'pending' → 'synced'
    setelah berhasil dikirim ke server pusat.
    """
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
    Cek apakah username dan password kasir valid.
    
    Return:
        dict: Data kasir kalau login berhasil
        None: Kalau username/password salah
    
    CATATAN: Sekarang kita cek password langsung (plain text).
    Nanti di step selanjutnya kita akan enkripsi pakai bcrypt.
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
        # "aktif = 1" = hanya kasir yang masih aktif
        
        kasir = cursor.fetchone()
        return kasir  # None kalau tidak ketemu
        
    except mysql.connector.Error as e:
        print(f"[ERROR] Gagal login: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================================
# PROGRAM UTAMA — untuk test fungsi-fungsi di atas
# Jalankan file ini langsung: python database.py
# ============================================================
if __name__ == "__main__":
    # "__main__" = blok ini hanya jalan kalau file ini dijalankan langsung
    # (tidak jalan kalau di-import dari file lain)
    
    print("\n" + "="*50)
    print("  TEST DATABASE LOKAL")
    print("="*50 + "\n")
    
    # Test 1: Koneksi
    if not test_koneksi():
        print("\nHentikan program. Perbaiki koneksi dulu!")
        exit()
    
    print()
    
    # Test 2: Ambil semua produk
    print("📦 Daftar Produk:")
    print("-" * 40)
    produk_list = get_semua_produk()
    if produk_list:
        for p in produk_list:
            print(f"  [{p['barcode']}] {p['nama_produk']:<25} Rp {p['harga']:>8,.0f}  Stok: {p['stok']}")
    else:
        print("  (tidak ada produk)")
    
    print()
    
    # Test 3: Cari produk by barcode
    print("🔍 Test cari produk barcode '8999999001':")
    produk = cari_produk_by_barcode('8999999001')
    if produk:
        print(f"  Ketemu! → {produk['nama_produk']} - Rp {produk['harga']:,.0f}")
    else:
        print("  Tidak ketemu!")
    
    print()
    
    # Test 4: Login kasir
    print("👤 Test login kasir:")
    kasir = login_kasir('kasir1', 'kasir123')
    if kasir:
        print(f"  Login berhasil! Selamat datang, {kasir['nama_lengkap']}!")
    else:
        print("  Login gagal!")
    
    print()
    
    # Test 5: Simpan transaksi contoh
    print("🧾 Test simpan transaksi:")
    items_test = [
        {'produk_id': 1, 'nama': 'Indomie Goreng',   'harga': 3500, 'jumlah': 2},
        {'produk_id': 3, 'nama': 'Aqua 600ml',        'harga': 4000, 'jumlah': 1},
    ]
    id_trx = simpan_transaksi(
        kasir_id=1,
        items=items_test,
        uang_bayar=20000
    )
    if id_trx:
        print(f"  ID Transaksi: {id_trx}")
    
    print()
    print("="*50)
    print("  SEMUA TEST SELESAI!")
    print("="*50)