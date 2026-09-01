import json
import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import time

# --- FUNGSI UTILITAS ---
def parse_shopee_metric(text_value):
    """
    Mengubah teks seperti '7,7m', '10RB', '1.5k' menjadi integer murni.
    """
    if not text_value:
        return 0
        
    text_clean = text_value.lower().strip().replace(',', '.')
    match = re.search(r'([\d.]+)\s*([a-z]*)', text_clean)
    if match:
        number = float(match.group(1))
        suffix = match.group(2)
        
        if suffix in ['m', 'jt', 'juta']:
            return int(number * 1000000)
        elif suffix in ['k', 'rb', 'ribu']:
            return int(number * 1000)
        return int(number)
    return 0

# --- FUNGSI 1: MATA-MATA PROFIL TOKO KOMPETITOR ---
def scrape_shop_profile(username):
    print(f"\n🕵️ [MATA-MATA TOKO] Memeriksa profil: {username}...")
    shop_url = f"https://shopee.co.id/{username}"
    shop_data = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # --- LOGIKA PEMUATAN KUKI AMAN ---
        cookies_env = os.getenv("SHOPEE_COOKIES")
        if cookies_env:
            try:
                cookies_data = json.loads(cookies_env)
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_data])
                print("✅ Kuki berhasil dimuat dari Environment Variable Azure!")
            except Exception as e:
                print("❌ Error memuat kuki dari environment:", e)
        elif os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
                print("✅ Kuki berhasil dimuat dari file lokal cookies.json!")
            except Exception as e:
                print("❌ Error membaca cookies.json:", e)
        else:
            print("⚠️ Peringatan: Tidak ada kuki yang ditemukan. Berjalan dalam mode Guest.")
        
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto(shop_url, timeout=45000, wait_until="commit")
            
            try:
                page.locator("h1.section-seller-overview-horizontal__portrait-name").wait_for(timeout=10000)
            except:
                print(f"❌ Toko '{username}' tidak ditemukan atau salah ejaan!")
                return {"error": f"Toko '{username}' tidak ditemukan. Cek ejaan username."}

            shop_name_text = page.locator("h1.section-seller-overview-horizontal__portrait-name").inner_text()
            full_text = page.inner_text("body")
            
            followers_match = re.search(r'Pengikut\s*\n?\s*([\d.,]+[KMRBJTm+]*)|Followers\s*\n?\s*([\d.,]+[KMRBJTm+]*)', full_text, re.IGNORECASE)
            products_match = re.search(r'Produk\s*\n?\s*([\d.,]+)|Products\s*\n?\s*([\d.,]+)', full_text, re.IGNORECASE)
            
            followers_raw = followers_match.group(1) or followers_match.group(2) if followers_match else "0"
            products_raw = products_match.group(1) or products_match.group(2) if products_match else "0"
            
            shop_data = {
                "username": username,
                "shop_name": shop_name_text.strip(),
                "followers": parse_shopee_metric(followers_raw),
                "total_products": parse_shopee_metric(products_raw)
            }
            print(f"📊 Hasil: {shop_data['shop_name']} | {shop_data['followers']} Followers | {shop_data['total_products']} Produk")
            
        except Exception as e:
            print(f"Error saat scan profil toko: {e}")
            return {"error": str(e)}
        finally:
            browser.close()
            
    return shop_data

# --- FUNGSI 2: MENCARI URL KOMPETITOR ---
def get_competitor_urls(keyword, limit=10, location=""):
    print(f"\n🔍 [FASE 1] Mencari {limit} URL untuk kata kunci: '{keyword}' (Lokasi: {location})...")
    
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://shopee.co.id/search?keyword={encoded_keyword}"
    
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
        
        # --- LOGIKA PEMUATAN KUKI AMAN ---
        cookies_env = os.getenv("SHOPEE_COOKIES")
        if cookies_env:
            try:
                cookies_data = json.loads(cookies_env)
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_data])
                print("✅ Kuki berhasil dimuat dari Environment Variable Azure!")
            except Exception as e:
                print("❌ Error memuat kuki dari environment:", e)
        elif os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
                print("✅ Kuki berhasil dimuat dari file lokal cookies.json!")
            except Exception as e:
                print("❌ Error membaca cookies.json:", e)
        else:
            print("⚠️ Peringatan: Tidak ada kuki yang ditemukan. Berjalan dalam mode Guest.")
            
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

        scroll_attempts = (limit // 10) + 3 
        print(f"Menggulir halaman {scroll_attempts} kali untuk memuat {limit} produk...")
        
        for _ in range(scroll_attempts):
            page.mouse.wheel(0, 1500)
            time.sleep(1.5)
        
        try:
            elements = page.locator("a[href*='-i.']").element_handles()
            for el in elements:
                href = el.get_attribute("href")
                if href:
                    clean_url = ("https://shopee.co.id" + href).split("?")[0]
                    if clean_url not in product_links and "ads" not in clean_url.lower():
                        product_links.append(clean_url)
                    if len(product_links) >= limit:
                        break
        except Exception as e:
            print(f"Error saat ekstrak link pencarian: {e}")
        finally:
            browser.close()
            
    print(f"✅ Ditemukan {len(product_links)} link target.")
    return product_links

# --- FUNGSI 3: MENARIK DATA PRODUK ---
def scrape_shopee_playwright(product_url):
    print(f"Mengakses: {product_url}")
    result_data = None 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # --- LOGIKA PEMUATAN KUKI AMAN ---
        cookies_env = os.getenv("SHOPEE_COOKIES")
        if cookies_env:
            try:
                cookies_data = json.loads(cookies_env)
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_data])
                print("✅ Kuki berhasil dimuat dari Environment Variable Azure!")
            except Exception as e:
                print("❌ Error memuat kuki dari environment:", e)
        elif os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
                print("✅ Kuki berhasil dimuat dari file lokal cookies.json!")
            except Exception as e:
                print("❌ Error membaca cookies.json:", e)
        else:
            print("⚠️ Peringatan: Tidak ada kuki yang ditemukan. Berjalan dalam mode Guest.")

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        extracted_data = {'api_info': None, 'shop_name_api': None, 'api_data_full': {}}

        def handle_response(response):
            if "api/v4" in response.url:
                if response.status == 200:
                    try:
                        json_data = response.json()
                        if "item/get" in response.url or "pdp/get_pc" in response.url:
                            if 'data' in json_data:
                                extracted_data['api_data_full'] = json_data['data']
                                extracted_data['api_info'] = json_data['data'].get('item', json_data['data'])
                        if "shop" in response.url:
                            if 'data' in json_data and 'name' in json_data['data']:
                                extracted_data['shop_name_api'] = json_data['data']['name']
                            elif 'data' in json_data and 'shop_name' in json_data['data']:
                                extracted_data['shop_name_api'] = json_data['data']['shop_name']
                    except:
                        pass

        page.on("response", handle_response)

        try:
            page.goto(product_url, timeout=45000)
        except Exception as e:
            pass 

        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=3000):
                lang_btn.click()
                time.sleep(1)
        except:
            pass

        print("Menggulir halaman produk untuk merender profil toko...")
        page.mouse.wheel(0, 800)
        time.sleep(3)
        page.mouse.wheel(0, 500)
        time.sleep(3)

        try:
            full_page_text = page.inner_text("body")
            
            match_ratings = re.search(r'([\d.,]+[KMRBJTm+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            total_ratings = match_ratings.group(1) if match_ratings else "0"

            match_sold = re.search(r'([\d.,]+[KMRBJT+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            historical_sold = match_sold.group(1).upper() if match_sold else "0"
            
            # --- LOGIKA BARU: MENANGKAP NIB ---
            match_nib = re.search(r'NIB:\s*([0-9*]+)', full_page_text, re.IGNORECASE)
            nib_value = match_nib.group(1) if match_nib else "Tidak Ada NIB"
            # -----------------------------------
            
            if extracted_data['api_info']:
                info = extracted_data['api_info']
                full_data = extracted_data['api_data_full'] 
                    
                item_name = info.get('name') or info.get('title', 'Nama tidak ditemukan')
                rating_star = info.get('item_rating', {}).get('rating_star', 0.0)
                shop_location = info.get('shop_location', 'Lokasi tidak diketahui')
                    
                shop_name = "Toko Tidak Ditemukan"
                if 'shop_detailed' in full_data and 'name' in full_data['shop_detailed']:
                    shop_name = full_data['shop_detailed']['name']
                elif 'shop_detailed' in info and 'name' in info['shop_detailed']:
                    shop_name = info['shop_detailed']['name']
                elif extracted_data['shop_name_api']:
                    shop_name = extracted_data['shop_name_api']
                elif 'shop_basic' in info and 'name' in info['shop_basic']:
                    shop_name = info['shop_basic']['name']

                image_hash = info.get('image', '')
                image_url = f"https://cf.shopee.co.id/file/{image_hash}" if image_hash else ""

                models = info.get('models', [])
                parsed_variants = []
                for model in models:
                    v_name = model.get('name')
                    if not v_name or v_name.strip() == "":
                        v_name = "Default"
                        
                    parsed_variants.append({
                        "variant_name": v_name,
                        "price": model.get('price') / 100000
                    })
                
                result_data = {
                    "shop_name": shop_name, 
                    "item_name": item_name,
                    "rating_star": round(rating_star, 1),
                    "total_ratings": parse_shopee_metric(total_ratings),
                    "sold": parse_shopee_metric(historical_sold),
                    "image_url": image_url,
                    "location": shop_location,
                    "variants": parsed_variants,
                    "source_url": product_url,
                    "nib": nib_value # Masukkan NIB ke dalam data produk
                }

                # --- KODE UNTUK DUMP JSON (UNTUK DEBUGGING) ---
                with open("debug_api_product.json", "w", encoding="utf-8") as f:
                    json.dump(extracted_data, f, indent=4, ensure_ascii=False)
                # ----------------------------------------------

        except Exception as e:
            print(f"Error saat mengekstrak teks produk: {e}")
        finally:
            browser.close()
            
    return result_data