import os
import time
import json
import re
from playwright.sync_api import sync_playwright
import pandas as pd

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Ubah definisi fungsi untuk menerima parameter
def get_seller_orders(start_date_raw, end_date_raw):
    print(f"\n📦 Memulai Ekstraksi Data Pesanan ({start_date_raw} hingga {end_date_raw})...")
    
    target_url = "https://seller.shopee.co.id/portal/sale/order?type=toship&source=to_process"
    excel_filename = os.path.join(DOWNLOAD_DIR, "data_pesanan_terbaru.xlsx")
    extracted_orders = []

    # =======================================================
    # FASE 0: PEMBERSIHAN FILE LAMA (SANGAT PENTING!)
    # =======================================================
    if os.path.exists(excel_filename):
        os.remove(excel_filename)
        print(f"🗑️ Menghapus file Excel sisa kemarin agar tidak terjadi duplikasi data.")

    # =======================================================
    # FASE 1: OTOMASI DOWNLOAD DENGAN PLAYWRIGHT
    # =======================================================
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            accept_downloads=True
        )

        if os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                    formatted_cookies = [{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_data]
                    context.add_cookies(formatted_cookies)
                print("✅ Cookies berhasil dimuat.")
            except Exception as e:
                print(f"❌ Error membaca cookies.json: {e}")
        else:
            print("⚠️ File cookies.json tidak ditemukan!")

        page = context.new_page()

        def basmi_popup():
            try:
                got_it_btn = page.locator("button", has_text=re.compile(r"Got [iI]t|Mengerti|Tutup")).first
                if got_it_btn.is_visible(timeout=1500):
                    print("   💡 Pop-up 'Got It/Mengerti' terdeteksi! Menyingkirkan...")
                    got_it_btn.click(force=True)
                    time.sleep(2)
            except:
                pass

        try:
            print(f"Membuka halaman To Ship: {target_url}")
            page.goto(target_url, timeout=90000, wait_until="domcontentloaded")
            
            print("⏳ Menunggu halaman termuat sempurna...")
            time.sleep(8) 
            
            basmi_popup()

            # --- LANGKAH 1: KLIK TOMBOL EXPORT UTAMA ---
            print("📥 Mengklik tombol Export utama...")
            export_main_btn = page.locator("button", has_text="Export").first
            if export_main_btn.is_visible(timeout=10000):
                export_main_btn.click(force=True)
            time.sleep(4) 
            
            basmi_popup()

           # --- LANGKAH 2: KLIK EXPORT DI POP-UP KALENDER ---
            print("📅 Mengisi rentang tanggal sesuai pilihan (Frontend)...")
            try:
                # React mengirim format YYYY-MM-DD. Shopee butuh DD/MM/YYYY.
                # Kita konversi format tanggalnya terlebih dahulu.
                sd_parts = start_date_raw.split('-')
                ed_parts = end_date_raw.split('-')
                shopee_date_format = f"{sd_parts[2]}/{sd_parts[1]}/{sd_parts[0]} - {ed_parts[2]}/{ed_parts[1]}/{ed_parts[0]}"
                
                # Cari input textbox di dalam kalender modal
                date_input = page.locator(".shopee-modal__content input, div[role='dialog'] input").first
                
                if date_input.is_visible(timeout=5000):
                    # Hapus isi default dan ketik tanggal baru
                    date_input.click(force=True)
                    page.keyboard.press("Control+A") # Select all
                    page.keyboard.press("Backspace") # Hapus
                    date_input.fill(shopee_date_format)
                    page.keyboard.press("Enter")
                    print(f"✅ Berhasil mengetik tanggal: {shopee_date_format}")
                    time.sleep(2)
                
                # Klik tombol Export merah di dalam kalender
                modal_export_btn = page.locator(".eds-modal button:has-text('Export'), .shopee-modal__container button:has-text('Export')").first
                if modal_export_btn.is_visible(timeout=3000):
                    modal_export_btn.click(force=True)
                else:
                    # Fallback bar-bar
                    semua_tombol_export = page.locator("button", has_text="Export").all()
                    if len(semua_tombol_export) > 1:
                        semua_tombol_export[-1].click(force=True)
                        
            except Exception as e:
                print(f"⚠️ Gagal mengatur tanggal kalender: {e}")
                
            # --- LANGKAH 3: BUKA EXPORT HISTORY ---
            # Kita langsung buka history untuk memantau status 'Processing' dari sana
            time.sleep(5)
            print("📂 Membuka menu Export History untuk memantau pembuatan laporan...")
            history_btn = page.locator("button", has_text="Export History").first
            if history_btn.is_visible(timeout=5000):
                history_btn.click(force=True)
            
            # --- LANGKAH 4: NONGKRONG NUNGGU TOMBOL DOWNLOAD (POLLING LOGIC) ---
            print("⬇️ Menunggu server Shopee menyelesaikan laporan (Bisa memakan waktu hingga 1 menit)...")
            download_berhasil = False
            
            # Robot akan mengecek setiap 10 detik, maksimal 7 kali coba (70 detik)
            for i in range(7):
                basmi_popup() # Jaga-jaga popup muncul saat nunggu
                
                # Cari tombol download aktif pertama
                download_btn = page.locator("button:has-text('Download'):not([disabled])").first
                
                if download_btn.is_visible(timeout=2000):
                    print(f"✅ Tombol Download akhirnya muncul pada detik ke-{(i*10)+5}! Memulai pengunduhan...")
                    with page.expect_download(timeout=60000) as download_info:
                        download_btn.click(force=True)
                        
                    download = download_info.value
                    download.save_as(excel_filename)
                    print(f"💾 File Excel TERBARU berhasil diselamatkan ke: {excel_filename}")
                    download_berhasil = True
                    break
                else:
                    print(f"   Laporan masih berstatus 'Processing'... (Percobaan {i+1}/7)")
                    time.sleep(10)
            
            if not download_berhasil:
                print("❌ Menyerah. Shopee terlalu lama memproses laporan atau UI berubah.")

        except Exception as e:
            print(f"❌ Error navigasi/download: {e}")
        finally:
            browser.close()

    # =======================================================
    # FASE 2: BONGKAR EXCEL DENGAN PANDAS
    # =======================================================
    if os.path.exists(excel_filename):
        print("\n📊 Membedah data dari file Excel menggunakan Pandas...")
        try:
            df = pd.read_excel(excel_filename)
            df = df.fillna("")
            
            for index, row in df.iterrows():
                if str(row.get("No. Pesanan", "")).strip() == "":
                    continue
                    
                order_data = {
                    "order_sn": str(row.get("No. Pesanan", "")),
                    "username": str(row.get("Username (Pembeli)", "")),
                    "item_name": str(row.get("Nama Produk", "")),
                    "sku": str(row.get("Nomor Referensi SKU", "")),
                    "address": str(row.get("Alamat Pengiriman", "")),
                    "city": str(row.get("Kota/Kabupaten", "")),
                    "province": str(row.get("Provinsi", "")),
                    "shipping_channel": str(row.get("Opsi Pengiriman", ""))
                }
                extracted_orders.append(order_data)
                
            print(f"✅ Berhasil mengekstrak {len(extracted_orders)} pesanan TERBARU dari Excel.")
            
        except Exception as e:
            print(f"❌ Error saat membaca Excel: {e}")
    else:
        print("⚠️ File Excel tidak ditemukan. Proses ekstraksi dibatalkan karena tidak ada data yang bisa dibaca.")

    return extracted_orders

if __name__ == "__main__":
    orders = get_seller_orders()
    if orders:
        print(f"\nContoh Data Pertama: {orders[0]}")