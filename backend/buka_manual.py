import os
from playwright.sync_api import sync_playwright

# Pastikan ini sama persis dengan yang ada di scraper_engine.py
PROFILE_DIR = os.path.join(os.getcwd(), "ShopeeBotProfile")

def buka_browser_manual():
    print("Membuka profil bot untuk intervensi manusia...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, 
            channel="chrome", 
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
        page.goto("https://shopee.co.id/")
        
        print("\n" + "="*60)
        print("🚀 BROWSER MANUAL TERBUKA!")
        print("1. Silakan Login ke akun Shopee (Wajib agar tidak dicurigai bot).")
        print("2. Selesaikan puzzle captcha jika muncul.")
        print("3. Jika sudah berada di beranda Shopee dan berhasil login...")
        print("="*60 + "\n")
        
        # Skrip akan tertahan di sini sampai kamu menekan tombol ENTER di terminal
        input("Tekan tombol ENTER di sini JIKA SUDAH SELESAI LOGIN untuk menyimpan sesi...")
        
        context.close()
        print("✅ Sesi berhasil disimpan! Silakan jalankan ulang main.py")

if __name__ == "__main__":
    buka_browser_manual()