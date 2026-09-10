from playwright.sync_api import sync_playwright
import time
import os

# Ini akan membuat folder khusus penyimpan data browser di foldermu saat ini
USER_DIR = os.path.join(os.getcwd(), "shopee_profile")

def setup_persistent_profile():
    print(f"📁 Membuat profil browser permanen di: {USER_DIR}")
    
    with sync_playwright() as p:
        # Meluncurkan browser dengan profil persisten
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DIR,
            headless=False, # Harus False agar kamu bisa lihat
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1920, "height": 1080}
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("🌐 Menuju halaman Shopee...")
        page.goto("https://shopee.co.id/buyer/login")
        
        print("=========================================")
        print("👉 GILIRANMU: Silakan login secara MANUAL.")
        print("👉 Selesaikan puzzle, masukkan OTP jika ada.")
        print("👉 Jika sudah berhasil masuk ke beranda, biarkan saja.")
        print("=========================================")
        
        # Skrip akan menunggu sampai kamu benar-benar berada di beranda utama Shopee
        page.wait_for_url("https://shopee.co.id/**", timeout=300000) 
        
        print("✅ LOGIN SUKSES! Mengunci profil dan menyimpan seluruh riwayat browser...")
        time.sleep(5) # Beri waktu agar cache dan local storage tersimpan ke harddisk
        
        browser.close()
        print("🎯 Profil berhasil dibuat! Mulai sekarang, scraper akan menggunakan profil ini.")

if __name__ == "__main__":
    setup_persistent_profile()