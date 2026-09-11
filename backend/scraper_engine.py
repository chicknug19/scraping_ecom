import json
import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import time
from ai_agent import filter_urls_with_gemini

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
def get_store_product_urls(username, keyword="", limit=10, is_all=False, custom_rules=""):
    target_limit = 9999 if is_all else limit
    print(f"\n🏬 [FASE 1] Memvalidasi dan Menjelajah toko '{username}'...")
    
    product_links = []
    seen_urls = set()
    page_number = 0 
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"]) 
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
        # TAHAP A: NORMALISASI USERNAME ORGANIK VIA UI SEARCH
        # =========================================================
        true_username = username
        search_url = f"https://shopee.co.id/search?keyword={urllib.parse.quote(username)}"
        
        try:
            print(f"🔍 Mengecek keabsahan nama toko '{username}' di mesin pencari Shopee...")
            page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Sikat pop-up bahasa jika muncul
            try:
                lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
                if lang_btn.is_visible(timeout=2000): 
                    lang_btn.click()
                    time.sleep(1)
            except: pass

            # 1. Cek Auto-Correct Shopee ("Apakah kamu mencari: ...") menggunakan Regex
            koreksi_teks = page.locator("div, span").filter(has_text=re.compile(r"Apakah kamu mencari:", re.IGNORECASE)).last
            if koreksi_teks.is_visible(timeout=3000):
                print("💡 Shopee mendeteksi typo! Mengklik saran perbaikan dari Shopee...")
                saran_link = koreksi_teks.locator("a").first
                if saran_link.is_visible():
                    saran_link.click()
                    time.sleep(4) # Tunggu hasil pencarian yang baru dimuat
            
            # 2. Tangkap username resmi dari Kartu Toko berdasarkan parameter "Pengikut"
            print("🕵️ Mencari Kartu Toko berdasarkan parameter 'Pengikut'...")
            # Kita filter tag <a> yang memiliki teks "Pengikut" di dalamnya
            store_card = page.locator("a").filter(has_text=re.compile(r"Pengikut", re.IGNORECASE)).first
            
            if store_card.is_visible(timeout=4000):
                href = store_card.get_attribute("href")
                if href:
                    # href bentuknya: /iboxofficial?entryPoint=ShopBySearch...
                    # Kita potong string-nya untuk mengambil username aslinya saja
                    raw_name = href.split('?')[0].strip('/')
                    
                    # Memastikan yang ditangkap bukan URL search halaman lain
                    if raw_name and "search" not in raw_name.lower():
                        true_username = raw_name
                        print(f"🎯 Username resmi ditemukan dari Kartu Toko UI: '{true_username}'")
            else:
                print(f"⚠️ Kartu toko khusus tidak ditemukan. Tetap menggunakan: '{true_username}'")
                
        except Exception as e:
            print(f"⚠️ Gagal melakukan validasi UI, menggunakan input awal. Info: {e}")

        # =========================================================
        # TAHAP B: MENGGUNAKAN UI SEARCH ATAU TAB SEMUA PRODUK
        # =========================================================
        base_shop_url = f"https://shopee.co.id/{true_username}"
        print(f"\n📄 Membuka beranda toko {true_username} untuk inisialisasi...")
        
        try:
            page.goto(base_shop_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
            
            # Sikat pop-up bahasa jika muncul
            try:
                lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
                if lang_btn.is_visible(timeout=2000): 
                    lang_btn.click()
                    time.sleep(1)
            except: pass

            if keyword:
                print(f"🔎 Mengetik kata kunci '{keyword}' di kolom pencarian toko...")
                # Cari input pencarian utama Shopee di header atas
                search_input = page.locator("input.shopee-searchbar-input__input").first
                search_input.fill(keyword)
                time.sleep(1)
                search_input.press("Enter")
                time.sleep(5) # Tunggu Shopee mengarahkan ke halaman hasil pencarian toko
                
                # Ambil URL hasil pencarian yang sudah digenerate otomatis oleh sistem Shopee!
                scrape_base_url = page.url
                print(f"✅ URL pencarian berhasil di-generate: {scrape_base_url}")
            else:
                print("🛒 Membuka tab 'Semua Produk'...")
                try:
                    tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
                    if tab_semua.is_visible(timeout=3000):
                        tab_semua.click()
                        time.sleep(3)
                except: pass
                scrape_base_url = f"https://shopee.co.id/{true_username}?sortBy=pop"

        except Exception as e:
            print(f"❌ Error navigasi awal toko: {e}")
            scrape_base_url = f"https://shopee.co.id/{true_username}?sortBy=pop"

        # =========================================================
        # TAHAP C: LOOPING PAGINASI (MENYAPU BARANG)
        # =========================================================
        while len(product_links) < target_limit:
            
            # Rakit URL dinamis dengan page yang aman
            separator = "&" if "?" in scrape_base_url else "?"
            current_url = f"{scrape_base_url}{separator}page={page_number}"
            
            if page_number > 0: # Halaman 1 sudah dimuat di Tahap B, tidak perlu refresh
                print(f"\n📄 Memindai etalase Halaman {page_number + 1}: {current_url}")
                try:
                    page.goto(current_url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(4) 
                    
                    # --- PERBAIKAN: Deteksi layar kosong hasil pencarian Shopee ---
                    empty_state = page.locator("div").filter(has_text=re.compile(r"Produk tidak ditemukan di toko ini", re.IGNORECASE)).first
                    if empty_state.is_visible(timeout=2000):
                        print("🛑 Pencarian habis! Shopee mengatakan tidak ada produk lagi di halaman ini.")
                        break # Langsung putus loop, berikan berapapun hasil yang sudah didapat
                    # --------------------------------------------------------------
                        
                except Exception as e:
                    print(f"Info navigasi toko: {e}")
            else:
                print(f"\n📄 Memindai etalase Halaman 1...")

            page.mouse.click(5, 5)
            time.sleep(1)

            print(f"Menggulir untuk merender produk di halaman {page_number + 1}...")
            # Kita tambah scroll sedikit agar lazy-load Shopee memuat SEMUA kartu di halaman 1
            for _ in range(12): 
                page.mouse.wheel(0, 1500)
                time.sleep(1)
                
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
                
            except Exception as e:
                print(f"Error saat ekstrak link pakai JS: {e}")
                break
            
            page_number += 1
            
        browser.close()
            
    print(f"✅ Filter Final: {len(product_links)} link produk dari toko {true_username} akan diteruskan ke Scraper Utama.")
    return product_links

# --- FUNGSI 3: MENARIK DATA PRODUK ---
def scrape_shopee_playwright(product_url):
    print(f"Mengakses: {product_url}")
    result_data = None 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
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

        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=3000):
                lang_btn.click()
                time.sleep(1)
        except: pass

        print("Menggulir halaman produk...")
        page.mouse.wheel(0, 800)
        time.sleep(3)

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

                # --- 1. EKSTRAKSI STOK CERDAS (ANTI-NYASAR) ---
                models = info.get('models', [])
                parsed_variants = []
                total_variant_stock = 0
                
                print("🕵️ Membaca varian dan kuantitas presisi dari layar...")
                
                # KUNCI 1: Kembalikan layar ke paling atas agar tidak membaca produk rekomendasi
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.5)

                for model in models:
                    v_name = model.get('name') or "Default"
                    v_has_stock = model.get('has_stock', False)
                    v_stock = 0
                    
                    if not v_has_stock:
                        v_stock = 0
                    else:
                        btn_labels = [label.strip() for label in v_name.split(',')]
                        
                        # A. Klik Varian
                        for label in btn_labels:
                            try:
                                btn = page.locator('button').filter(has_text=re.compile(f"^{re.escape(label)}$", re.IGNORECASE)).first
                                if btn.is_visible(timeout=1000):
                                    btn.click(force=True, timeout=1000)
                                    time.sleep(0.5) # Tunggu DOM Shopee merender angka
                            except Exception:
                                pass
                        
                        # B. Ekstrak Angka Menggunakan DOM JavaScript (Super Presisi)
                        js_extract_stock = """
                        () => {
                            // Trik 1: Cari elemen berlabel "Kuantitas" lalu ambil angka di sebelahnya
                            let labels = Array.from(document.querySelectorAll('div, span')).filter(e => e.innerText && e.innerText.trim().match(/^(Kuantitas|Quantity)$/i));
                            if (labels.length > 0) {
                                let parent = labels[0].parentElement.parentElement;
                                if (parent) {
                                    let match = parent.innerText.match(/Tersedia\\s*(\\d+)/i);
                                    if (match) return parseInt(match[1]);
                                }
                            }
                            
                            // Trik 2: Fallback cari elemen tunggal yang isinya persis "Tersedia xxx"
                            let allDivs = document.querySelectorAll('div');
                            for (let d of allDivs) {
                                if (d.childNodes.length === 1 && d.innerText && d.innerText.match(/^Tersedia\\s*\\d+$/i)) {
                                    let match = d.innerText.match(/Tersedia\\s*(\\d+)/i);
                                    if (match) return parseInt(match[1]);
                                }
                            }
                            return 1; // Fallback jika benar-benar tersembunyi
                        }
                        """
                        try:
                            v_stock = page.evaluate(js_extract_stock)
                        except Exception:
                            v_stock = 1

                    parsed_variants.append({
                        "variant_name": v_name,
                        "price": model.get('price', 0) / 100000,
                        "stock": v_stock
                    })
                    total_variant_stock += v_stock

                # --- 2. PERBAIKAN STOK TOTAL ---
                if len(parsed_variants) > 0:
                    stock_count = total_variant_stock
                else:
                    try:
                        raw_total_stock = info.get('stock_display') or info.get('stock_displayed') or info.get('stock')
                        stock_count = int(raw_total_stock) if raw_total_stock else 0
                    except:
                        stock_count = 0

                # --- 3. PEMBUNGKUSAN DATA AKHIR ---

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
                    "stock": total_variant_stock,   # Total stok diambil dari JSON (contoh: 8 atau 121)
                    "platform": "Shopee",
                    "variants": parsed_variants, # Varian berisi stok riil (contoh: Silver 256GB bernilai 7)
                    "source_url": product_url,
                    "nib": nib_value,
                    "followers": followers_count,
                    "total_products": total_products,
                    "shop_rating": round(shop_rating, 1)
                }

        except Exception as e:
            print(f"Error saat mengekstrak teks produk: {e}")
        finally:
            browser.close()
            
    return result_data