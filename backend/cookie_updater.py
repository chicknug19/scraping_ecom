import os
import json
import pyodbc
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Muat kredensial dari .env lokalmu
load_dotenv()

def update_shopee_cookie():
    # 1. Setup Koneksi ke Azure SQL
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    driver = '{ODBC Driver 17 for SQL Server}'
    conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 2. Otomatis membuat tabel jika belum ada
        print("⚙️ Memeriksa tabel AppConfigs di database Azure...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AppConfigs' and xtype='U')
            CREATE TABLE AppConfigs (
                ConfigKey VARCHAR(50) PRIMARY KEY,
                ConfigValue NVARCHAR(MAX),
                LastUpdated DATETIME
            )
        """)
        conn.commit()

        # 3. Buka browser untuk Login Manual
        print("\n🌐 Membuka browser... Silakan login ke Shopee secara manual.")
        print("⚠️ PENTING: Gunakan akun tumbal (dummy), JANGAN akun pribadi atau akun utama PT Cipta Utama Karya!")
        
        with sync_playwright() as p:
            # Headless=False agar browser terlihat olehmu
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            page.goto("https://shopee.co.id/buyer/login")
            
            print("⏳ Menunggu kamu menyelesaikan login/OTP... (Skrip akan otomatis lanjut jika berhasil masuk ke beranda)")
            
            # Menunggu sampai URL berubah menjadi beranda Shopee (maksimal 5 menit)
            page.wait_for_url("https://shopee.co.id/**", timeout=300000) 
            
            # 4. Ekstrak dan Simpan Kuki
            cookies = context.cookies()
            cookie_json = json.dumps(cookies)
            
            print("✅ Kuki berhasil diekstrak! Menyimpan ke Azure SQL...")
            
            # Upsert (Update jika ada, Insert jika baru)
            cursor.execute("""
                IF EXISTS (SELECT 1 FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE')
                    UPDATE AppConfigs SET ConfigValue = ?, LastUpdated = DATEADD(hour, 7, GETUTCDATE()) WHERE ConfigKey = 'SHOPEE_COOKIE'
                ELSE
                    INSERT INTO AppConfigs (ConfigKey, ConfigValue, LastUpdated) VALUES ('SHOPEE_COOKIE', ?, DATEADD(hour, 7, GETUTCDATE()))
            """, cookie_json, cookie_json)
            
            conn.commit()
            browser.close()
            print("🚀 SUPER SEKALI! Kuki sukses diamankan ke dalam Database Azure. Plan B Tahap 1 Selesai.")
            
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    update_shopee_cookie()