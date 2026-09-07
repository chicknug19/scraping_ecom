import json
import os
import re
import urllib.parse
import time
import pyodbc
from playwright.sync_api import sync_playwright
from google import genai
from playwright_stealth import Stealth

# --- FUNGSI UTILITAS & DATABASE ---
def parse_shopee_metric(text_value):
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

def get_cookie_from_db():
    try:
        server = os.getenv("DB_SERVER")
        database = os.getenv("DB_NAME")
        username = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        driver = '{ODBC Driver 17 for SQL Server}'
        conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT ConfigValue FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE'")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return json.loads(row[0])
    except Exception as e:
        print(f"❌ Error DB Kuki: {e}")
    return None

def inject_cookies_to_context(context):
    cookies_db = get_cookie_from_db()
    if cookies_db:
        try:
            context.add_cookies([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain"), "path": c.get("path", "/")} for c in cookies_db])
            print("✅ Kuki sakti berhasil disuntikkan dari Azure SQL!")
        except Exception as e:
            print("❌ Gagal menyuntikkan kuki:", e)
    else:
        print("⚠️ Peringatan: Tidak ada kuki di database. Berjalan dalam mode Guest.")

# --- FUNGSI 1: MATA-MATA PROFIL TOKO KOMPETITOR ---
def scrape_shop_profile(username):
    print(f"\n🕵️ [MATA-MATA TOKO] Memeriksa profil: {username}...")
    shop_url = f"https://shopee.co.id/{username}"
    shop_data = None
    
    with Stealth().use_sync(sync_playwright()) as p:
        iphone_13 = p.devices['iPhone 13']
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(**iphone_13)
        inject_cookies_to_context(context)
        page = context.new_page()

        try:
            print("🔥 Melakukan pemanasan ke beranda Shopee...")
            page.goto("https://shopee.co.id/", timeout=60000, wait_until="domcontentloaded") 
            time.sleep(3) 
            
            print(f"🚀 Menembak URL profil toko: {shop_url}")
            page.goto(shop_url, timeout=60000, wait_until="domcontentloaded")
            
            try:
                page.locator("h1.section-seller-overview-horizontal__portrait-name").wait_for(timeout=10000)
            except:
                pass

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
    print(f"\n🔍 [FASE 1] Mencari {limit} URL untuk kata kunci: '{keyword}' (Lokasi: {location}) via Mobile Stealth...")
    
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://shopee.co.id/search?keyword={encoded_keyword}"
    
    if location:
        encoded_location = urllib.parse.quote(location)
        search_url += f"&locations={encoded_location}"
        
    product_links = []
    
    with Stealth().use_sync(sync_playwright()) as p:
        iphone_13 = p.devices['iPhone 13']
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(**iphone_13)
        inject_cookies_to_context(context)
        page = context.new_page()

        try:
            print("🔥 Melakukan pemanasan ke beranda Shopee...")
            page.goto("https://shopee.co.id/", timeout=60000, wait_until="domcontentloaded") 
            time.sleep(3) 
            
            print(f"🚀 Menembak URL pencarian: {search_url}")
            page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
            
            print(f"👀 Judul halaman saat ini: {page.title()}") 
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

# --- FUNGSI AI: FILTER PRODUK SEMANTIK ---
def filter_urls_with_gemini(raw_products, keyword, target_limit):
    if not keyword or not raw_products:
        return [p['url'] for p in raw_products][:target_limit]
    
    print(f"🧠 Meminta Gemini menyaring {len(raw_products)} produk untuk mencari makna '{keyword}'...")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        prompt = f"""Kamu adalah filter mesin pencari e-commerce. User mencari produk HP: "{keyword}".
        Pahami bahwa penjual sering menyingkat seri, contohnya "iPhone" menjadi "IP", "i-phone", dll.
        
        Tugasmu:
        1. Evaluasi daftar produk di bawah ini berdasarkan judulnya.
        2. Pilih HANYA produk unit Ponsel/HP utama yang cocok dengan seri yang dicari.
        3. TOLAK dengan tegas semua produk AKSESORIS (Casing, Case, Cover, Charger, Adaptor, Kabel, Box, Dus, Antigores, dll).
        4. TOLAK produk yang beda seri (misal mencari iPhone 12, tolak iPhone 11 atau 13).
        
        Data Produk JSON:
        {json.dumps(raw_products[:80], ensure_ascii=False)}
        
        KEMBALIKAN RESPONSE DALAM FORMAT ARRAY JSON MURNI BERISI URL YANG LOLOS FILTER.
        Contoh: ["url1", "url2"]. Jangan gunakan awalan ```json dan akhiran ```."""
        
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )
        
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        valid_urls = json.loads(clean_text)
        print(f"🎯 Gemini menemukan {len(valid_urls)} produk valid, membuang sisanya.")
        return valid_urls[:target_limit]
        
    except Exception as e:
        print(f"❌ Error Gemini Filter: {e}")
        return [p['url'] for p in raw_products][:target_limit]

# --- FUNGSI 4: MENCARI URL PRODUK BERDASARKAN TOKO KOMPETITOR ---
def get_store_product_urls(username, keyword="", limit=10, is_all=False):
    target_limit = 9999 if is_all else limit
    print(f"\n🏬 [FASE 1] Menjelajah toko '{username}' | Target: {target_limit} produk via Mobile...")
    
    shop_url = f"https://shopee.co.id/{username}?page=0&sortBy=pop"
    product_links = []
    
    with Stealth().use_sync(sync_playwright()) as p:
        iphone_13 = p.devices['iPhone 13']
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(**iphone_13)
        inject_cookies_to_context(context)
        page = context.new_page()

        try:
            print("🔥 Melakukan pemanasan ke beranda Shopee...")
            page.goto("https://shopee.co.id/", timeout=60000, wait_until="domcontentloaded") 
            time.sleep(3) 
            
            print(f"🚀 Menembak URL toko: {shop_url}")
            page.goto(shop_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4) 
            print(f"👀 Judul halaman saat ini: {page.title()}")
        except Exception as e:
            print(f"Info navigasi toko: {e}")

        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=2000): lang_btn.click(); time.sleep(1)
        except: pass

        page.mouse.click(5, 5)
        time.sleep(1)

        try:
            tab_semua = page.locator("a, div").filter(has_text=re.compile(r"^(Semua Produk|All Products)$", re.IGNORECASE)).last
            if tab_semua.is_visible(timeout=3000):
                tab_semua.click()
                time.sleep(3)
        except: pass

        print(f"Menyapu etalase {username} secara real-time...")
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
            seen_urls = set()
            for p in raw_products:
                if p['url'] not in seen_urls:
                    seen_urls.add(p['url'])
                    unique_products.append(p)
                    
            print(f"📦 Berhasil menyerok {len(unique_products)} produk mentah dari etalase layar.")
            product_links = filter_urls_with_gemini(unique_products, keyword, target_limit)
        except Exception as e:
            print(f"Error saat ekstrak link pakai JS: {e}")
        finally:
            browser.close()
            
    print(f"✅ Filter Final: {len(product_links)} link produk akan diteruskan ke Scraper Utama.")
    return product_links

# --- FUNGSI 3: MENARIK DATA PRODUK ---
def scrape_shopee_playwright(product_url):
    print(f"Mengakses via Mobile: {product_url}")
    result_data = None 

    with Stealth().use_sync(sync_playwright()) as p:
        iphone_13 = p.devices['iPhone 13']
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(**iphone_13)
        inject_cookies_to_context(context) 
        page = context.new_page()
        
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
            print("🔥 Melakukan pemanasan ke beranda Shopee...")
            page.goto("https://shopee.co.id/", timeout=60000, wait_until="domcontentloaded") 
            time.sleep(3) 
            
            print(f"🚀 Menembak URL produk: {product_url}")
            page.goto(product_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
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
                shop_location = info.get('shop_location', 'Lokasi tidak diketahui')
                
                review_data = info.get('product_review', {})
                
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

        except Exception as e:
            print(f"Error saat mengekstrak teks produk: {e}")
        finally:
            browser.close()
            
    return result_data