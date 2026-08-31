import json
import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import time

# --- FUNGSI 1: MENCARI URL KOMPETITOR ---
# Tambahkan parameter location pada fungsi
def get_competitor_urls(keyword, limit=10, location=""):
    print(f"\n🔍 [FASE 1] Mencari {limit} URL untuk kata kunci: '{keyword}' (Lokasi: {location})...")
    
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://shopee.co.id/search?keyword={encoded_keyword}"
    
    # Jika lokasi dipilih, tambahkan parameter wilayah ke URL Shopee
    if location:
        encoded_location = urllib.parse.quote(location)
        search_url += f"&locations={encoded_location}"
        
    product_links = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        if os.path.exists("cookies.json"):
            with open("cookies.json", "r", encoding="utf-8") as f:
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto(search_url, timeout=45000, wait_until="commit")
        except Exception as e:
            print(f"Info navigasi search: {e}")

        print("Menunggu elemen produk dimuat di halaman pencarian...")
        try:
            page.locator("a[href*='-i.']").first.wait_for(timeout=15000)
        except:
            time.sleep(5)

        print("Menggulir halaman untuk memuat produk...")
        for _ in range(4):
            page.mouse.wheel(0, 1000)
            time.sleep(2)
        
        try:
            elements = page.locator("a[href*='-i.']").element_handles()
            for el in elements:
                href = el.get_attribute("href")
                if href:
                    clean_url = ("https://shopee.co.id" + href).split("?")[0]
                    if clean_url not in product_links:
                        product_links.append(clean_url)
                    if len(product_links) >= limit:
                        break
        except Exception as e:
            print(f"Error saat ekstrak link pencarian: {e}")
        finally:
            browser.close()
            
    print(f"✅ Ditemukan {len(product_links)} link target.")
    return product_links

# --- FUNGSI 2: MENARIK DATA PRODUK ---
def scrape_shopee_playwright(product_url):
    print(f"Mengakses: {product_url}")
    result_data = None 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        if os.path.exists("cookies.json"):
            with open("cookies.json", "r", encoding="utf-8") as f:
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        extracted_data = {'api_info': None}

        def handle_response(response):
            if "api/v4/item/get" in response.url or "api/v4/pdp/get_pc" in response.url:
                if response.status == 200:
                    try:
                        json_data = response.json()
                        if 'data' in json_data:
                            extracted_data['api_info'] = json_data['data'].get('item', json_data['data'])
                    except:
                        pass

        page.on("response", handle_response)

        try:
            page.goto(product_url, timeout=45000)
        except Exception as e:
            pass 

        time.sleep(6) 

        try:
            full_page_text = page.inner_text("body")
            
            match_ratings = re.search(r'([\d.,]+[KMRB+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            total_ratings = match_ratings.group(1) if match_ratings else "0"

            match_sold = re.search(r'([\d.,]+[KMRB+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            historical_sold = match_sold.group(1).upper() if match_sold else "0"

            # Mengambil Nama Toko langsung dari elemen teks di halaman (biasanya tombol kunjungi toko)
            shop_name = "Toko Tidak Ditemukan"
            try:
                # Mencoba mengambil teks dari elemen nama toko di panel penjual
                shop_name = page.locator(".event-collapse ~ div ._3L-_54, .flex.items-center.f > div._3L-_54, .shop-name").first.inner_text(timeout=3000).strip()
            except:
                # Cadangan: ambil dari teks umum jika struktur berubah
                pass

            if extracted_data['api_info']:
                info = extracted_data['api_info']
                item_name = info.get('name') or info.get('title', 'Nama tidak ditemukan')
                rating_star = info.get('item_rating', {}).get('rating_star', 0.0)
                shop_location = info.get('shop_location', 'Lokasi tidak diketahui')
                
                image_hash = info.get('image', '')
                image_url = f"https://cf.shopee.co.id/file/{image_hash}" if image_hash else ""

                models = info.get('models', [])
                parsed_variants = []
                for model in models:
                    parsed_variants.append({
                        "variant_name": model.get('name'),
                        "price": model.get('price') / 100000
                    })
                
                result_data = {
                    "shop_name": shop_name, 
                    "item_name": item_name,
                    "rating_star": round(rating_star, 1),
                    "total_ratings": total_ratings,
                    "sold": historical_sold,
                    "image_url": image_url,
                    "location": shop_location,
                    "variants": parsed_variants,
                    "source_url": product_url
                }
        except Exception as e:
            print(f"Error saat mengekstrak teks produk: {e}")
        finally:
            browser.close()
            
    return result_data