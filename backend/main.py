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

        # Ambil NIB dari data scraper, default ke "Tidak Ada NIB" jika kosong
        nib_data = data.get('nib', 'Tidak Ada NIB')

        if store_row:
            store_id = store_row[0]
            # Opsional: Update NIB jika sebelumnya "Tidak Ada NIB" tapi sekarang ketemu
            cursor.execute("UPDATE Stores SET NIB = ? WHERE StoreID = ? AND NIB = 'Tidak Ada NIB'", nib_data, store_id)
        else:
            fake_username = data['shop_name'].replace(" ", "").lower()[:50]
            cursor.execute("""
                INSERT INTO Stores (Username, ShopName, NIB) 
                OUTPUT INSERTED.StoreID 
                VALUES (?, ?, ?)
            """, fake_username, data['shop_name'], nib_data)
            store_id = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # TAHAP 2: UPSERT DATA PRODUK (ITEMS)
        # ---------------------------------------------------------
        # Cek apakah produk ini dari toko ini sudah ada di database
        cursor.execute("SELECT ItemCode FROM Items WHERE ItemName = ? AND StoreID = ?", data['item_name'], store_id)
        item_row = cursor.fetchone()

        if item_row:
            # JIKA ADA: Cukup perbarui angka penjualan dan rating terbaru
            generated_item_code = item_row[0]
            cursor.execute("""
                UPDATE Items 
                SET TotalRatings = ?, TotalSold = ?, RatingStar = ?, ImageURL = ?, Location = ?
                WHERE ItemCode = ?
            """, data['total_ratings'], data['sold'], data['rating_star'], data['image_url'], data['location'], generated_item_code)
            
            # Bersihkan varian lama agar bisa diganti dengan harga hari ini
            cursor.execute("DELETE FROM ItemVariants WHERE ItemCode = ?", generated_item_code)
        else:
            # JIKA BELUM ADA: Masukkan sebagai produk baru
            # Pastikan tabel Items milikmu sudah memiliki kolom StoreID dan membuang kolom ShopName
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

if __name__ == "__main__":
    import uvicorn
    # Menjalankan server di port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)