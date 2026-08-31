from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pyodbc
import os
from dotenv import load_dotenv

# Load variabel dari file .env
load_dotenv()

app = FastAPI(title="Pricing AI Agent API")

# Setup CORS agar React bisa menembak API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Saat production, ganti dengan domain React-mu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    # Mengambil konfigurasi dari .env
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    driver = '{ODBC Driver 17 for SQL Server}' # Pastikan driver ini terinstall di Windows kamu

    conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'
    conn = pyodbc.connect(conn_str)
    return conn

@app.get("/")
def read_root():
    return {"message": "Pricing AI Backend is Running!"}

@app.get("/api/products")
def get_scraped_products():
    """
    Endpoint ini nantinya dipakai oleh React untuk mengambil data
    dari tabel st_scraping di Azure SQL.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Query disesuaikan dengan nama tabelmu
        cursor.execute("SELECT TOP 50 * FROM st_scraping ORDER BY dtime DESC")
        
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return {"status": "success", "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}