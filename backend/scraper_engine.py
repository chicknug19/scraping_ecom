import json
import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import time
from ai_agent import filter_urls_with_gemini
import random
import math

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
    """Menghitung titik koordinat pada kurva lengkung."""
    return (1-t)**3 * p0 + 3 * (1-t)**2 * t * p1 + 3 * (1-t) * t**2 * p2 + t**3 * p3

def human_click(page, locator):
    """Menggerakkan mouse dengan kurva lengkung sebelum menekan tombol."""
    box = locator.bounding_box()
    if box:
        # Tentukan titik target secara acak di dalam area tombol (tidak selalu di tengah)
        target_x = box['x'] + (box['width'] * random.uniform(0.3, 0.7))
        target_y = box['y'] + (box['height'] * random.uniform(0.3, 0.7))
        
        # Mulai dari posisi acak di layar
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)
        
        # Tentukan 2 titik kontrol untuk menarik garis menjadi melengkung
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.1, 0.5) + random.randint(-100, 100)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.5) + random.randint(-100, 100)
        
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.5, 0.9) + random.randint(-100, 100)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.5, 0.9) + random.randint(-100, 100)
        
        # Simulasikan gerakan frame per frame
        steps = random.randint(15, 30)
        for i in range(steps + 1):
            t = i / steps
            x = cubic_bezier(t, start_x, cp1_x, cp2_x, target_x)
            y = cubic_bezier(t, start_y, cp1_y, cp2_y, target_y)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.005, 0.015)) # Kecepatan gerak bervariasi
            
        # Jeda mikrosekon (seperti manusia memastikan kursor sudah pas) lalu klik
        time.sleep(random.uniform(0.1, 0.3))
        locator.click(force=True)
        time.sleep(random.uniform(0.2, 0.5))

def human_scroll(page, scroll_times=8):
    """Melakukan gulir halaman (scroll) dengan jarak dan jeda yang tidak tertebak."""
    for _ in range(scroll_times):
        scroll_amount = random.randint(600, 1400) # Jarak scroll acak
        page.mouse.wheel(0, scroll_amount)
        time.sleep(random.uniform(0.8, 2.2)) # Jeda baca acak


# --- FUNGSI 1: MATA-MATA PROFIL TOKO KOMPETITOR ---
def scrape_shop_profile(username):
    print(f"\n🕵️ [MATA-MATA TOKO] Memeriksa profil: {username}...")
    shop_url = f"https://shopee.co.id/{username}"
    shop_data = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
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
            time.sleep(3)

            # PERBAIKAN: Deteksi halaman Error Shopee jika username tidak ada
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
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"]) 
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
            except: pass
        elif os.path.exists("cookies.json"):
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in json.load(f)])
                print("✅ Kuki berhasil dimuat dari file lokal cookies.json!")
            except: pass
            
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            print(f"🚀 Menembak URL pencarian: {search_url}")
            page.goto(search_url, timeout=45000, wait_until="commit")
            
            time.sleep(3)
            print(f"👀 Memantau layar... URL saat ini: {page.url}")
            if "login" in page.url or "verify" in page.url:
                print("🚨 GAGAL SCRAPING: Terhadang keamanan! Cek browser yang terbuka.")
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
            browser.close()
            
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
        # Gunakan args tambahan untuk mempercepat kinerja di jaringan lambat
        browser = p.chromium.launch(
            headless=False, 
            channel="chrome", 
            args=["--disable-blink-features=AutomationControlled", "--disable-images", "--no-sandbox"]
        ) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
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

        # =========================================================
        # TAHAP A: NORMALISASI USERNAME ORGANIK VIA UI SEARCH (ANTI-LAG)
        # =========================================================
        true_username = username
        search_url = f"https://shopee.co.id/search?keyword={urllib.parse.quote(username)}"
        
        try:
            print(f"🔍 Mengecek keabsahan nama toko '{username}' di mesin pencari Shopee...")
            # PENTING: Gunakan timeout yang lebih panjang (60 detik) untuk jaringan lambat
            page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            
            # Waktu tunggu ekstra agar elemen pencarian selesai dimuat
            time.sleep(5) 
            
            # Sikat pop-up bahasa jika muncul di layar utama (Pastikan BUKAN dropdown header)
            try:
                # Mengincar teks "Bahasa Indonesia" yang ADA DI DALAM elemen pop-up/dialog
                lang_btn = page.locator("div[role='dialog']").get_by_text("Bahasa Indonesia", exact=True).first
                if lang_btn.is_visible(timeout=3000): 
                    human_click(page, lang_btn)
                    time.sleep(2)
            except: pass

            # 1. Cek Auto-Correct Shopee ("Apakah kamu mencari: ...")
            try:
                koreksi_teks = page.locator("div, span").filter(has_text=re.compile(r"Apakah kamu mencari:", re.IGNORECASE)).last
                if koreksi_teks.is_visible(timeout=5000):
                    print("💡 Shopee mendeteksi typo! Mengklik saran perbaikan dari Shopee...")
                    saran_link = koreksi_teks.locator("a").first
                    if saran_link.is_visible():
                        human_click(page, saran_link)
                        # Tunggu halaman selesai dimuat ulang (networkidle)
                        page.wait_for_load_state("networkidle", timeout=30000)
                        time.sleep(4) 
            except: pass
            
            # 2. Tangkap username resmi dari Kartu Toko (Official Store Card)
            print("🕵️ Mencari Kartu Toko resmi di hasil pencarian...")
            # Kita cari elemen profil toko (bisa menggunakan parameter "Pengikut" ATAU "Produk" untuk jaga-jaga)
            store_card = page.locator("a").filter(has_text=re.compile(r"Pengikut|Produk", re.IGNORECASE)).first
            
            if store_card.is_visible(timeout=10000): # Tunggu maksimal 10 detik untuk Kartu Toko
                href = store_card.get_attribute("href")
                if href:
                    raw_name = href.split('?')[0].strip('/')
                    # Mencegah menangkap URL yang salah
                    if raw_name and "search" not in raw_name.lower():
                        true_username = raw_name
                        print(f"🎯 Username resmi divalidasi dari UI: '{true_username}'")
            else:
                # --- PLAN B (Hardcoded Fallback) ---
                # Jika UI benar-benar gagal dimuat karena lag, gunakan daftar perbaikan manual (Kamus Mini)
                kamus_typo = {"ibox": "iboxofficial", "queenphone": "queenphonee"}
                if username.lower() in kamus_typo:
                    true_username = kamus_typo[username.lower()]
                    print(f"⚠️ UI Lagging! Menggunakan Kamus Mini: '{username}' -> '{true_username}'")
                else:
                    print(f"⚠️ Kartu toko khusus tidak ditemukan. Terpaksa menggunakan: '{true_username}'")
                
        except Exception as e:
            print(f"⚠️ Gagal melakukan validasi UI secara total. Info: {e}")
            # Fallback terakhir menggunakan Kamus Mini
            kamus_typo = {"ibox": "iboxofficial", "queenphone": "queenphonee"}
            true_username = kamus_typo.get(username.lower(), username)

        # Lanjut ke TAHAP B menggunakan true_username...

        # =========================================================
        # TAHAP B: MENGGUNAKAN UI SEARCH ATAU TAB SEMUA PRODUK (ANTI-NYASAR)
        # =========================================================
        base_shop_url = f"https://shopee.co.id/{true_username}"
        print(f"\n📄 Membuka beranda toko {true_username} untuk inisialisasi...")

        try:
            page.goto(base_shop_url, timeout=60000, wait_until="networkidle") # Gunakan networkidle agar loading benar-benar selesai
            time.sleep(4)

            # Sikat pop-up bahasa jika muncul (Lebih Tahan Lag)
            try:
                time.sleep(2) # Beri nafas ekstra agar JavaScript pop-up Shopee sempat termuat saat lag
                # Cari elemen dengan tag apapun yang teksnya persis "Bahasa Indonesia"
                lang_btn = page.get_by_text("Bahasa Indonesia", exact=True).first
                if lang_btn.is_visible(timeout=5000): # Perpanjang waktu toleransi pencarian pop-up menjadi 5 detik
                    human_click(page, lang_btn)
                    time.sleep(1.5)
            except: pass

            if keyword:
                print(f"🔎 Mengetik kata kunci '{keyword}' di dalam toko...")
                
                # Gunakan CSS selector yang SUPER SPESIFIK untuk kolom pencarian toko
                # (mencegah klik kolom pencarian global Shopee)
                shop_search_input = page.locator("div.shop-search-input input, div.shopee-shop-search-input input, input[placeholder*='toko']").first
                
                if shop_search_input.is_visible(timeout=10000):
                    shop_search_input.fill(keyword)
                    time.sleep(1)
                    shop_search_input.press("Enter")
                    
                    # Tunggu hingga halaman selesai memuat hasil pencarian (menghindari lag)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    time.sleep(5)
                else:
                    print("⚠️ Kolom pencarian toko tidak ditemukan, mencoba merakit URL pencarian manual...")
                    # Fallback URL jika input pencarian tidak ditemukan di layar
                    encoded_kw = urllib.parse.quote(keyword)
                    page.goto(f"https://shopee.co.id/{true_username}?keyword={encoded_kw}&sortBy=pop", wait_until="networkidle")
                    time.sleep(5)

                scrape_base_url = page.url
                
                # VALIDASI ANTI-NYASAR: Pastikan URL saat ini MASIH berada di dalam lingkup toko
                if "search?keyword=" in scrape_base_url and "shop=" not in scrape_base_url and true_username not in scrape_base_url:
                    print("🚨 BAHAYA: Robot terlempar ke pencarian global Shopee! Melakukan hard-reset URL...")
                    encoded_kw = urllib.parse.quote(keyword)
                    scrape_base_url = f"https://shopee.co.id/{true_username}?keyword={encoded_kw}&sortBy=pop"
                    page.goto(scrape_base_url, wait_until="domcontentloaded")
                    time.sleep(4)
                
                print(f"✅ URL pencarian terverifikasi: {scrape_base_url}")
                
            else:
                print("🛒 Membuka tab 'Semua Produk'...")
                try:
                    tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
                    if tab_semua.is_visible(timeout=5000):
                        human_click(page, tab_semua)
                        page.wait_for_load_state("networkidle")
                except: pass
                scrape_base_url = f"https://shopee.co.id/{true_username}?sortBy=pop"

        except Exception as e:
            print(f"❌ Error navigasi awal toko (Lag Network): {e}")
            # Jika semua gagal karena lag, paksa rakit URL secara manual
            encoded_kw = urllib.parse.quote(keyword) if keyword else ""
            param = f"?keyword={encoded_kw}&sortBy=pop" if keyword else "?sortBy=pop"
            scrape_base_url = f"https://shopee.co.id/{true_username}{param}"

        # =========================================================
        # TAHAP C: LOOPING PAGINASI BERBASIS UI (KLIK TOMBOL NEXT)
        # =========================================================
        while len(product_links) < target_limit:
            
            print(f"\n📄 Memindai etalase Halaman {page_number + 1}...")

            page.mouse.click(5, 5)
            time.sleep(1)

            print(f"Menggulir untuk merender produk di halaman {page_number + 1}...")
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
                    print("🛑 Tidak ada elemen produk yang bisa di-scrape di layar.")
                    break
                        
                print(f"📦 Menyerok {len(unique_products)} produk mentah dari layar.")
                
                filtered_urls = filter_urls_with_gemini(unique_products, keyword, target_limit - len(product_links), custom_rules)
                product_links.extend(filtered_urls)
                
                print(f"📊 Progres Sementara: Terkumpul {len(product_links)} / {target_limit} produk target.")
                
                # JIKA TARGET BELUM TERCAPAI, CARI DAN KLIK TOMBOL "NEXT PAGE"
                if len(product_links) < target_limit:
                    try:
                        # Mencari tombol panah kanan (Next) di sistem paginasi Shopee Mall
                        next_btn = page.locator("button.shopee-icon-button--right").first
                        
                        if next_btn.is_visible(timeout=3000) and not next_btn.is_disabled():
                            print("➡️ Menuju ke halaman selanjutnya...")
                            human_click(page, next_btn)
                            page.wait_for_load_state("networkidle", timeout=20000)
                            time.sleep(3)
                            page_number += 1
                        else:
                            print("🛑 Tombol Next tidak tersedia atau ini adalah halaman terakhir. Pencarian selesai.")
                            break
                    except Exception as e:
                        print(f"⚠️ Gagal pindah halaman via UI: {e}")
                        break
                else:
                    break # Keluar loop jika target sudah terpenuhi
                
            except Exception as e:
                print(f"Error saat ekstrak link pakai JS: {e}")
                break
            
        browser.close()
            
    print(f"✅ Filter Final: {len(product_links)} link produk dari toko {true_username} akan diteruskan ke Scraper Utama.")
    return product_links

# --- FUNGSI 3: MENARIK DATA PRODUK (VERSI CEPAT TANPA CEK STOK) ---
def scrape_shopee_playwright(product_url):
    print(f"Mengakses: {product_url}")
    result_data = None 

    with sync_playwright() as p:
        # Konfigurasi browser standar (Nanti akan kita ubah ke Persistent Context)
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # (Logika muat kuki cookies_env / cookies.json masih dipertahankan sementara di sini)
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
        except: pass 

        # --- SIKAT POP-UP BAHASA ---
        try:
            time.sleep(2)
            lang_btn = page.locator("div[role='dialog']").get_by_text("Bahasa Indonesia", exact=True).first
            if lang_btn.is_visible(timeout=5000):
                human_click(page, lang_btn)
                time.sleep(1.5)
        except: pass

        # Gulir sedikit untuk simulasi manusia dan memicu API memuat ulasan
        human_scroll(page, scroll_times=4)

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
                rating_star = info.get('item_rating', {}).get('rating_star', 0.0)
                
                shop_detailed = full_data.get('shop_detailed', {}) or info.get('shop_detailed', {})
                shop_location_api = info.get('shop_location') or shop_detailed.get('shop_location') or 'Tidak Diketahui'
                
                review_data = info.get('product_review', {})
                
                total_ratings_raw = str(review_data.get('total_rating_count') or review_data.get('rating_count', [0])[0] or backup_ratings)
                sold_raw = str(review_data.get('historical_sold_display') or review_data.get('historical_sold') or info.get('historical_sold') or backup_sold)
                    
                shop_name = shop_detailed.get('name', extracted_data['shop_name_api'] or 'Toko Tidak Ditemukan')
                shop_username = shop_detailed.get('account', {}).get('username', '')
                followers_count = shop_detailed.get('follower_count', 0)
                total_products = shop_detailed.get('item_count', 0)
                shop_rating = shop_detailed.get('rating_star', 0.0)

                image_hash = info.get('image', '')
                image_url = f"https://cf.shopee.co.id/file/{image_hash}" if image_hash else ""

                # --- EKSTRAKSI VARIAN CEPAT DARI JSON (TANPA CEK STOK) ---
                models = info.get('models', [])
                parsed_variants = []

                for model in models:
                    v_name = model.get('name') or "Default"
                    parsed_variants.append({
                        "variant_name": v_name,
                        "price": model.get('price', 0) / 100000,
                        "stock": 0  # Stok dipukul rata 0 agar cepat dan tidak ribet
                    })

                # --- PEMBUNGKUSAN DATA AKHIR ---
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
                    "stock": 0, # Stok utama dipukul rata 0
                    "platform": "Shopee",
                    "variants": parsed_variants,
                    "source_url": product_url,
                    "nib": nib_value,
                    "followers": followers_count,
                    "total_products": total_products,
                    "shop_rating": round(shop_rating, 1)
                }

        except Exception as e:
            print(f"Error saat mengekstrak data produk: {e}")
        finally:
            browser.close()
            
    return result_data