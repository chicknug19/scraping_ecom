import os
import json
import pyodbc
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Muat environment variable (Pastikan DB_SERVER, DB_USER, dll ada di .env)
load_dotenv()

# GANTI DENGAN KREDENSIAL AKUN TUMBALMU
SHOPEE_DUMMY_USER = "username_tumbal_kamu"
SHOPEE_DUMMY_PASS = "PasswordTumbal123!"

def save_cookie_to_azure(cookie_json):
    print("⚙️ Menghubungkan ke Azure SQL Database...")
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    driver = '{ODBC Driver 17 for SQL Server}'
    conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Buat tabel jika belum ada
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AppConfigs' and xtype='U')
            CREATE TABLE AppConfigs (
                ConfigKey VARCHAR(50) PRIMARY KEY,
                ConfigValue NVARCHAR(MAX),
                LastUpdated DATETIME
            )
        """)
        conn.commit()

        # Simpan atau perbarui Kuki
        cursor.execute("""
            IF EXISTS (SELECT 1 FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE')
                UPDATE AppConfigs SET ConfigValue = ?, LastUpdated = DATEADD(hour, 7, GETUTCDATE()) WHERE ConfigKey = 'SHOPEE_COOKIE'
            ELSE
                INSERT INTO AppConfigs (ConfigKey, ConfigValue, LastUpdated) VALUES ('SHOPEE_COOKIE', ?, DATEADD(hour, 7, GETUTCDATE()))
        """, cookie_json, cookie_json)
        
        conn.commit()
        print("🚀 SUPER SEKALI! Kuki terbaru sukses diamankan ke Database Azure.")
    except Exception as e:
        print(f"❌ Gagal menyimpan ke database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def auto_login_and_extract():
    print("\n🌐 Memulai Otomatisasi Login Shopee...")
    
    with sync_playwright() as p:
        # Menggunakan argumen anti-deteksi standar
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("Pemanasan menuju halaman Login...")
        page.goto("https://shopee.co.id/buyer/login", timeout=60000)

        # Usir popup bahasa jika muncul
        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=3000): lang_btn.click(); time.sleep(1)
        except: pass

        try:
            print("⌨️ Mengisi Username dan Password...")
            page.locator('input[name="loginKey"]').fill(SHOPEE_DUMMY_USER)
            time.sleep(0.5)
            page.locator('input[name="password"]').fill(SHOPEE_DUMMY_PASS)
            time.sleep(1)
            
            # Tekan Enter untuk login
            page.keyboard.press("Enter")
            
            print("\n🧩 GILIRANMU! Silakan geser puzzle slider di layar (dan masukkan OTP jika ada).")
            print("⏳ Menunggu kamu berhasil masuk ke beranda (Maks 3 menit)...")
            
            # Skrip akan diam menunggu sampai URL berubah menjadi beranda Shopee
            page.wait_for_url("https://shopee.co.id/**", timeout=180000) 
            
            print("✅ Berhasil Login! Menyedot Kuki...")
            time.sleep(3) # Beri waktu agar kuki sesi tersimpan sempurna di browser
            
            # Ekstrak kuki
            cookies = context.cookies()
            cookie_json = json.dumps(cookies)
            
            # Panggil fungsi simpan ke Azure
            save_cookie_to_azure(cookie_json)
            
        except Exception as e:
            print(f"❌ Proses login gagal atau timeout: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    auto_login_and_extract()