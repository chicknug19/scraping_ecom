import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def send_captcha_alert(toko_target, url_terakhir, produk_ke):
    """
    Mengirimkan email notifikasi ke tim jika scraper terkena Hard Block / Captcha.
    """
    # 1. Konfigurasi Pengirim (Ambil dari .env)
    SENDER_EMAIL = os.getenv("BOT_EMAIL") # Contoh: bot.ciptautama@gmail.com
    SENDER_PASSWORD = os.getenv("BOT_EMAIL_PASSWORD") # App Password 16 huruf
    
    # 2. Daftar Penerima (Bisa lebih dari 1 orang)
    RECEIVERS = ["jason.adianto@binus.ac.id", "nathan.phan@binus.ac.id","radianda.setiawan@binus.ac.id"] 
    
    # Jangan lanjut jika kredensial belum disetting
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("⚠️ [Email System] Kredensial email belum diatur di .env. Notifikasi dibatalkan.")
        return False

    waktu_kejadian = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
    
    # 3. Merakit Isi Email
    subject = f"🚨 URGENT: Bot Shopee Terblokir di Toko {toko_target.upper()}"
    
    body = f"""
    Halo Tim,
    
    Sistem Scraper mendeteksi adanya Hard Block / Captcha dari Datadome Shopee.
    Proses scraping otomatis telah DIHENTIKAN SEMENTARA untuk melindungi IP Kantor.
    
    Detail Kejadian:
    - Toko Target: {toko_target}
    - Terhenti pada produk ke: {produk_ke}
    - Waktu Kejadian: {waktu_kejadian}
    - URL Terakhir: {url_terakhir}
    
    TINDAKAN YANG DIPERLUKAN:
    1. Buka layar komputer server di kantor.
    2. Klik ganda aplikasi "Buka_Shopee.bat" yang ada di layar Desktop.
    3. Selesaikan puzzle captcha atau login ulang di layar Chrome yang terbuka.
    4. Kembali ke layar hitam (terminal) yang muncul, lalu tekan ENTER untuk menutup dan menyimpan sesi.
    
    Cron job akan otomatis melanjutkan proses dari produk ke-{produk_ke} pada jadwal berikutnya setelah captcha diselesaikan.
    
    Salam,
    Robot Scraper AI Cipta Utama
    """
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVERS)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    # 4. Proses Pengiriman via Server Google
    try:
        print(f"📧 Mencoba mengirim email notifikasi ke {len(RECEIVERS)} penerima...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email notifikasi berhasil dikirim!")
        return True
    except Exception as e:
        print(f"❌ Gagal mengirim email: {e}")
        return False

# --- BLOK TESTING (Hanya jalan jika file ini di-run langsung) ---
if __name__ == "__main__":
    print("Mengetes sistem pengiriman email...")
    # Tes manual
    send_captcha_alert("iboxofficial", "https://shopee.co.id/iboxofficial", 15)