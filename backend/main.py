from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyodbc
import os
import time
from dotenv import load_dotenv
from typing import Optional
from google import genai
from google.genai import types

from ai_agent import filter_urls_with_gemini, parse_scraping_intent 
from scraper_engine import get_competitor_urls, scrape_shopee_playwright, get_store_product_urls

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FUNGSI 1: ALAT (TOOL) UNTUK GEMINI ---
def get_competitor_data_from_db(keyword: str, limit: int = 20):
    try:
        server = os.getenv("DB_SERVER")
        database = os.getenv("DB_NAME")
        username = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        driver = '{ODBC Driver 17 for SQL Server}'
        conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        query = """
            SELECT TOP (?) 
                i.ItemName, i.ShopName, i.Location, i.TotalSold, i.Stock, i.Platform, v.VariantName, v.Price
            FROM Items i
            LEFT JOIN ItemVariants v ON i.ItemCode = v.ItemCode
            WHERE i.ItemName LIKE ?
            ORDER BY i.ScrapedAt DESC
        """
        cursor.execute(query, limit, f"%{keyword}%")
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "Toko": row.ShopName,
                "Platform": row.Platform,
                "Lokasi": row.Location,
                "Produk": row.ItemName,
                "Varian": row.VariantName,
                "Harga": float(row.Price) if row.Price else 0,
                "Terjual": row.TotalSold,
                "Stok": row.Stock
            })
        
        return results if results else [{"message": f"Tidak ada data ditemukan untuk keyword: {keyword}"}]
    except Exception as e:
        return [{"error": str(e)}]

# --- MODEL REQUEST FRONTEND ---
class ChatRequest(BaseModel):
    user_prompt: str

class ScrapeRequest(BaseModel):
    keyword: str
    limit: int = 10
    location: Optional[str] = ""

class StoreTask(BaseModel):
    username: str
    keyword: str = ""
    limit: int = 10
    isAll: bool = False

class StoreScrapeRequest(BaseModel):
    tasks: list[StoreTask]

class SmartScrapeRequest(BaseModel):
    prompt: str

# --- ENDPOINT 1: CHAT AI DENGAN FUNCTION CALLING ---
@app.post("/api/analyze")
def chat_with_ai(req: ChatRequest):
    print(f"Menerima prompt dari frontend: {req.user_prompt[:50]}...")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        chat = client.chats.create(
            model="gemini-3.5-flash",
            config=types.GenerateContentConfig(
                tools=[get_competitor_data_from_db],
            )
        )
        response = chat.send_message(req.user_prompt)
        return {"message": "Sukses", "ai_response": response.text}
    except Exception as e:
        print(f"Error AI Analysis: {e}")
        return {"error": str(e)}

# --- FUNGSI PENYIMPANAN DATABASE ---
def save_to_database(data):
    try:
        server = os.getenv("DB_SERVER")
        database = os.getenv("DB_NAME")
        username = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        driver = '{ODBC Driver 17 for SQL Server}'

        conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        platform_data = data.get('platform', 'Shopee')
        stock_data = data.get('stock', 0)
        
        location_data = data.get('location')
        if not location_data or location_data.strip() == "":
            location_data = data.get('shop_location_fallback', 'Tidak Diketahui')

        nib_data = data.get('nib', 'Tidak Ada NIB')
        followers_data = data.get('followers', 0)
        products_data = data.get('total_products', 0)
        shop_rating_data = data.get('shop_rating', 0.0)
        username_data = data.get('username') or data['shop_name'].replace(" ", "").lower()[:50]

        cursor.execute("SELECT StoreID FROM Stores WHERE ShopName = ? AND Platform = ?", data['shop_name'], platform_data)
        store_row = cursor.fetchone()

        if store_row:
            store_id = store_row[0]
            cursor.execute("""
                UPDATE Stores 
                SET FollowersCount = ?, TotalProducts = ?, Rating = ?, LastUpdated = DATEADD(hour, 7, GETUTCDATE()),
                    NIB = CASE WHEN NIB = 'Tidak Ada NIB' OR NIB IS NULL THEN ? ELSE NIB END
                WHERE StoreID = ?
            """, followers_data, products_data, shop_rating_data, nib_data, store_id)
        else:
            cursor.execute("""
                INSERT INTO Stores (Username, ShopName, NIB, FollowersCount, TotalProducts, Rating, Platform, LastUpdated) 
                OUTPUT INSERTED.StoreID 
                VALUES (?, ?, ?, ?, ?, ?, ?, DATEADD(hour, 7, GETUTCDATE()))
            """, username_data, data['shop_name'], nib_data, followers_data, products_data, shop_rating_data, platform_data)
            store_id = cursor.fetchone()[0]

        cursor.execute("SELECT ItemCode FROM Items WHERE ItemName = ? AND StoreID = ?", data['item_name'], store_id)
        item_row = cursor.fetchone()

        if item_row:
            generated_item_code = item_row[0]
            cursor.execute("""
                UPDATE Items 
                SET TotalRatings = ?, TotalSold = ?, RatingStar = ?, ImageURL = ?, Location = ?, ShopName = ?, Stock = ?, Platform = ?, ScrapedAt = DATEADD(hour, 7, GETUTCDATE())
                WHERE ItemCode = ?
            """, data['total_ratings'], data['sold'], data['rating_star'], data['image_url'], location_data, data['shop_name'], stock_data, platform_data, generated_item_code)
            
            cursor.execute("DELETE FROM ItemVariants WHERE ItemCode = ?", generated_item_code)
        else:
            cursor.execute("""
                INSERT INTO Items (ItemName, StoreID, ShopName, Location, RatingStar, TotalRatings, TotalSold, ImageURL, SourceURL, Stock, Platform, ScrapedAt)
                OUTPUT INSERTED.ItemCode
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATEADD(hour, 7, GETUTCDATE()))
            """, data['item_name'], store_id, data['shop_name'], location_data, data['rating_star'], data['total_ratings'], data['sold'], data['image_url'], data['source_url'], stock_data, platform_data)
            generated_item_code = cursor.fetchone()[0]

        if generated_item_code and data.get('variants'):
            query_variant = """
                INSERT INTO ItemVariants (ItemCode, VariantName, Price, Stock)
                VALUES (?, ?, ?, ?)
            """
            for varian in data['variants']:
                cursor.execute(query_variant, generated_item_code, varian['variant_name'], varian['price'], varian.get('stock', 0))

        conn.commit()
        conn.close()
        print(f"✅ [DB] Sukses upsert item ID {generated_item_code} untuk Toko {store_id}")
    except Exception as e:
        print(f"❌ Error DB: {e}")

# --- ENDPOINT 2: SCRAPE PENCARIAN UMUM ---
@app.post("/api/scrape")
def run_scraper(req: ScrapeRequest):
    print(f"Menerima request dari frontend: {req.keyword} (Limit: {req.limit}, Lokasi: {req.location})")
    daftar_url = get_competitor_urls(keyword=req.keyword, limit=req.limit, location=req.location)
    semua_data = []

    for target_url in daftar_url:
        data_produk = scrape_shopee_playwright(target_url)
        
        # --- REM DARURAT ---
        if data_produk and data_produk.get("status") == "BLOCKED":
            print("🛑 ALERT: Terhenti paksa karena CAPTCHA/Hard Block.")
            break
            
        if data_produk:
            semua_data.append(data_produk)
            save_to_database(data_produk)
        time.sleep(2)

    return {"message": "Selesai", "results": semua_data}

# --- ENDPOINT 3: SCRAPE TOKO (MANUAL MODE) ---
@app.post("/api/scrape-stores")
def run_store_scraper(req: StoreScrapeRequest):
    print(f"\n🚀 Memulai Multi-Task Store Scraper. Total Tugas: {len(req.tasks)}")
    semua_data = []
    is_blocked_global = False

    for task in req.tasks:
        if is_blocked_global: break # Keluar dari tugas toko lain jika kena blok
        
        clean_username = task.username.replace(" ", "").lower() 
        print(f"Mengeksekusi toko: '{clean_username}'")
        
        daftar_url = get_store_product_urls(
            username=clean_username, 
            keyword=task.keyword, 
            limit=task.limit, 
            is_all=task.isAll
        )
        
        for target_url in daftar_url:
            data_produk = scrape_shopee_playwright(target_url)
            
            # --- REM DARURAT ---
            if data_produk and data_produk.get("status") == "BLOCKED":
                print("🛑 ALERT: Terhenti paksa karena CAPTCHA/Hard Block.")
                is_blocked_global = True
                break
                
            if data_produk:
                semua_data.append(data_produk)
                save_to_database(data_produk)
            time.sleep(2)

    return {"message": f"Selesai memproses.", "results": semua_data}

# --- ENDPOINT 4: SCRAPE TOKO (AI SMART MODE) ---
@app.post("/api/scrape-smart")
def run_smart_store_scraper(req: SmartScrapeRequest):
    print(f"\n🧠 Memulai Smart Scraper dengan prompt: '{req.prompt}'")
    
    intent_data = parse_scraping_intent(req.prompt)
    if not intent_data.get("is_valid"):
        return {"message": intent_data.get("message", "Perintah tidak lengkap.")}
        
    semua_data = []
    username = intent_data.get("username", "").replace(" ", "").lower()
    keyword = intent_data.get("keyword", "")
    limit = intent_data.get("limit") or 10
    is_all = intent_data.get("isAll", False)
    custom_rules = intent_data.get("custom_rules", "")
    
    print(f"🤖 AI Menerjemahkan Tugas -> Toko: {username}, Keyword: {keyword}, Limit: {limit}, Aturan Khusus: {custom_rules}")
    
    daftar_url = get_store_product_urls(
        username=username, 
        keyword=keyword, 
        limit=limit, 
        is_all=is_all,
        custom_rules=custom_rules 
    )
    
    for target_url in daftar_url:
        data_produk = scrape_shopee_playwright(target_url)
        
        # --- REM DARURAT ---
        if data_produk and data_produk.get("status") == "BLOCKED":
            print("🛑 ALERT: Terhenti paksa karena CAPTCHA/Hard Block.")
            break
            
        if data_produk:
            semua_data.append(data_produk)
            save_to_database(data_produk)
        time.sleep(2)

    return {"message": "Selesai", "results": semua_data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)