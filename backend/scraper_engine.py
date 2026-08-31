import json
import os
import re
from playwright.sync_api import sync_playwright
import time

def scrape_shopee_playwright(product_url):
    print("Membuka browser dengan akun tumbal (Hybrid Mode)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 1. Memuat Cookies
        if os.path.exists("cookies.json"):
            with open("cookies.json", "r", encoding="utf-8") as f:
                raw_cookies = json.load(f)
            cleaned_cookies = [{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in raw_cookies]
            context.add_cookies(cleaned_cookies)
        else:
            print("Error: File cookies.json tidak ditemukan.")
            return

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.add_init_script("window.navigator.chrome = { runtime: {} };")

        extracted_data = {'api_info': None}

        # 2. PENYADAP API (Hanya fokus menangkap Harga, Varian, dan Bintang)
        def handle_response(response):
            if "api/v4/item/get" in response.url or "api/v4/pdp/get_pc" in response.url:
                if response.status == 200:
                    try:
                        json_data = response.json()
                        if 'data' in json_data:
                            if 'item' in json_data['data']:
                                extracted_data['api_info'] = json_data['data']['item']
                            else:
                                extracted_data['api_info'] = json_data['data']
                    except:
                        pass

        page.on("response", handle_response)

        try:
            # 3. Navigasi Cepat
            page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            
            # Beri waktu 5 detik agar API JSON tertangkap dan teks web muncul
            time.sleep(5)

            # 4. EKSTRAKSI TEKS WEB (Fokus mencari Ulasan & Terjual)
            full_page_text = page.inner_text("body")

            # Regex yang diperbarui (Menoleransi adanya spasi atau enter di antara teks)
            match_ratings = re.search(r'([\d.,]+[KMRB+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            total_ratings = match_ratings.group(1) if match_ratings else "0"

            match_sold = re.search(r'([\d.,]+[KMRB+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            historical_sold = match_sold.group(1).upper() if match_sold else "Tidak ditemukan"

            # 5. GABUNGAN DATA (Mencetak hasil akhir yang utuh)
            if extracted_data['api_info']:
                info = extracted_data['api_info']
                item_name = info.get('name') or info.get('title', 'Nama tidak ditemukan')
                
                # Bintang diambil dengan aman dari API
                item_rating = info.get('item_rating', {})
                rating_star = item_rating.get('rating_star', 0.0)

                print(f"\n==========================================")
                print(f"📦 Produk: {item_name}")
                print(f"⭐ Rating: {rating_star:.1f} / 5.0 (Ulasan: {total_ratings})")
                print(f"🔥 Terjual: {historical_sold}")
                print(f"==========================================\n")

                models = info.get('models', [])
                if not models:
                    print("- Produk ini tidak memiliki varian.")
                
                for model in models:
                    variant_name = model.get('name')
                    price = model.get('price') / 100000
                    print(f"- Varian: {variant_name} | Harga: Rp {price:,.0f}")
            else:
                print("\nMasih gagal menangkap API JSON. Coba perbarui cookies.")

        except Exception as e:
            print(f"Terjadi error: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    TEST_URL = "https://shopee.co.id/PROMO!!!-Maybelline-Superstay-Matte-Ink-Liquid-Long-Lasting-Waterproof-Matte-Lipstick-Lipcream-Make-Up-Transferproof-i.1858716991.49462262306" 
    scrape_shopee_playwright(TEST_URL)