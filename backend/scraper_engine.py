import json
import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import time
from ai_agent import filter_urls_with_gemini
import random
import math

# IMPORT BARU: OpenCV untuk Computer Vision & Numpy
import cv2
import numpy as np

# IMPORT BARU: Mengambil fungsi pengirim email
from email_notifier import send_captcha_alert

# LOKASI FOLDER PROFIL PERMANEN CHROME
PROFILE_DIR = os.path.join(os.getcwd(), "ShopeeBotProfile")

# --- FUNGSI UTILITAS ---
def parse_shopee_metric(text_value):
    if not text_value: return 0
    text_clean = text_value.lower().strip().replace(',', '.')
    match = re.search(r'([\d.]+)\s*([a-z]*)', text_clean)
    if match:
        number = float(match.group(1))
        suffix = match.group(2)
        if suffix in ['m', 'jt', 'juta']: return int(number * 1000000)
        elif suffix in ['k', 'rb', 'ribu']: return int(number * 1000)
        return int(number)
    return 0


# --- FUNGSI ANTI-BOT: ALGORITMA KURVA BEZIER ---
def cubic_bezier(t, p0, p1, p2, p3):
    return (1-t)**3 * p0 + 3 * (1-t)**2 * t * p1 + 3 * (1-t) * t**2 * p2 + t**3 * p3

def human_click(page, locator):
    box = locator.bounding_box()
    if box:
        target_x = box['x'] + (box['width'] * random.uniform(0.3, 0.7))
        target_y = box['y'] + (box['height'] * random.uniform(0.3, 0.7))
        
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)
        
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.1, 0.5) + random.randint(-100, 100)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.5) + random.randint(-100, 100)
        
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.5, 0.9) + random.randint(-100, 100)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.5, 0.9) + random.randint(-100, 100)
        
        steps = random.randint(15, 30)
        for i in range(steps + 1):
            t = i / steps
            x = cubic_bezier(t, start_x, cp1_x, cp2_x, target_x)
            y = cubic_bezier(t, start_y, cp1_y, cp2_y, target_y)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.005, 0.015))
            
        time.sleep(random.uniform(0.1, 0.3))
        locator.click(force=True)
        time.sleep(random.uniform(0.2, 0.5))

def human_scroll(page, scroll_times=8):
    for _ in range(scroll_times):
        scroll_amount = random.randint(600, 1400)
        page.mouse.wheel(0, scroll_amount)
        time.sleep(random.uniform(0.8, 2.2))


# --- FUNGSI ANTI-BOT: DRAG AND DROP (GESER PUZZLE) ---
def human_drag(page, start_x, start_y, distance_x):
    """Menahan dan menggeser slider puzzle secara natural menyerupai tangan manusia."""
    page.mouse.move(start_x, start_y)
    time.sleep(random.uniform(0.1, 0.3))
    page.mouse.down() # Tahan klik kiri
    time.sleep(random.uniform(0.1, 0.4))
    
    target_x = start_x + distance_x
    target_y = start_y + random.uniform(-3, 3) # Sedikit goyang di sumbu Y
    
    # Gerakan menggeser perlahan dengan perlambatan di akhir (Ease-out)
    steps = random.randint(25, 45)
    for i in range(1, steps + 1):
        t = i / steps
        ease_t = 1 - pow(1 - t, 3) # Rumus ease-out cubic
        current_x = start_x + (target_x - start_x) * ease_t
        current_y = start_y + random.uniform(-1.5, 1.5)
        
        page.mouse.move(current_x, current_y)
        time.sleep(random.uniform(0.01, 0.04))
        
    time.sleep(random.uniform(0.3, 0.7))
    page.mouse.up() # Lepas klik
    print("🧩 Puzzle dilepaskan!")
    time.sleep(3) # Tunggu loading verifikasi Shopee


# --- FUNGSI PENYELESAI CAPTCHA (OPENCV) ---
def solve_captcha_slider(page):
    """Mendeteksi gambar puzzle, menghitung jarak dengan CV2, dan menggeser slider."""
    print("🤖 Menjalankan Computer Vision untuk memecahkan Captcha...")
    try:
        # Cari iframe Datadome/Shopee Captcha
        iframe_element = page.locator('iframe[src*="captcha"], iframe[src*="verify"]').first
        
        if iframe_element.is_visible(timeout=5000):
            frame = iframe_element.content_frame
        else:
            frame = page

        # Ambil elemen Background dan Potongan Puzzle
        bg_img = frame.locator('img[alt*="background"], .background-img, .captcha-bg, .captcha-image').first
        piece_img = frame.locator('img[alt*="puzzle"], .piece-img, .jigsaw, .captcha-jigsaw-piece').first
        slider_btn = frame.locator('.slider, .sec-slider, .slider-button, .captcha-slider-btn').first
        
        if not bg_img.is_visible(timeout=5000) or not slider_btn.is_visible():
            print("⚠️ Elemen gambar puzzle atau slider tidak ditemukan di layar.")
            return False

        print("📸 Mengambil screenshot puzzle...")
        bg_img.screenshot(path="captcha_bg.png")
        piece_img.screenshot(path="captcha_piece.png")
        
        # Proses Gambar dengan OpenCV
        bg = cv2.imread("captcha_bg.png", cv2.IMREAD_GRAYSCALE)
        piece = cv2.imread("captcha_piece.png", cv2.IMREAD_GRAYSCALE)
        
        # Canny Edge Detection (Deteksi Garis Tepi)
        bg_edges = cv2.Canny(bg, 100, 200)
        piece_edges = cv2.Canny(piece, 100, 200)
        
        # Template Matching untuk mencari lokasi lubang
        res = cv2.matchTemplate(bg_edges, piece_edges, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        distance = max_loc[0] 
        print(f"🎯 Computer Vision mendeteksi lubang di jarak: {distance} px")
        
        # Kalibrasi jarak layar vs resolusi gambar asli
        bg_box = bg_img.bounding_box()
        slider_box = slider_btn.bounding_box()
        
        scale_ratio = bg_box['width'] / bg.shape[1] 
        actual_distance = distance * scale_ratio
        
        # Lakukan penggeseran (Drag and Drop)
        start_x = slider_box['x'] + (slider_box['width'] / 2)
        start_y = slider_box['y'] + (slider_box['height'] / 2)
        
        human_drag(page, start_x, start_y, actual_distance)
        
        # Bersihkan file sampah
        if os.path.exists("captcha_bg.png"): os.remove("captcha_bg.png")
        if os.path.exists("captcha_piece.png"): os.remove("captcha_piece.png")
        
        return True

    except Exception as e:
        print(f"❌ CV2 Captcha Solver gagal: {e}")
        return False


# --- FUNGSI CEK BLOKIR (REUSABLE & AUTONOMOUS) ---
def check_for_block(page, toko_target, produk_ke):
    """Mengecek apakah layar memutih atau dialihkan ke halaman captcha, lalu mencoba melawannya!"""
    try:
        if "verify" in page.url or "captcha" in page.url:
            print("🚨 SOFT BLOCK TERDETEKSI! Halaman verifikasi muncul.")
            
            # Coba kerjakan secara otomatis pakai AI Computer Vision
            sukses = solve_captcha_slider(page)
            
            if sukses:
                time.sleep(3)
                if "verify" not in page.url and "captcha" not in page.url:
                    print("✅ Captcha berhasil dipecahkan oleh Computer Vision! Melanjutkan tugas...")
                    return False # Tidak jadi blokir, jalan terus!
            
            print("❌ CV2 Gagal memecahkan puzzle. Mengirim alarm email...")
            send_captcha_alert(toko_target=toko_target, url_terakhir=page.url, produk_ke=produk_ke)
            return True
            
        elif page.get_by_text("Informasi gagal diterima", exact=False).is_visible(timeout=2000) or "login" in page.url:
            print("🚨 HARD BLOCK / HALAMAN RUSAK / LOGIN DIMINTA!")
            send_captcha_alert(toko_target=toko_target, url_terakhir=page.url, produk_ke=produk_ke)
            return True
            
    except: pass
    return False


# --- FUNGSI 1: MATA-MATA PROFIL TOKO KOMPETITOR ---
def scrape_shop_profile(username):
    print(f"\n🕵️ [MATA-MATA TOKO] Memeriksa profil: {username}...")
    shop_url = f"https://shopee.co.id/{username}"
    shop_data = None
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, 
            channel="chrome", 
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto(shop_url, timeout=45000, wait_until="commit")
            time.sleep(3)

            if check_for_block(page, username, "Cek Profil Toko"):
                context.close()
                return {"error": "Terblokir Captcha"}

            if page.get_by_text("Informasi gagal diterima", exact=False).is_visible():
                print(f"❌ ERROR: Halaman toko '{username}' rusak atau username tidak terdaftar!")
                return {"error": f"Toko '{username}' tidak ditemukan. Pastikan username benar."}
            
            try:
                page.locator("h1.section-seller-overview-horizontal__portrait-name").wait_for(timeout=10000)
            except:
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
            context.close()
            
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
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, 
            channel="chrome", 
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            print(f"🚀 Menembak URL pencarian: {search_url}")
            page.goto(search_url, timeout=45000, wait_until="commit")
            time.sleep(3)
            
            if check_for_block(page, f"Pencarian: {keyword}", "Halaman Pencarian"):
                context.close()
                return []
                
        except Exception as e:
            print(f"Info navigasi search: {e}")

        print("Menunggu elemen produk dimuat di halaman pencarian...")
        try:
            page.locator("a[href*='-i.']").first.wait_for(timeout=15000)
        except:
            time.sleep(5)

        scroll_attempts = (limit // 10) + 3 
        print(f"Menggulir halaman {scroll_attempts} kali untuk memuat {limit} produk...")
        human_scroll(page, scroll_times=12)
        
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
            context.close()
            
    print(f"✅ Ditemukan {len(product_links)} link target.")
    return product_links


# --- FUNGSI 4: MENCARI URL PRODUK BERDASARKAN TOKO KOMPETITOR ---
def get_store_product_urls(username, keyword="", limit=10, is_all=False, custom_rules=""):
    target_limit = 9999 if is_all else limit
    print(f"\n🏬 [FASE 1] Memvalidasi dan Menjelajah toko '{username}'...")
    
    product_links = []
    seen_urls = set()
    page_number = 0 
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, 
            channel="chrome", 
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        true_username = username
        search_url = f"https://shopee.co.id/search?keyword={urllib.parse.quote(username)}"
        
        try:
            print(f"🔍 Mengecek keabsahan nama toko '{username}' di mesin pencari Shopee...")
            page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5) 
            
            if check_for_block(page, username, "Validasi URL Toko"):
                context.close()
                return []
            
            try:
                lang_btn = page.locator("div[role='dialog']").get_by_text("Bahasa Indonesia", exact=True).first
                if lang_btn.is_visible(timeout=3000): 
                    human_click(page, lang_btn)
                    time.sleep(2)
            except: pass

            try:
                koreksi_teks = page.locator("div, span").filter(has_text=re.compile(r"Apakah kamu mencari:", re.IGNORECASE)).last
                if koreksi_teks.is_visible(timeout=5000):
                    saran_link = koreksi_teks.locator("a").first
                    if saran_link.is_visible():
                        human_click(page, saran_link)
                        page.wait_for_load_state("networkidle", timeout=30000)
                        time.sleep(4) 
            except: pass
            
            store_card = page.locator("a").filter(has_text=re.compile(r"Pengikut|Produk", re.IGNORECASE)).first
            if store_card.is_visible(timeout=10000):
                href = store_card.get_attribute("href")
                if href:
                    raw_name = href.split('?')[0].strip('/')
                    if raw_name and "search" not in raw_name.lower():
                        true_username = raw_name
                        print(f"🎯 Username resmi divalidasi dari UI: '{true_username}'")
            else:
                kamus_typo = {"ibox": "iboxofficial", "queenphone": "queenphonee"}
                if username.lower() in kamus_typo:
                    true_username = kamus_typo[username.lower()]
                
        except Exception as e:
            kamus_typo = {"ibox": "iboxofficial", "queenphone": "queenphonee"}
            true_username = kamus_typo.get(username.lower(), username)

        base_shop_url = f"https://shopee.co.id/{true_username}"
        print(f"\n📄 Membuka beranda toko {true_username} untuk inisialisasi...")

        try:
            page.goto(base_shop_url, timeout=60000, wait_until="networkidle")
            time.sleep(4)

            if check_for_block(page, true_username, "Beranda Toko"):
                context.close()
                return []

            try:
                time.sleep(2) 
                lang_btn = page.locator("div[role='dialog']").get_by_text("Bahasa Indonesia", exact=True).first
                if lang_btn.is_visible(timeout=5000):
                    human_click(page, lang_btn)
                    time.sleep(1.5)
            except: pass

            if keyword:
                print(f"🔎 Mengetik kata kunci '{keyword}' di dalam toko...")
                shop_search_input = page.locator("div.shop-search-input input, div.shopee-shop-search-input input, input[placeholder*='toko']").first
                
                if shop_search_input.is_visible(timeout=10000):
                    shop_search_input.fill(keyword)
                    time.sleep(1)
                    shop_search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=30000)
                    time.sleep(5)
                else:
                    encoded_kw = urllib.parse.quote(keyword)
                    page.goto(f"https://shopee.co.id/{true_username}?keyword={encoded_kw}&sortBy=pop", wait_until="networkidle")
                    time.sleep(5)

                scrape_base_url = page.url
                
                if "search?keyword=" in scrape_base_url and "shop=" not in scrape_base_url and true_username not in scrape_base_url:
                    encoded_kw = urllib.parse.quote(keyword)
                    scrape_base_url = f"https://shopee.co.id/{true_username}?keyword={encoded_kw}&sortBy=pop"
                    page.goto(scrape_base_url, wait_until="domcontentloaded")
                    time.sleep(4)
                
            else:
                try:
                    tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
                    if tab_semua.is_visible(timeout=5000):
                        human_click(page, tab_semua)
                        page.wait_for_load_state("networkidle")
                except: pass
                scrape_base_url = f"https://shopee.co.id/{true_username}?sortBy=pop"

        except Exception as e:
            encoded_kw = urllib.parse.quote(keyword) if keyword else ""
            param = f"?keyword={encoded_kw}&sortBy=pop" if keyword else "?sortBy=pop"
            scrape_base_url = f"https://shopee.co.id/{true_username}{param}"

        while len(product_links) < target_limit:
            
            print(f"\n📄 Memindai etalase Halaman {page_number + 1}...")
            page.mouse.click(5, 5)
            time.sleep(1)

            if check_for_block(page, true_username, f"Etalase Halaman {page_number + 1}"):
                context.close()
                return product_links

            human_scroll(page, scroll_times=12)

            js_code = """
            () => {
                let items = [];
                document.querySelectorAll("a[href*='-i.']").forEach(a => {
                    let url = a.href.split('?')[0];
                    let img = a.querySelector('img');
                    let title = img ? img.getAttribute('alt') : a.innerText.replace(/\\n/g, ' ');
                    if(url && !url.includes('ads') && title) {
                        items.push({url: url, title: title.trim()});
                    }
                });
                return items;
            }
            """
            try:
                raw_products = page.evaluate(js_code)
                unique_products = []
                for p in raw_products:
                    if p['url'] not in seen_urls:
                        seen_urls.add(p['url'])
                        unique_products.append(p)
                
                if len(unique_products) == 0:
                    break
                        
                filtered_urls = filter_urls_with_gemini(unique_products, keyword, target_limit - len(product_links), custom_rules)
                product_links.extend(filtered_urls)
                
                if len(product_links) < target_limit:
                    try:
                        next_btn = page.locator("button.shopee-icon-button--right").first
                        if next_btn.is_visible(timeout=3000) and not next_btn.is_disabled():
                            human_click(page, next_btn)
                            page.wait_for_load_state("networkidle", timeout=20000)
                            time.sleep(3)
                            page_number += 1
                        else:
                            break
                    except: break
                else:
                    break
                
            except Exception as e:
                break
            
        context.close()
            
    print(f"✅ Filter Final: {len(product_links)} link produk dari toko {true_username} akan diteruskan ke Scraper Utama.")
    return product_links

# --- FUNGSI 3: MENARIK DATA PRODUK (VERSI CEPAT TANPA CEK STOK) ---
def scrape_shopee_playwright(product_url):
    print(f"\nMengakses: {product_url}")
    result_data = None 

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, 
            channel="chrome", 
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
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
                    except: pass

        page.on("response", handle_response)

        try:
            page.goto(product_url, timeout=45000)
            
            if check_for_block(page, "Ekstraksi Produk", product_url):
                context.close()
                return {"status": "BLOCKED"} 
                
        except: pass 

        try:
            time.sleep(2)
            lang_btn = page.locator("div[role='dialog']").get_by_text("Bahasa Indonesia", exact=True).first
            if lang_btn.is_visible(timeout=5000):
                human_click(page, lang_btn)
                time.sleep(1.5)
        except: pass

        human_scroll(page, scroll_times=4)
        
        if check_for_block(page, "Ekstraksi Produk (Post-Scroll)", product_url):
            context.close()
            return {"status": "BLOCKED"} 

        try:
            full_page_text = page.inner_text("body")
            
            match_ratings = re.search(r'([\d.,]+[KMRBJTm+]*)\s*\n?\s*(?:Ratings|Penilaian)', full_page_text, re.IGNORECASE)
            backup_ratings = match_ratings.group(1) if match_ratings else "0"

            match_sold = re.search(r'([\d.,]+[KMRBJT+]*)\s*\n?\s*(?:Sold|Terjual)', full_page_text, re.IGNORECASE)
            backup_sold = match_sold.group(1).upper() if match_sold else "0" 
            
            match_nib = re.search(r'NIB:\s*([0-9*]+)', full_page_text, re.IGNORECASE)
            nib_value = match_nib.group(1) if match_nib else "Tidak Ada NIB"
            
            if extracted_data['api_info']:
                info = extracted_data['api_info']
                full_data = extracted_data['api_data_full'] 
                    
                item_name = info.get('name') or info.get('title', 'Nama tidak ditemukan')
                
                # --- PERBAIKAN LOGIKA NULL/NONE ---
                item_rating_obj = info.get('item_rating') or {}
                rating_star = item_rating_obj.get('rating_star')
                rating_star = float(rating_star) if rating_star is not None else 0.0
                
                shop_detailed = full_data.get('shop_detailed') or info.get('shop_detailed') or {}
                shop_location_api = info.get('shop_location') or shop_detailed.get('shop_location') or 'Tidak Diketahui'
                
                review_data = info.get('product_review') or {}
                
                # Pencegahan error jika rating_count mengembalikan list kosong
                rating_count_arr = review_data.get('rating_count')
                rating_count_val = rating_count_arr[0] if isinstance(rating_count_arr, list) and len(rating_count_arr) > 0 else 0
                
                total_ratings_raw = str(review_data.get('total_rating_count') or rating_count_val or backup_ratings)
                sold_raw = str(review_data.get('historical_sold_display') or review_data.get('historical_sold') or info.get('historical_sold') or backup_sold)
                    
                shop_name = shop_detailed.get('name') or extracted_data['shop_name_api'] or 'Toko Tidak Ditemukan'
                
                account_obj = shop_detailed.get('account') or {}
                shop_username = account_obj.get('username') or ''
                
                followers_count = shop_detailed.get('follower_count') or 0
                total_products = shop_detailed.get('item_count') or 0
                
                shop_rating = shop_detailed.get('rating_star')
                shop_rating = float(shop_rating) if shop_rating is not None else 0.0
                # -----------------------------------

                image_hash = info.get('image', '')
                image_url = f"https://cf.shopee.co.id/file/{image_hash}" if image_hash else ""

                models = info.get('models') or []
                parsed_variants = []

                for model in models:
                    v_name = model.get('name') or "Default"
                    v_price = model.get('price')
                    v_price = (v_price / 100000) if v_price is not None else 0
                    
                    parsed_variants.append({
                        "variant_name": v_name,
                        "price": v_price,
                        "stock": 0 
                    })

                result_data = {
                    "shop_name": shop_name, 
                    "username": shop_username,
                    "item_name": item_name,
                    "rating_star": round(rating_star, 1),
                    "total_ratings": parse_shopee_metric(total_ratings_raw),
                    "sold": parse_shopee_metric(sold_raw),
                    "image_url": image_url,
                    "location": shop_location_api,
                    "shop_location_fallback": shop_location_api,
                    "stock": 0, 
                    "platform": "Shopee",
                    "variants": parsed_variants,
                    "source_url": product_url,
                    "nib": nib_value,
                    "followers": followers_count,
                    "total_products": total_products,
                    "shop_rating": round(shop_rating, 1)
                }

        except Exception as e:
            print(f"❌ Error saat mengekstrak data produk: {e}")
        finally:
            context.close()
            
    return result_data