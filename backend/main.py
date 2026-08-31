from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyodbc
import os
import time
from dotenv import load_dotenv
from scraper_engine import get_competitor_urls, scrape_shopee_playwright

load_dotenv()
app = FastAPI()

# Mengizinkan Frontend (React) berkomunikasi dengan Backend (Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    keyword: str
    limit: int = 10

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
    print(f"Menerima request dari frontend: {req.keyword} (Limit: {req.limit})")
    
    daftar_url = get_competitor_urls(keyword=req.keyword, limit=req.limit)
    semua_data = []

    for target_url in daftar_url:
        data_produk = scrape_shopee_playwright(target_url)
        
        if data_produk:
            semua_data.append(data_produk)
            # Jauh lebih rapi: kita cukup melempar 1 dictionary penuh ke fungsi DB
            save_to_database(data_produk)
            
        time.sleep(2)

    return {"message": "Selesai", "results": semua_data}

if __name__ == "__main__":
    import uvicorn
    # Menjalankan server di port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)