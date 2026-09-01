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

        # Menggunakan OUTPUT INSERTED.ItemCode untuk langsung menangkap ID yang baru dibuat
        query_item = """
            INSERT INTO Items (ItemName, ShopName, Location, RatingStar, TotalRatings, TotalSold, ImageURL, SourceURL)
            OUTPUT INSERTED.ItemCode
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query_item, data['item_name'], data['shop_name'], data['location'], data['rating_star'], data['total_ratings'], data['sold'], data['image_url'], data['source_url'])
        
        row = cursor.fetchone()
        generated_item_code = int(row[0]) if row and row[0] is not None else None

        if generated_item_code and data['variants']:
            query_variant = """
                INSERT INTO ItemVariants (ItemCode, VariantName, Price)
                VALUES (?, ?, ?)
            """
            for varian in data['variants']:
                cursor.execute(query_variant, generated_item_code, varian['variant_name'], varian['price'])

        conn.commit()
        conn.close()
        print(f"    [DB] Berhasil menyimpan item ID: {generated_item_code} dengan {len(data['variants'])} varian.")
    except Exception as e:
        print(f"Error DB: {e}")



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