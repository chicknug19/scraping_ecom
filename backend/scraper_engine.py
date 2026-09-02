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


# --- FUNGSI 4: MENCARI URL PRODUK BERDASARKAN TOKO KOMPETITOR ---
def get_store_product_urls(username, keyword="", limit=10, is_all=False):
    target_limit = 9999 if is_all else limit
    print(f"\n🏬 [FASE 1] Menjelajah toko '{username}' | Pencarian: '{keyword}' | Target: {target_limit} produk...")
    
    if keyword:
        encoded_keyword = urllib.parse.quote(keyword)
        shop_url = f"https://shopee.co.id/{username}?page=0&sortBy=pop&keyword={encoded_keyword}"
    else:
        shop_url = f"https://shopee.co.id/{username}?page=0&sortBy=pop"
        
    product_links = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # --- LOGIKA PEMUATAN KUKI ---
        cookies_env = os.getenv("SHOPEE_COOKIES")
        if cookies_env:
            try:
                cookies_data = json.loads(cookies_env)
                context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_data])
            except: pass
        elif os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
            except: pass
            
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"Membuka URL: {shop_url}")
        try:
            # wait_until domcontentloaded lebih stabil daripada wait_until commit
            page.goto(shop_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4) # Wajib jeda agar JS Shopee sempat bangun
        except Exception as e:
            print(f"Info navigasi toko: {e}")

        # 1. Tutup Popup Bahasa (Bila muncul)
        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=2000):
                lang_btn.click()
                time.sleep(1)
        except: pass

        # 2. Tutup Popup Voucher/Iklan (Klik paksa area kosong di pojok kiri atas)
        page.mouse.click(5, 5)
        time.sleep(1)

        # 3. Jika tanpa keyword, paksa Shopee pindah ke tab "Semua Produk" agar banner lenyap
        if not keyword:
            try:
                tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
                if tab_semua.is_visible(timeout=2000):
                    tab_semua.click()
                    time.sleep(3)
            except: pass

        print(f"Menyapu etalase {username} secara real-time...")
        
        # JURUS BARU: Sapu Layar (Scroll pelan + Ekstrak di tengah jalan)
        scroll_attempts = 60 if is_all else (target_limit // 10) + 5 
        
        for _ in range(scroll_attempts):
            try:
                # Ambil apa saja yang terlihat di layar SAAT INI
                elements = page.locator("a[href*='-i.']").element_handles()
                for el in elements:
                    href = el.get_attribute("href")
                    if href:
                        clean_url = ("https://shopee.co.id" + href).split("?")[0]
                        
                        # Filter Kata Kunci oleh Python (Versi Super Akurat)
                        if keyword:
                            url_text = clean_url.lower().replace("-", " ")
                            search_term = keyword.lower()
                            
                            # Cek persis seluruh frasa
                            is_match = search_term in url_text
                            
                            # Jika tidak cocok persis, cek per kata menggunakan batas kata (Word Boundary)
                            if not is_match:
                                keyword_parts = search_term.split()
                                match_count = 0
                                for part in keyword_parts:
                                    # Menggunakan regex \b agar "12" tidak cocok dengan "128gb"
                                    if re.search(r'\b' + re.escape(part) + r'\b', url_text):
                                        match_count += 1
                                        
                                if match_count == len(keyword_parts):
                                    is_match = True
                                    
                            if not is_match:
                                continue
                                
                        if clean_url not in product_links and "ads" not in clean_url.lower():
                            product_links.append(clean_url)
                            
                        if len(product_links) >= target_limit:
                            break
            except:
                pass
                
            if len(product_links) >= target_limit:
                break
                
            # Scroll pelan-pelan lalu tunggu 2 detik agar Shopee memuat produk berikutnya
            page.mouse.wheel(0, 800)
            time.sleep(2) 
            
        browser.close()
        
    print(f"✅ Ditemukan {len(product_links)} link produk dari toko {username}.")
    return product_links[:target_limit]


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
            
            # --- JURUS CADANGAN DARI LAYAR (DOM HTML) ---
            match_ratings = re.search(r'([\d.,]+[KMRBJTm+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            backup_ratings = match_ratings.group(1) if match_ratings else "0"

            match_sold = re.search(r'([\d.,]+[KMRBJT+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            # PERBAIKAN 1: Nama variabel diubah menjadi backup_sold
            backup_sold = match_sold.group(1).upper() if match_sold else "0" 
            
            # --- LOGIKA MENANGKAP NIB ---
            match_nib = re.search(r'NIB:\s*([0-9*]+)', full_page_text, re.IGNORECASE)
            nib_value = match_nib.group(1) if match_nib else "Tidak Ada NIB"
            # ---------------------------------------------
            
            if extracted_data['api_info']:
                info = extracted_data['api_info']
                full_data = extracted_data['api_data_full'] 
                    
                item_name = info.get('name') or info.get('title', 'Nama tidak ditemukan')
                rating_star = info.get('item_rating', {}).get('rating_star', 0.0)
                shop_location = info.get('shop_location', 'Lokasi tidak diketahui')
                
                review_data = info.get('product_review', {})
                
                # EKSTRAKSI CERDAS: Utamakan JSON. Jika JSON kosong, pakai backup dari layar!
                total_ratings_raw = str(review_data.get('total_rating_count') or review_data.get('rating_count', [0])[0] or backup_ratings)
                sold_raw = str(review_data.get('historical_sold_display') or review_data.get('historical_sold') or info.get('historical_sold') or backup_sold)
                    
                shop_detailed = full_data.get('shop_detailed', {}) or info.get('shop_detailed', {})
                shop_name = shop_detailed.get('name', extracted_data['shop_name_api'] or 'Toko Tidak Ditemukan')
                shop_username = shop_detailed.get('account', {}).get('username', '')
                followers_count = shop_detailed.get('follower_count', 0)
                total_products = shop_detailed.get('item_count', 0)
                shop_rating = shop_detailed.get('rating_star', 0.0)

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
                
                # PERBAIKAN 2: Memasukkan variabel toko yang tertinggal ke dalam result_data
                result_data = {
                    "shop_name": shop_name, 
                    "username": shop_username,
                    "item_name": item_name,
                    "rating_star": round(rating_star, 1),
                    "total_ratings": parse_shopee_metric(total_ratings_raw),
                    "sold": parse_shopee_metric(sold_raw),
                    "image_url": image_url,
                    "location": shop_location,
                    "variants": parsed_variants,
                    "source_url": product_url,
                    "nib": nib_value,
                    "followers": followers_count,
                    "total_products": total_products,
                    "shop_rating": round(shop_rating, 1)
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