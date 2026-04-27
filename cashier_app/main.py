# ============================================================
# FILE: cashier_app/main.py
# TUJUAN: Aplikasi kasir desktop dengan tampilan GUI
# LIBRARY: Tkinter (sudah built-in di Python, tidak perlu install)
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import socket
import json
import threading
from datetime import datetime


# ============================================================
# KONFIGURASI: Alamat server lokal cabang
# ============================================================
SERVER_HOST = 'localhost'  # Server lokal ada di komputer yang sama
SERVER_PORT = 9000         # Port yang sama dengan server.py


# ============================================================
# CLASS KONEKSI KE SERVER
# ============================================================

class KoneksiServer:
    """
    Mengelola koneksi ke server lokal cabang.
    """
    
    def __init__(self):
        self.socket = None
        self.terhubung = False
    
    def konek(self):
        """Buat koneksi ke server lokal."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # Timeout 5 detik
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.terhubung = True
            return True
        except Exception as e:
            self.terhubung = False
            print(f"Gagal konek ke server: {e}")
            return False
    
    def kirim(self, data):
        """
        Kirim data ke server dan tunggu response.
        
        Return:
            dict: Response dari server
            None: Kalau gagal
        """
        if not self.terhubung:
            return None
        
        try:
            pesan = json.dumps(data)
            self.socket.send(pesan.encode('utf-8'))
            
            response_raw = self.socket.recv(8192)  # Terima sampai 8KB
            return json.loads(response_raw.decode('utf-8'))
            
        except Exception as e:
            print(f"Error komunikasi server: {e}")
            self.terhubung = False
            return None
    
    def putus(self):
        """Tutup koneksi."""
        if self.socket:
            try:
                self.kirim({'aksi': 'LOGOUT'})
                self.socket.close()
            except:
                pass
        self.terhubung = False


# ============================================================
# HALAMAN LOGIN
# ============================================================

class HalamanLogin:
    """
    Tampilan login kasir.
    Kasir harus login sebelum bisa transaksi.
    """
    
    def __init__(self, root, callback_berhasil):
        """
        Parameter:
            root              : Jendela utama Tkinter
            callback_berhasil : Fungsi yang dipanggil kalau login berhasil
        """
        self.root = root
        self.callback_berhasil = callback_berhasil
        self.server = KoneksiServer()
        
        self.buat_tampilan()
    
    def buat_tampilan(self):
        """Buat tampilan halaman login."""
        self.root.title("Sistem Kasir — Login")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        self.root.configure(bg='#1a1a2e')
        
        # Tengahkan jendela di layar
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 400) // 2
        y = (self.root.winfo_screenheight() - 350) // 2
        self.root.geometry(f"400x350+{x}+{y}")
        
        # ---- JUDUL ----
        frame_judul = tk.Frame(self.root, bg='#16213e', pady=20)
        frame_judul.pack(fill='x')
        
        tk.Label(
            frame_judul,
            text="🛒  SISTEM KASIR",
            font=('Helvetica', 20, 'bold'),
            bg='#16213e',
            fg='#e94560'
        ).pack()
        
        tk.Label(
            frame_judul,
            text="Multi Cabang Terdistribusi",
            font=('Helvetica', 10),
            bg='#16213e',
            fg='#aaaaaa'
        ).pack()
        
        # ---- FORM LOGIN ----
        frame_form = tk.Frame(self.root, bg='#1a1a2e', padx=40, pady=30)
        frame_form.pack(fill='both', expand=True)
        
        # Username
        tk.Label(
            frame_form, text="Username",
            font=('Helvetica', 11),
            bg='#1a1a2e', fg='white', anchor='w'
        ).pack(fill='x', pady=(0, 3))
        
        self.entry_username = tk.Entry(
            frame_form,
            font=('Helvetica', 12),
            bg='#0f3460', fg='white',
            insertbackground='white',   # Warna kursor teks
            relief='flat', bd=8
        )
        self.entry_username.pack(fill='x', pady=(0, 15))
        self.entry_username.focus()     # Langsung fokus ke field ini
        
        # Password
        tk.Label(
            frame_form, text="Password",
            font=('Helvetica', 11),
            bg='#1a1a2e', fg='white', anchor='w'
        ).pack(fill='x', pady=(0, 3))
        
        self.entry_password = tk.Entry(
            frame_form,
            font=('Helvetica', 12),
            bg='#0f3460', fg='white',
            insertbackground='white',
            show='●',         # Tampilkan ● untuk menyembunyikan password
            relief='flat', bd=8
        )
        self.entry_password.pack(fill='x', pady=(0, 20))
        
        # Bind Enter key → langsung login
        self.entry_password.bind('<Return>', lambda e: self.proses_login())
        
        # Tombol Login
        self.btn_login = tk.Button(
            frame_form,
            text="MASUK",
            font=('Helvetica', 12, 'bold'),
            bg='#e94560', fg='white',
            relief='flat', bd=0,
            pady=10,
            cursor='hand2',   # Kursor berubah jadi tangan saat hover
            command=self.proses_login
        )
        self.btn_login.pack(fill='x')
        
        # Label status (untuk pesan error/info)
        self.label_status = tk.Label(
            frame_form, text="",
            font=('Helvetica', 10),
            bg='#1a1a2e', fg='#ff6b6b'
        )
        self.label_status.pack(pady=(10, 0))
    
    def proses_login(self):
        """Proses klik tombol login."""
        username = self.entry_username.get().strip()  # .strip() = hapus spasi di awal/akhir
        password = self.entry_password.get()
        
        # Validasi: field tidak boleh kosong
        if not username or not password:
            self.label_status.config(text="⚠️  Username dan password wajib diisi!")
            return
        
        # Ubah tampilan saat loading
        self.btn_login.config(text="Menghubungkan...", state='disabled')
        self.label_status.config(text="Menghubungkan ke server...", fg='#aaaaaa')
        self.root.update()  # Paksa update tampilan
        
        # Lakukan login di thread terpisah supaya UI tidak freeze
        # (Kalau dilakukan di thread utama, UI akan "beku" saat konek ke server)
        thread = threading.Thread(target=self._login_thread, args=(username, password))
        thread.daemon = True
        thread.start()
    
    def _login_thread(self, username, password):
        """Proses login di background thread."""
        # Konek ke server
        if not self.server.konek():
            # Gagal konek → update UI dari main thread
            self.root.after(0, self._login_gagal, 
                           "❌  Tidak bisa konek ke server!\nPastikan server sudah dijalankan.")
            return
        
        # Kirim request login
        response = self.server.kirim({
            'aksi': 'LOGIN',
            'username': username,
            'password': password
        })
        
        # Update UI (harus dari main thread, pakai root.after)
        if response and response.get('sukses'):
            self.root.after(0, self._login_berhasil, response['kasir'])
        else:
            pesan = response.get('pesan', 'Login gagal') if response else 'Server tidak merespon'
            self.root.after(0, self._login_gagal, f"❌  {pesan}")
    
    def _login_berhasil(self, info_kasir):
        """Dipanggil kalau login berhasil."""
        # Hapus semua widget dari jendela
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Tampilkan halaman kasir utama
        HalamanKasir(self.root, info_kasir, self.server)
    
    def _login_gagal(self, pesan):
        """Dipanggil kalau login gagal."""
        self.btn_login.config(text="MASUK", state='normal')
        self.label_status.config(text=pesan, fg='#ff6b6b')
        self.entry_password.delete(0, 'end')  # Hapus isi field password


# ============================================================
# HALAMAN KASIR UTAMA
# ============================================================

class HalamanKasir:
    """
    Tampilan utama aplikasi kasir.
    Di sini kasir bisa:
    - Scan/cari produk
    - Tambah ke keranjang
    - Proses pembayaran
    """
    
    def __init__(self, root, info_kasir, server):
        self.root = root
        self.info_kasir = info_kasir    # {'id': 1, 'username': 'kasir1', 'nama_lengkap': 'Budi'}
        self.server = server
        
        self.keranjang = []             # Daftar barang yang akan dibeli
        self.total = 0                  # Total harga
        
        self.buat_tampilan()
        self.muat_produk()              # Load daftar produk dari server
    
    def buat_tampilan(self):
        """Buat tampilan utama kasir."""
        self.root.title(f"Kasir — {self.info_kasir['nama_lengkap']}")
        self.root.geometry("1100x700")
        self.root.configure(bg='#f0f4f8')
        
        # Tengahkan
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 1100) // 2
        y = (self.root.winfo_screenheight() - 700) // 2
        self.root.geometry(f"1100x700+{x}+{y}")
        
        # ---- HEADER ----
        self.buat_header()
        
        # ---- KONTEN UTAMA (kiri + kanan) ----
        frame_konten = tk.Frame(self.root, bg='#f0f4f8')
        frame_konten.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Panel kiri: Produk
        self.buat_panel_produk(frame_konten)
        
        # Panel kanan: Keranjang + Bayar
        self.buat_panel_keranjang(frame_konten)
    
    def buat_header(self):
        """Buat header atas."""
        header = tk.Frame(self.root, bg='#2c3e50', pady=12, padx=20)
        header.pack(fill='x')
        
        tk.Label(
            header,
            text="🛒  SISTEM KASIR",
            font=('Helvetica', 16, 'bold'),
            bg='#2c3e50', fg='white'
        ).pack(side='left')
        
        # Info kasir di kanan
        frame_info = tk.Frame(header, bg='#2c3e50')
        frame_info.pack(side='right')
        
        tk.Label(
            frame_info,
            text=f"👤  {self.info_kasir['nama_lengkap']}",
            font=('Helvetica', 11),
            bg='#2c3e50', fg='#ecf0f1'
        ).pack(side='left', padx=(0, 20))
        
        # Waktu
        self.label_waktu = tk.Label(
            frame_info,
            text="",
            font=('Helvetica', 10),
            bg='#2c3e50', fg='#bdc3c7'
        )
        self.label_waktu.pack(side='left', padx=(0, 20))
        self.update_waktu()
        
        # Tombol Logout
        tk.Button(
            frame_info,
            text="Logout",
            bg='#e74c3c', fg='white',
            font=('Helvetica', 10),
            relief='flat', padx=10, pady=3,
            cursor='hand2',
            command=self.logout
        ).pack(side='left')
    
    def update_waktu(self):
        """Update tampilan waktu setiap detik."""
        waktu = datetime.now().strftime("%A, %d %B %Y  %H:%M:%S")
        self.label_waktu.config(text=waktu)
        # Panggil diri sendiri lagi setelah 1000ms (1 detik)
        self.root.after(1000, self.update_waktu)
    
    def buat_panel_produk(self, parent):
        """Panel kiri: daftar produk."""
        frame = tk.Frame(parent, bg='white', relief='flat', bd=1)
        frame.pack(side='left', fill='both', expand=True, padx=(0, 8))
        
        # Judul panel
        tk.Label(
            frame, text="📦  DAFTAR PRODUK",
            font=('Helvetica', 12, 'bold'),
            bg='#3498db', fg='white',
            pady=10
        ).pack(fill='x')
        
        # Search bar
        frame_cari = tk.Frame(frame, bg='white', padx=10, pady=8)
        frame_cari.pack(fill='x')
        
        tk.Label(
            frame_cari, text="Barcode / Nama:",
            bg='white', font=('Helvetica', 10)
        ).pack(side='left')
        
        self.entry_cari = tk.Entry(
            frame_cari,
            font=('Helvetica', 11),
            relief='solid', bd=1
        )
        self.entry_cari.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.entry_cari.bind('<Return>', lambda e: self.cari_dan_tambah())
        
        tk.Button(
            frame_cari,
            text="Tambah",
            bg='#27ae60', fg='white',
            font=('Helvetica', 10, 'bold'),
            relief='flat', padx=10,
            cursor='hand2',
            command=self.cari_dan_tambah
        ).pack(side='left')
        
        # Tabel produk
        frame_tabel = tk.Frame(frame, bg='white')
        frame_tabel.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_tabel)
        scrollbar.pack(side='right', fill='y')
        
        # Tabel
        kolom = ('barcode', 'nama', 'harga', 'stok')
        self.tabel_produk = ttk.Treeview(
            frame_tabel,
            columns=kolom,
            show='headings',
            yscrollcommand=scrollbar.set,
            height=20
        )
        
        # Header kolom
        self.tabel_produk.heading('barcode', text='Barcode')
        self.tabel_produk.heading('nama',    text='Nama Produk')
        self.tabel_produk.heading('harga',   text='Harga')
        self.tabel_produk.heading('stok',    text='Stok')
        
        # Lebar kolom
        self.tabel_produk.column('barcode', width=120, anchor='center')
        self.tabel_produk.column('nama',    width=200)
        self.tabel_produk.column('harga',   width=100, anchor='e')
        self.tabel_produk.column('stok',    width=60,  anchor='center')
        
        self.tabel_produk.pack(fill='both', expand=True)
        scrollbar.config(command=self.tabel_produk.yview)
        
        # Double-click pada produk = tambah ke keranjang
        self.tabel_produk.bind('<Double-Button-1>', self.tambah_dari_tabel)
    
    def buat_panel_keranjang(self, parent):
        """Panel kanan: keranjang belanja + pembayaran."""
        frame = tk.Frame(parent, bg='white', width=380)
        frame.pack(side='right', fill='y')
        frame.pack_propagate(False)  # Jaga ukuran tetap 380px
        
        # Judul
        tk.Label(
            frame, text="🛍️  KERANJANG BELANJA",
            font=('Helvetica', 12, 'bold'),
            bg='#e74c3c', fg='white', pady=10
        ).pack(fill='x')
        
        # Tabel keranjang
        frame_keranjang = tk.Frame(frame, bg='white')
        frame_keranjang.pack(fill='both', expand=True, padx=10, pady=10)
        
        kolom = ('nama', 'qty', 'harga', 'subtotal')
        self.tabel_keranjang = ttk.Treeview(
            frame_keranjang,
            columns=kolom,
            show='headings',
            height=12
        )
        
        self.tabel_keranjang.heading('nama',     text='Produk')
        self.tabel_keranjang.heading('qty',      text='Qty')
        self.tabel_keranjang.heading('harga',    text='Harga')
        self.tabel_keranjang.heading('subtotal', text='Subtotal')
        
        self.tabel_keranjang.column('nama',     width=140)
        self.tabel_keranjang.column('qty',      width=40,  anchor='center')
        self.tabel_keranjang.column('harga',    width=80,  anchor='e')
        self.tabel_keranjang.column('subtotal', width=90,  anchor='e')
        
        self.tabel_keranjang.pack(fill='both', expand=True)
        
        # Tombol hapus item
        tk.Button(
            frame_keranjang,
            text="🗑️  Hapus Item",
            bg='#e74c3c', fg='white',
            font=('Helvetica', 10),
            relief='flat', pady=5,
            cursor='hand2',
            command=self.hapus_item
        ).pack(fill='x', pady=(5, 0))
        
        # ---- AREA PEMBAYARAN ----
        frame_bayar = tk.Frame(frame, bg='#ecf0f1', padx=15, pady=15)
        frame_bayar.pack(fill='x', side='bottom')
        
        # Total
        tk.Label(
            frame_bayar, text="TOTAL:",
            font=('Helvetica', 13, 'bold'),
            bg='#ecf0f1'
        ).grid(row=0, column=0, sticky='w')
        
        self.label_total = tk.Label(
            frame_bayar,
            text="Rp 0",
            font=('Helvetica', 18, 'bold'),
            bg='#ecf0f1', fg='#e74c3c'
        )
        self.label_total.grid(row=0, column=1, sticky='e')
        
        # Input uang bayar
        tk.Label(
            frame_bayar, text="Uang Bayar:",
            font=('Helvetica', 11),
            bg='#ecf0f1'
        ).grid(row=1, column=0, sticky='w', pady=(10, 0))
        
        self.entry_bayar = tk.Entry(
            frame_bayar,
            font=('Helvetica', 14),
            relief='solid', bd=1, width=15
        )
        self.entry_bayar.grid(row=1, column=1, sticky='ew', pady=(10, 0))
        
        # Kembalian
        tk.Label(
            frame_bayar, text="Kembalian:",
            font=('Helvetica', 11),
            bg='#ecf0f1'
        ).grid(row=2, column=0, sticky='w', pady=(5, 0))
        
        self.label_kembalian = tk.Label(
            frame_bayar,
            text="Rp 0",
            font=('Helvetica', 14, 'bold'),
            bg='#ecf0f1', fg='#27ae60'
        )
        self.label_kembalian.grid(row=2, column=1, sticky='e', pady=(5, 0))
        
        frame_bayar.columnconfigure(1, weight=1)
        
        # Tombol Bayar
        self.btn_bayar = tk.Button(
            frame_bayar,
            text="💳  PROSES PEMBAYARAN",
            font=('Helvetica', 13, 'bold'),
            bg='#27ae60', fg='white',
            relief='flat', pady=12,
            cursor='hand2',
            command=self.proses_pembayaran
        )
        self.btn_bayar.grid(row=3, column=0, columnspan=2, 
                           sticky='ew', pady=(15, 5))
        
        # Tombol Batal
        tk.Button(
            frame_bayar,
            text="❌  BATAL",
            font=('Helvetica', 11),
            bg='#e74c3c', fg='white',
            relief='flat', pady=8,
            cursor='hand2',
            command=self.batal_transaksi
        ).grid(row=4, column=0, columnspan=2, sticky='ew')
        
        # Update kembalian saat uang bayar diubah
        self.entry_bayar.bind('<KeyRelease>', self.update_kembalian)
    
    def muat_produk(self):
        """Muat daftar produk dari server."""
        response = self.server.kirim({'aksi': 'GET_PRODUK'})
        
        if response and response.get('sukses'):
            # Hapus isi tabel dulu
            for item in self.tabel_produk.get_children():
                self.tabel_produk.delete(item)
            
            # Isi dengan data baru
            for p in response['produk']:
                self.tabel_produk.insert('', 'end', values=(
                    p['barcode'],
                    p['nama_produk'],
                    f"Rp {float(p['harga']):,.0f}",
                    p['stok']
                ))
        else:
            messagebox.showerror("Error", "Gagal memuat daftar produk!")
    
    def cari_dan_tambah(self):
        """Cari produk berdasarkan pilihan di tabel atau input manual."""
        item_terpilih = self.tabel_produk.selection()

        if item_terpilih:
            nilai = self.tabel_produk.item(item_terpilih[0])['values']
            barcode = nilai[0]
        else:
            barcode = self.entry_cari.get().strip()
            if not barcode:
                messagebox.showwarning("Peringatan", "Pilih produk dulu atau ketik barcode!")
                return

        response = self.server.kirim({
            'aksi': 'SCAN_BARCODE',
            'barcode': barcode
        })

        if response and response.get('sukses'):
            self.tambah_ke_keranjang(response['produk'])
            self.entry_cari.delete(0, 'end')
        else:
            messagebox.showwarning("Tidak Ditemukan", f"Produk '{barcode}' tidak ditemukan!")
    
    def tambah_dari_tabel(self, event):
        """Double-click pada tabel produk = tambah ke keranjang."""
        item = self.tabel_produk.selection()
        if not item:
            return
        
        nilai = self.tabel_produk.item(item[0])['values']
        barcode = nilai[0]
        
        response = self.server.kirim({
            'aksi': 'SCAN_BARCODE',
            'barcode': barcode
        })
        
        if response and response.get('sukses'):
            self.tambah_ke_keranjang(response['produk'])
    
    def tambah_ke_keranjang(self, produk):
        """
        Tambah produk ke keranjang.
        Kalau sudah ada, tambah jumlahnya saja.
        """
        # Cek apakah produk sudah ada di keranjang
        for item in self.keranjang:
            if item['produk_id'] == produk['id']:
                item['jumlah'] += 1  # Tambah jumlah
                self.refresh_keranjang()
                return
        
        # Produk baru, tambah ke daftar
        self.keranjang.append({
            'produk_id': produk['id'],
            'nama':      produk['nama_produk'],
            'harga':     float(produk['harga']),
            'jumlah':    1
        })
        
        self.refresh_keranjang()
    
    def refresh_keranjang(self):
        """Update tampilan keranjang dan total harga."""
        # Hapus isi tabel keranjang
        for item in self.tabel_keranjang.get_children():
            self.tabel_keranjang.delete(item)
        
        # Isi ulang
        self.total = 0
        for item in self.keranjang:
            subtotal = item['harga'] * item['jumlah']
            self.total += subtotal
            
            self.tabel_keranjang.insert('', 'end', values=(
                item['nama'],
                item['jumlah'],
                f"Rp {item['harga']:,.0f}",
                f"Rp {subtotal:,.0f}"
            ))
        
        # Update label total
        self.label_total.config(text=f"Rp {self.total:,.0f}")
        self.update_kembalian()
    
    def hapus_item(self):
        """Hapus item yang dipilih dari keranjang."""
        item = self.tabel_keranjang.selection()
        if not item:
            messagebox.showinfo("Info", "Pilih item yang ingin dihapus!")
            return

        idx = self.tabel_keranjang.index(item[0])
        nama = self.keranjang[idx]['nama']

        if messagebox.askyesno("Hapus Item", f"Hapus '{nama}' dari keranjang?"):
            self.keranjang.pop(idx)
            self.refresh_keranjang()
    
    def update_kembalian(self, event=None):
        """Update label kembalian saat uang bayar diubah."""
        try:
            bayar = float(self.entry_bayar.get().replace(',', ''))
            kembalian = bayar - self.total
            
            if kembalian >= 0:
                self.label_kembalian.config(
                    text=f"Rp {kembalian:,.0f}",
                    fg='#27ae60'    # Hijau kalau cukup
                )
            else:
                self.label_kembalian.config(
                    text=f"Rp {kembalian:,.0f}",
                    fg='#e74c3c'    # Merah kalau kurang
                )
        except ValueError:
            self.label_kembalian.config(text="Rp 0")
    
    def proses_pembayaran(self):
        """Proses pembayaran transaksi."""
        # Validasi keranjang tidak kosong
        if not self.keranjang:
            messagebox.showwarning("Peringatan", "Keranjang masih kosong!")
            return
        
        # Validasi uang bayar
        try:
            uang_bayar = float(self.entry_bayar.get().replace(',', ''))
        except ValueError:
            messagebox.showwarning("Peringatan", "Masukkan jumlah uang bayar!")
            return
        
        if uang_bayar < self.total:
            messagebox.showwarning("Peringatan", 
                f"Uang bayar kurang!\nTotal: Rp {self.total:,.0f}\n"
                f"Bayar: Rp {uang_bayar:,.0f}")
            return
        
        # Konfirmasi
        if not messagebox.askyesno("Konfirmasi", 
            f"Proses pembayaran?\n\n"
            f"Total     : Rp {self.total:,.0f}\n"
            f"Bayar     : Rp {uang_bayar:,.0f}\n"
            f"Kembalian : Rp {uang_bayar - self.total:,.0f}"):
            return
        
        # Kirim ke server
        self.btn_bayar.config(text="Memproses...", state='disabled')
        self.root.update()
        
        response = self.server.kirim({
            'aksi':       'TRANSAKSI',
            'items':      self.keranjang,
            'uang_bayar': uang_bayar
        })
        
        self.btn_bayar.config(text="💳  PROSES PEMBAYARAN", state='normal')
        
        if response and response.get('sukses'):
            # Tampilkan struk sederhana
            self.tampilkan_struk(response, uang_bayar)
            # Reset keranjang
            self.batal_transaksi()
            # Refresh produk (update stok)
            self.muat_produk()
        else:
            pesan = response.get('pesan', 'Terjadi kesalahan') if response else 'Server tidak merespon'
            messagebox.showerror("Error", f"Transaksi gagal!\n{pesan}")
    
    def tampilkan_struk(self, data, uang_bayar):
        """Tampilkan jendela struk pembayaran."""
        jendela = tk.Toplevel(self.root)
        jendela.title("Struk Pembayaran")
        jendela.geometry("320x500")
        jendela.resizable(False, False)
        jendela.configure(bg='white')
        
        # Tengahkan
        jendela.update_idletasks()
        x = (jendela.winfo_screenwidth() - 320) // 2
        y = (jendela.winfo_screenheight() - 500) // 2
        jendela.geometry(f"320x500+{x}+{y}")
        
        frame = tk.Frame(jendela, bg='white', padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        # Header struk
        tk.Label(frame, text="MINIMARKET SEGAR",
            font=('Courier', 14, 'bold'), bg='white').pack()
        tk.Label(frame, text="Terima kasih telah berbelanja!",
            font=('Courier', 9), bg='white').pack()
        tk.Label(frame, text="-" * 38,
            font=('Courier', 9), bg='white').pack()
        tk.Label(frame, text=f"ID: {data.get('id_transaksi', '-')}",
            font=('Courier', 8), bg='white').pack(anchor='w')
        tk.Label(frame, text=f"Kasir: {self.info_kasir['nama_lengkap']}",
            font=('Courier', 8), bg='white').pack(anchor='w')
        tk.Label(frame, text=f"Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            font=('Courier', 8), bg='white').pack(anchor='w')
        tk.Label(frame, text="-" * 38,
            font=('Courier', 9), bg='white').pack()
        
        # Item belanja
        for item in self.keranjang:
            subtotal = item['harga'] * item['jumlah']
            tk.Label(frame,
                text=f"{item['nama'][:20]:<20}",
                font=('Courier', 9), bg='white').pack(anchor='w')
            tk.Label(frame,
                text=f"  {item['jumlah']} x {item['harga']:>8,.0f} = {subtotal:>10,.0f}",
                font=('Courier', 9), bg='white').pack(anchor='w')
        
        tk.Label(frame, text="-" * 38,
            font=('Courier', 9), bg='white').pack()
        tk.Label(frame, text=f"{'TOTAL':<20} Rp {self.total:>12,.0f}",
            font=('Courier', 10, 'bold'), bg='white').pack(anchor='w')
        tk.Label(frame, text=f"{'BAYAR':<20} Rp {uang_bayar:>12,.0f}",
            font=('Courier', 9), bg='white').pack(anchor='w')
        tk.Label(frame, text=f"{'KEMBALI':<20} Rp {(uang_bayar-self.total):>12,.0f}",
            font=('Courier', 9), bg='white').pack(anchor='w')
        tk.Label(frame, text="=" * 38,
            font=('Courier', 9), bg='white').pack()
        tk.Label(frame, text="✅  TRANSAKSI BERHASIL!",
            font=('Courier', 10, 'bold'), bg='white', fg='green').pack(pady=5)
        
        tk.Button(frame, text="Tutup", command=jendela.destroy,
            bg='#e74c3c', fg='white', font=('Helvetica', 10),
            relief='flat', padx=20, pady=5).pack(pady=5)
    
    def batal_transaksi(self):
        """Reset keranjang belanja."""
        self.keranjang = []
        self.total = 0
        self.entry_bayar.delete(0, 'end')
        self.refresh_keranjang()
    
    def logout(self):
        """Logout dari sistem."""
        if messagebox.askyesno("Logout", "Yakin ingin logout?"):
            self.server.putus()
            for widget in self.root.winfo_children():
                widget.destroy()
            self.root.geometry("400x350")
            HalamanLogin(self.root, None)


# ============================================================
# ENTRY POINT — Titik masuk program
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()                  # Buat jendela utama
    app = HalamanLogin(root, None)  # Tampilkan halaman login
    root.mainloop()                 # Mulai event loop (program berjalan terus)
    # mainloop() = program menunggu input user (klik, ketik, dll)
    # Program baru berhenti kalau jendela ditutup