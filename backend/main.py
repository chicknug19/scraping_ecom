from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyodbc
import os
import time
from dotenv import load_dotenv
from scraper_engine import get_competitor_urls, scrape_shopee_playwright
from typing import Optional
from google import genai
from google.genai import types
from scraper_engine import get_competitor_urls, scrape_shopee_playwright, get_store_product_urls


load_dotenv()
app = FastAPI()

# Mengizinkan Frontend (React) berkomunikasi dengan Backend (Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FUNGSI 1: ALAT (TOOL) UNTUK GEMINI ---
def get_competitor_data_from_db(keyword: str, limit: int = 20):
    """
    Mengambil data harga produk kompetitor dari database untuk dianalisis.
    
    Args:
        keyword: Kata kunci produk yang dicari (misal: "iphone 17").
        limit: Jumlah maksimum produk yang ingin ditarik (default 20).
    """
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
                i.ItemName, i.ShopName, i.Location, i.TotalSold, v.VariantName, v.Price
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
                "Lokasi": row.Location,
                "Produk": row.ItemName,
                "Varian": row.VariantName,
                "Harga": float(row.Price),
                "Terjual": row.TotalSold
            })
        
        return results if results else [{"message": f"Tidak ada data ditemukan untuk keyword: {keyword}"}]
    except Exception as e:
        return [{"error": str(e)}]

# --- MODEL REQUEST FRONTEND ---
class ChatRequest(BaseModel):
    user_prompt: str

# --- ENDPOINT 2: CHAT AI DENGAN FUNCTION CALLING ---
@app.post("/api/analyze")
def chat_with_ai(req: ChatRequest):
    print(f"Menerima prompt dari frontend: {req.user_prompt[:50]}...")
    
    try:
        # Inisialisasi Client menggunakan SDK baru
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Membuat sesi obrolan dan menanamkan fungsi database kita sebagai alat (tools)
        chat = client.chats.create(
            model="gemini-3.5-flash",
            config=types.GenerateContentConfig(
                tools=[get_competitor_data_from_db],
            )
        )
        
        # Mengirim prompt pengguna. AI akan otomatis mengeksekusi SQL jika diminta!
        response = chat.send_message(req.user_prompt)
        
        return {
            "message": "Sukses",
            "ai_response": response.text
        }

    except Exception as e:
        print(f"Error AI Analysis: {e}")
        return {"error": str(e)}

class ScrapeRequest(BaseModel):
    keyword: str
    limit: int = 10
    location: Optional[str] = ""

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

        # ---------------------------------------------------------
        # TAHAP 1: CARI ATAU BUAT PROFIL TOKO (UPSERT STORES)
        # ---------------------------------------------------------
        cursor.execute("SELECT StoreID FROM Stores WHERE ShopName = ?", data['shop_name'])
        store_row = cursor.fetchone()

        # Ambil data lengkap dari scraper
        nib_data = data.get('nib', 'Tidak Ada NIB')
        followers_data = data.get('followers', 0)
        products_data = data.get('total_products', 0)
        shop_rating_data = data.get('shop_rating', 0.0)
        username_data = data.get('username') or data['shop_name'].replace(" ", "").lower()[:50]

        if store_row:
            store_id = store_row[0]
            # UPDATE: Perbarui Followers dan Rating setiap kali produknya discrape
            cursor.execute("""
                UPDATE Stores 
                SET FollowersCount = ?, TotalProducts = ?, Rating = ?, LastUpdated = GETDATE(),
                    NIB = CASE WHEN NIB = 'Tidak Ada NIB' OR NIB IS NULL THEN ? ELSE NIB END
                WHERE StoreID = ?
            """, followers_data, products_data, shop_rating_data, nib_data, store_id)
        else:
            # INSERT: Masukkan data toko secara utuh
            cursor.execute("""
                INSERT INTO Stores (Username, ShopName, NIB, FollowersCount, TotalProducts, Rating) 
                OUTPUT INSERTED.StoreID 
                VALUES (?, ?, ?, ?, ?, ?)
            """, username_data, data['shop_name'], nib_data, followers_data, products_data, shop_rating_data)
            store_id = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # TAHAP 2: UPSERT DATA PRODUK (ITEMS)
        # ---------------------------------------------------------
        cursor.execute("SELECT ItemCode FROM Items WHERE ItemName = ? AND StoreID = ?", data['item_name'], store_id)
        item_row = cursor.fetchone()

        if item_row:
            generated_item_code = item_row[0]
            cursor.execute("""
                UPDATE Items 
                SET TotalRatings = ?, TotalSold = ?, RatingStar = ?, ImageURL = ?, Location = ?
                WHERE ItemCode = ?
            """, data['total_ratings'], data['sold'], data['rating_star'], data['image_url'], data['location'], generated_item_code)
            
            cursor.execute("DELETE FROM ItemVariants WHERE ItemCode = ?", generated_item_code)
        else:
            cursor.execute("""
                INSERT INTO Items (ItemName, StoreID, Location, RatingStar, TotalRatings, TotalSold, ImageURL, SourceURL)
                OUTPUT INSERTED.ItemCode
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data['item_name'], store_id, data['location'], data['rating_star'], data['total_ratings'], data['sold'], data['image_url'], data['source_url'])
            generated_item_code = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # TAHAP 3: INSERT VARIAN & HARGA TERBARU
        # ---------------------------------------------------------
        if generated_item_code and data['variants']:
            query_variant = """
                INSERT INTO ItemVariants (ItemCode, VariantName, Price)
                VALUES (?, ?, ?)
            """
            for varian in data['variants']:
                cursor.execute(query_variant, generated_item_code, varian['variant_name'], varian['price'])

        conn.commit()
        conn.close()
        print(f"✅ [DB] Sukses upsert item ID {generated_item_code} untuk Toko {store_id}")
    except Exception as e:
        print(f"❌ Error DB: {e}")



@app.post("/api/scrape")
def run_scraper(req: ScrapeRequest):
    print(f"Menerima request dari frontend: {req.keyword} (Limit: {req.limit}, Lokasi: {req.location})")
    
    # Kirim parameter location ke fungsi get_competitor_urls
    daftar_url = get_competitor_urls(keyword=req.keyword, limit=req.limit, location=req.location)
    semua_data = []

    for target_url in daftar_url:
        data_produk = scrape_shopee_playwright(target_url)
        if data_produk:
            semua_data.append(data_produk)
            save_to_database(data_produk)
        time.sleep(2)

    return {"message": "Selesai", "results": semua_data}


# --- FUNGSI AI: NORMALISASI USERNAME TOKO ---
def normalize_shopee_username(raw_username: str) -> str:
    if not raw_username or raw_username.strip() == "":
        return ""
        
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = f"""Kamu adalah ahli data e-commerce Indonesia. Tugasmu adalah mengubah input user berupa nama toko menjadi username/slug resmi Shopee.
        Contoh: 'i box' -> 'iboxofficial', 'queen phone' -> 'queenphonee', 'maybelline' -> 'maybellineindonesiaofficialstore'.
        Jika kamu tidak mengetahui nama resminya, cukup hapus semua spasi dan jadikan huruf kecil.
        Input User: '{raw_username}'
        KEMBALIKAN HANYA USERNAME, TANPA TEKS ATAU TANDA BACA LAIN."""
        
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )
        # AI merespons, kita bersihkan spasi tambahan untuk keamanan
        return response.text.strip().replace(" ", "").lower()
    except Exception as e:
        print(f"⚠️ Error AI Normalization: {e}")
        return raw_username.replace(" ", "").lower()

# Model untuk tugas individual
class StoreTask(BaseModel):
    username: str
    keyword: str = ""
    limit: int = 10
    isAll: bool = False

# Model pembungkus array tugas
class StoreScrapeRequest(BaseModel):
    tasks: list[StoreTask]

@app.post("/api/scrape-stores")
def run_store_scraper(req: StoreScrapeRequest):
    print(f"\n🚀 Memulai Multi-Task Store Scraper. Total Tugas: {len(req.tasks)}")
    semua_data = []

    for task in req.tasks:
        # 1. Panggil Gemini untuk membersihkan nama toko
        clean_username = normalize_shopee_username(task.username)
        print(f"🤖 AI memvalidasi toko: '{task.username}' -> menjadi '{clean_username}'")
        
        # 2. Panggil API cerdas dengan username yang sudah bersih
        daftar_url = get_store_product_urls(
            username=clean_username, 
            keyword=task.keyword, 
            limit=task.limit, 
            is_all=task.isAll
        )
        
        for target_url in daftar_url:
            data_produk = scrape_shopee_playwright(target_url)
            if data_produk:
                semua_data.append(data_produk)
                save_to_database(data_produk)
            time.sleep(2)

    return {"message": f"Berhasil memproses {len(req.tasks)} tugas.", "results": semua_data}

if __name__ == "__main__":
    import uvicorn
    # Menjalankan server di port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)