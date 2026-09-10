import json
import os
import re
import time
import random
import cv2
import numpy as np
import pyodbc
import urllib.parse
from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv
from playwright_stealth import Stealth

load_dotenv()

# --- KREDENSIAL AKUN TUMBAL ---
SHOPEE_USER = "ikantauco695"
SHOPEE_PASS = "f-d4KJuVyzCnxkt" 

# ==========================================
# BAGIAN 1: SISTEM DATABASE & KUKI
# ==========================================
def parse_shopee_metric(text_value):
    if not text_value: return 0
    text_clean = text_value.lower().strip().replace(',', '.')
    match = re.search(r'([\d.]+)\s*([a-z]*)', text_clean)
    if match:
        number, suffix = float(match.group(1)), match.group(2)
        if suffix in ['m', 'jt', 'juta']: return int(number * 1000000)
        elif suffix in ['k', 'rb', 'ribu']: return int(number * 1000)
        return int(number)
    return 0

def get_cookie_from_db():
    try:
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={os.getenv("DB_SERVER")};PORT=1433;DATABASE={os.getenv("DB_NAME")};UID={os.getenv("DB_USER")};PWD={os.getenv("DB_PASS")}'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT ConfigValue FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE'")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]: return json.loads(row[0])
    except Exception as e: print(f"❌ Error DB Kuki: {e}")
    return None

def save_cookie_to_azure(cookie_json):
    try:
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={os.getenv("DB_SERVER")};PORT=1433;DATABASE={os.getenv("DB_NAME")};UID={os.getenv("DB_USER")};PWD={os.getenv("DB_PASS")}'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AppConfigs' and xtype='U')
            CREATE TABLE AppConfigs (ConfigKey VARCHAR(50) PRIMARY KEY, ConfigValue NVARCHAR(MAX), LastUpdated DATETIME)
        """)
        cursor.execute("""
            IF EXISTS (SELECT 1 FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE')
                UPDATE AppConfigs SET ConfigValue = ?, LastUpdated = DATEADD(hour, 7, GETUTCDATE()) WHERE ConfigKey = 'SHOPEE_COOKIE'
            ELSE
                INSERT INTO AppConfigs (ConfigKey, ConfigValue, LastUpdated) VALUES ('SHOPEE_COOKIE', ?, DATEADD(hour, 7, GETUTCDATE()))
        """, cookie_json, cookie_json)
        conn.commit()
        conn.close()
        print("🚀 Kuki baru sukses diamankan ke Azure SQL!")
    except Exception as e: pass

def load_cookies_aman(context):
    cookies_db = get_cookie_from_db()
    if cookies_db:
        context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_db])
        print("✅ Kuki dimuat dari Azure SQL Database!")
    elif os.path.exists("cookies.json"):
        with open("cookies.json", "r", encoding="utf-8") as f:
            context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
        print("✅ Kuki dimuat dari cookies.json lokal!")

# ==========================================
# BAGIAN 2: SISTEM AI (COMPUTER VISION & INTERCEPTOR)
# ==========================================
def get_slider_distance(bg_path, puzzle_path):
    print("🧠 [AI Vision] Membaca matriks gambar lokal...")
    bg, puzzle = cv2.imread(bg_path, 0), cv2.imread(puzzle_path, 0)
    result = cv2.matchTemplate(cv2.Canny(bg, 100, 200), cv2.Canny(puzzle, 100, 200), cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)
    return max_loc[0]

def auto_solve_slider(page):
    try:
        print("🧩 [Anti-Bot] Memecahkan Slider secara visual...")
        bg_element = page.locator('.shopee-captcha__bg-image').first
        puzzle_element = page.locator('.shopee-captcha__puzzle-image').first
        slider_btn = page.locator('.shopee-captcha__slider-button').first
        
        bg_element.wait_for(state="visible", timeout=10000)
        
        # PERBAIKAN: Gunakan Screenshot elemen (Bypass proteksi enkripsi gambar Base64)
        bg_element.screenshot(path="bg_temp.png")
        puzzle_element.screenshot(path="puzzle_temp.png")
        
        jarak_x = get_slider_distance("bg_temp.png", "puzzle_temp.png")
        print(f"🤖 Menggeser mouse sejauh {jarak_x} pixel...")
        
        box = slider_btn.bounding_box()
        start_x, start_y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(0.2)
        
        current_x, sisa = start_x, jarak_x
        while sisa > 0:
            step = min(random.randint(5, 20), sisa)
            current_x += step
            sisa -= step
            page.mouse.move(current_x, start_y + random.uniform(-2, 2))
            time.sleep(random.uniform(0.01, 0.04))
            
        page.mouse.up()
        print("✅ [Anti-Bot] Slider berhasil digeser!")
        time.sleep(4) 
        return True
    except Exception as e:
        print(f"⚠️ Error memecahkan Slider: {e}")
        return False

def destroy_popup(page):
    try:
        lang_btn = page.locator('button, a, div').filter(has_text="Bahasa Indonesia").first
        if lang_btn.is_visible(timeout=3000): 
            lang_btn.click()
            time.sleep(2)
    except: pass
    page.mouse.click(5, 5)
    page.keyboard.press("Escape")
    time.sleep(1.5)

def check_and_resolve_security(page, context, original_url, kedalaman=0):
    """Fungsi Rekursif: Mencegat pemblokiran dan memulihkan sesi"""
    if kedalaman > 3: 
        print("🛑 Batas percobaan keamanan tercapai (Looping protection).")
        return

    # Beri napas sedikit agar DOM (layar) stabil
    time.sleep(2)
    current_url = page.url
    
    # --- KASUS 1: FORM LOGIN MUNCUL (PRIORITAS UTAMA) ---
    # Cek berdasarkan KOTAK INPUT, bukan sekadar URL (Lebih Akurat)
    username_field = page.get_by_placeholder("No. Handphone/Username/Email").first
    if "buyer/login" in current_url or username_field.is_visible():
        print("🚨 [Keamanan] Form Login terdeteksi. Memulai prosedur Auto-Login...")
        try:
            print("⏳ Menunggu form login aktif sepenuhnya...")
            username_field.wait_for(state="visible", timeout=15000)
            
            print("⌨️ Mengetik kredensial...")
            username_field.click()
            time.sleep(0.5)
            username_field.fill(SHOPEE_USER)
            time.sleep(1)
            
            password_field = page.get_by_placeholder("Password").first
            password_field.click()
            time.sleep(0.5)
            password_field.fill(SHOPEE_PASS)
            time.sleep(1)
            
            page.keyboard.press("Enter")
            time.sleep(5)
            
            # Jika Shopee melempar puzzle setelah kita enter
            if page.locator('.shopee-captcha__bg-image').is_visible():
                auto_solve_slider(page)
            
            page.wait_for_url("https://shopee.co.id/**", timeout=45000)
            print("✅ [Keamanan] Login Sukses! Menyimpan kuki baru...")
            save_cookie_to_azure(json.dumps(context.cookies()))
            
            print(f"🔄 Mengulang kembali navigasi ke target: {original_url}")
            page.goto(original_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
        except Exception as e: print(f"❌ Gagal Auto-Login: {e}")
        return # Selesai, jangan lanjut ke bawah

    # --- KASUS 2: Halaman "Masuk Diperlukan" (Traffic Error) ---
    elif "verify/traffic/error" in current_url or page.get_by_text("Masuk Diperlukan").is_visible():
        print("🚨 [Keamanan] Layar 'Masuk Diperlukan' terdeteksi.")
        try:
            # Gunakan get_by_text spesifik agar tidak tertukar dengan tombol lain
            login_btn = page.get_by_text("Log In", exact=True).last
            if not login_btn.is_visible():
                login_btn = page.locator("button, a, div").filter(has_text="Log In").last
                
            if login_btn.is_visible(timeout=5000):
                print("👉 Mengklik tombol Log In untuk pindah halaman...")
                login_btn.click()
                
                # PERBAIKAN KRUSIAL: Tunggu URL benar-benar berubah sebelum memanggil ulang!
                print("⏳ Menunggu transisi ke halaman login...")
                try:
                    page.wait_for_url("**/buyer/login**", timeout=15000)
                except: pass # Jika gagal tunggu, biarkan dipanggil ulang
                
                return check_and_resolve_security(page, context, original_url, kedalaman + 1)
        except Exception as e: print(f"⚠️ Gagal menekan Log In: {e}")
            
    # --- KASUS 3: Slider pencegat muncul tiba-tiba di tengah jalan ---
    elif page.locator('.shopee-captcha__bg-image').is_visible():
        print("🚨 [Keamanan] Slider pencegat muncul.")
        auto_solve_slider(page)
        save_cookie_to_azure(json.dumps(context.cookies()))
        time.sleep(3)
        return check_and_resolve_security(page, context, original_url, kedalaman + 1)
        
    # --- KASUS 4: Hard Block (Silakan Coba Lagi Nanti) ---
    elif "verify/captcha" in current_url or page.get_by_text("Silakan Coba Lagi Nanti").is_visible():
        print("🚨 [Keamanan] Terkena Hard Block dari Server.")
        try:
            coba_lagi_btn = page.get_by_text("Coba Lagi").last
            if coba_lagi_btn.is_visible(timeout=3000):
                print("👉 Mengklik 'Coba Lagi' untuk memancing puzzle...")
                coba_lagi_btn.click()
                time.sleep(5)
                return check_and_resolve_security(page, context, original_url, kedalaman + 1)
        except Exception as e: pass


# ==========================================
# BAGIAN 3: MESIN SCRAPER UTAMA
# ==========================================
def scrape_shop_profile(username):
    print(f"\n🕵️ [MATA-MATA TOKO] Memeriksa profil: {username}...")
    shop_url = f"https://shopee.co.id/{username}"
    shop_data = None
    
    with Stealth().use_sync(sync_playwright()) as p:
        USER_DIR = os.path.join(os.getcwd(), "shopee_profile")
        context = p.chromium.launch_persistent_context(user_data_dir=USER_DIR, headless=False, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1920, "height": 1080})
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto(shop_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            
            check_and_resolve_security(page, context, shop_url)
            destroy_popup(page)
            
            try: page.locator("h1.section-seller-overview-horizontal__portrait-name").wait_for(timeout=10000)
            except: return {"error": f"Toko '{username}' tidak ditemukan."}

            shop_name_text = page.locator("h1.section-seller-overview-horizontal__portrait-name").inner_text()
            full_text = page.inner_text("body")
            
            followers_match = re.search(r'Pengikut\s*\n?\s*([\d.,]+[KMRBJTm+]*)|Followers\s*\n?\s*([\d.,]+[KMRBJTm+]*)', full_text, re.IGNORECASE)
            products_match = re.search(r'Produk\s*\n?\s*([\d.,]+)|Products\s*\n?\s*([\d.,]+)', full_text, re.IGNORECASE)
            
            followers_raw = followers_match.group(1) or followers_match.group(2) if followers_match else "0"
            products_raw = products_match.group(1) or products_match.group(2) if products_match else "0"
            
            shop_data = {"username": username, "shop_name": shop_name_text.strip(), "followers": parse_shopee_metric(followers_raw), "total_products": parse_shopee_metric(products_raw)}
            print(f"📊 Hasil: {shop_data['shop_name']} | {shop_data['followers']} Followers")
        except Exception as e: return {"error": str(e)}
        finally: context.close()
    return shop_data

def get_competitor_urls(keyword, limit=10, location=""):
    print(f"\n🔍 [FASE 1] Mencari {limit} URL untuk: '{keyword}'...")
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://shopee.co.id/search?keyword={encoded_keyword}"
    if location: search_url += f"&locations={urllib.parse.quote(location)}"
    product_links = []
    
    with Stealth().use_sync(sync_playwright()) as p:
        USER_DIR = os.path.join(os.getcwd(), "shopee_profile")
        context = p.chromium.launch_persistent_context(user_data_dir=USER_DIR, headless=False, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1920, "height": 1080})
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            print("🔥 Melakukan pemanasan ke beranda...")
            page.goto("https://shopee.co.id/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            check_and_resolve_security(page, context, "https://shopee.co.id/")
            
            print(f"🚀 Menembak URL pencarian...")
            page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            check_and_resolve_security(page, context, search_url)
            destroy_popup(page)

            print("Menunggu elemen produk dimuat...")
            try: 
                page.locator("a[href*='-i.']").first.wait_for(timeout=15000)
            except: 
                print("⚠️ Produk tidak muncul. Mengecek ulang keamanan...")
                check_and_resolve_security(page, context, search_url)
                try: page.locator("a[href*='-i.']").first.wait_for(timeout=10000)
                except: pass

            scroll_attempts = (limit // 10) + 3 
            for _ in range(scroll_attempts):
                page.mouse.wheel(0, 1500)
                time.sleep(1.5)
            
            elements = page.locator("a[href*='-i.']").element_handles()
            for el in elements:
                href = el.get_attribute("href")
                if href:
                    clean_url = ("https://shopee.co.id" + href).split("?")[0]
                    if clean_url not in product_links and "ads" not in clean_url.lower():
                        product_links.append(clean_url)
                    if len(product_links) >= limit: break
        except Exception as e: print(f"Error ekstrak link: {e}")
        finally: context.close()
    print(f"✅ Ditemukan {len(product_links)} link target.")
    return product_links

def filter_urls_with_gemini(raw_products, keyword, target_limit):
    if not keyword or not raw_products: return [p['url'] for p in raw_products][:target_limit]
    print(f"🧠 Meminta Gemini menyaring {len(raw_products)} produk...")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = f"""Kamu filter e-commerce. User cari HP: "{keyword}". Pilih HANYA produk HP utama. Tolak AKSESORIS. Tolak beda seri. Data: {json.dumps(raw_products[:80], ensure_ascii=False)}. KEMBALIKAN ARRAY JSON MURNI BERISI URL SAJA."""
        response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)[:target_limit]
    except Exception as e: return [p['url'] for p in raw_products][:target_limit]

def get_store_product_urls(username, keyword="", limit=10, is_all=False):
    target_limit = 9999 if is_all else limit
    print(f"\n🏬 [FASE 1] Menjelajah toko '{username}' | Target: {target_limit} produk...")
    shop_url = f"https://shopee.co.id/{username}?page=0&sortBy=pop"
    product_links = []
    
    with Stealth().use_sync(sync_playwright()) as p:
        USER_DIR = os.path.join(os.getcwd(), "shopee_profile")
        context = p.chromium.launch_persistent_context(user_data_dir=USER_DIR, headless=False, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1920, "height": 1080})
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto(shop_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
            
            check_and_resolve_security(page, context, shop_url)
            destroy_popup(page)

            try:
                tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
                if tab_semua.is_visible(timeout=3000): tab_semua.click(); time.sleep(3)
            except: pass

            scroll_attempts = 50 if (is_all or keyword) else (target_limit // 10) + 5 
            for _ in range(scroll_attempts):
                page.mouse.wheel(0, 1500)
                time.sleep(1.5)
            
            js_code = """
            () => {
                let items = [];
                document.querySelectorAll("a[href*='-i.']").forEach(a => {
                    let url = a.href.split('?')[0];
                    let img = a.querySelector('img');
                    let title = img ? img.getAttribute('alt') : a.innerText.replace(/\\n/g, ' ');
                    if(url && !url.includes('ads') && title) items.push({url: url, title: title.trim()});
                });
                return items;
            }
            """
            raw_products = page.evaluate(js_code)
            unique_products = []
            seen_urls = set()
            for p in raw_products:
                if p['url'] not in seen_urls:
                    seen_urls.add(p['url'])
                    unique_products.append(p)
                    
            print(f"📦 Berhasil menyerok {len(unique_products)} produk mentah.")
            product_links = filter_urls_with_gemini(unique_products, keyword, target_limit)
        except Exception as e: print(f"Error ekstrak link JS: {e}")
        finally: context.close()
    return product_links

def scrape_shopee_playwright(product_url):
    print(f"Mengakses: {product_url}")
    result_data = None 

    with Stealth().use_sync(sync_playwright()) as p:
        USER_DIR = os.path.join(os.getcwd(), "shopee_profile")
        context = p.chromium.launch_persistent_context(user_data_dir=USER_DIR, headless=False, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1920, "height": 1080})
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        extracted_data = {'api_info': None, 'shop_name_api': None, 'api_data_full': {}}

        def handle_response(response):
            if "api/v4" in response.url and response.status == 200:
                try:
                    json_data = response.json()
                    if "item/get" in response.url or "pdp/get_pc" in response.url:
                        if 'data' in json_data:
                            extracted_data['api_data_full'] = json_data['data']
                            extracted_data['api_info'] = json_data['data'].get('item', json_data['data'])
                    if "shop" in response.url:
                        if 'data' in json_data: 
                            extracted_data['shop_name_api'] = json_data['data'].get('name', json_data['data'].get('shop_name'))
                except: pass
        page.on("response", handle_response)

        try:
            page.goto(product_url, timeout=45000)
            time.sleep(4)
            
            check_and_resolve_security(page, context, product_url)
            destroy_popup(page)
            
            page.mouse.wheel(0, 800)
            time.sleep(3)
            page.mouse.wheel(0, 500)
            time.sleep(3)

            full_page_text = page.inner_text("body")
            
            match_ratings = re.search(r'([\d.,]+[KMRBJTm+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            match_sold = re.search(r'([\d.,]+[KMRBJT+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            match_nib = re.search(r'NIB:\s*([0-9*]+)', full_page_text, re.IGNORECASE)
            
            backup_ratings = match_ratings.group(1) if match_ratings else "0"
            backup_sold = match_sold.group(1).upper() if match_sold else "0" 
            nib_value = match_nib.group(1) if match_nib else "Tidak Ada NIB"
            
            if extracted_data['api_info']:
                info, full_data = extracted_data['api_info'], extracted_data['api_data_full'] 
                shop_detailed = full_data.get('shop_detailed', {}) or info.get('shop_detailed', {})
                review_data = info.get('product_review', {})
                
                parsed_variants = [{"variant_name": m.get('name', 'Default') or "Default", "price": m.get('price', 0) / 100000} for m in info.get('models', [])]
                
                result_data = {
                    "shop_name": shop_detailed.get('name', extracted_data['shop_name_api'] or 'Toko Tidak Ditemukan'), 
                    "username": shop_detailed.get('account', {}).get('username', ''),
                    "item_name": info.get('name') or info.get('title', 'Nama tidak ditemukan'),
                    "rating_star": round(info.get('item_rating', {}).get('rating_star', 0.0), 1),
                    "total_ratings": parse_shopee_metric(str(review_data.get('total_rating_count') or review_data.get('rating_count', [0])[0] or backup_ratings)),
                    "sold": parse_shopee_metric(str(review_data.get('historical_sold_display') or review_data.get('historical_sold') or info.get('historical_sold') or backup_sold)),
                    "image_url": f"https://cf.shopee.co.id/file/{info.get('image', '')}" if info.get('image', '') else "",
                    "location": info.get('shop_location', 'Lokasi tidak diketahui'),
                    "variants": parsed_variants,
                    "source_url": product_url,
                    "nib": nib_value,
                    "followers": shop_detailed.get('follower_count', 0),
                    "total_products": shop_detailed.get('item_count', 0),
                    "shop_rating": round(shop_detailed.get('rating_star', 0.0), 1)
                }
        except Exception as e: print(f"Error saat mengekstrak teks produk: {e}")
        finally: context.close()
            
    return result_data