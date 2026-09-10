import cv2
import numpy as np
import time
import random
import urllib.request
import os
import json
import pyodbc
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# Ganti dengan Username dan Password Shopee (BUKAN password email Google)
SHOPEE_USER = "ikantauco695" 
SHOPEE_PASS = "f-d4KJuVyzCnxkt"

# --- FUNGSI DATABASE ---
def save_cookie_to_azure(cookie_json):
    print("⚙️ Menghubungkan ke Azure SQL Database...")
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    driver = '{ODBC Driver 17 for SQL Server}'
    conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AppConfigs' and xtype='U')
            CREATE TABLE AppConfigs (ConfigKey VARCHAR(50) PRIMARY KEY, ConfigValue NVARCHAR(MAX), LastUpdated DATETIME)
        """)
        cursor.execute("""
            IF EXISTS (SELECT 1 FROM AppConfigs WHERE ConfigKey = 'SHOPEE_COOKIE')
                UPDATE AppConfigs SET ConfigValue = ?, LastUpdated = DATEADD(hour, 7, GETUTCDATE()) WHERE ConfigKey = 'SHOPEE_COOKIE'
            ELSE
                INSERT INTO AppConfigs (ConfigKey, ConfigValue, LastUpdated) VALUES ('SHOPEE_COOKIE', ?, DATEADD(hour, 7, GETUTCDATE()))
        """, cookie_json, cookie_json)
        conn.commit()
        print("🚀 SUPER SEKALI! Kuki AI sukses diamankan ke Database Azure.")
    except Exception as e:
        print(f"❌ Gagal menyimpan ke database: {e}")
    finally:
        if 'conn' in locals(): conn.close()

# --- FUNGSI COMPUTER VISION ---
def download_image(url, filename):
    urllib.request.urlretrieve(url, filename)

def solve_puzzle(bg_path, puzzle_path):
    print("🧠 OpenCV menganalisis matriks gambar...")
    bg = cv2.imread(bg_path, 0)
    puzzle = cv2.imread(puzzle_path, 0)
    
    bg_edge = cv2.Canny(bg, 100, 200)
    puzzle_edge = cv2.Canny(puzzle, 100, 200)
    
    result = cv2.matchTemplate(bg_edge, puzzle_edge, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)
    
    jarak_x = max_loc[0] 
    print(f"🎯 Target Koordinat X ditemukan: Geser {jarak_x} pixel.")
    return jarak_x

def geser_slider(page, slider_element, jarak_x):
    box = slider_element.bounding_box()
    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2
    
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    time.sleep(random.uniform(0.1, 0.3))
    
    current_x = start_x
    sisa = jarak_x
    
    while sisa > 0:
        step = min(random.randint(5, 20), sisa)
        current_x += step
        sisa -= step
        page.mouse.move(current_x, start_y + random.uniform(-2, 2))
        time.sleep(random.uniform(0.01, 0.04))
        
    page.mouse.up()
    print("✅ Simulasi geseran tangan selesai!")

# --- ALUR UTAMA ---
def auto_login_cv():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        print("🌐 Membuka halaman login Shopee...")
        page.goto("https://shopee.co.id/buyer/login", timeout=60000)

        try:
            lang_btn = page.locator('button').filter(has_text="Bahasa Indonesia").first
            if lang_btn.is_visible(timeout=3000): lang_btn.click(); time.sleep(1)
        except: pass

        print("⌨️ Mengisi Kredensial...")
        page.locator('input[name="loginKey"]').fill(SHOPEE_USER)
        time.sleep(0.5)
        page.locator('input[name="password"]').fill(SHOPEE_PASS)
        page.keyboard.press("Enter")

        print("⏳ Menunggu tantangan Slider...")
        try:
            # Mencari elemen slider (Class ini mungkin harus kamu sesuaikan jika Shopee mengubahnya)
            bg_element = page.locator('.shopee-captcha__bg-image') 
            puzzle_element = page.locator('.shopee-captcha__puzzle-image') 
            slider_btn = page.locator('.shopee-captcha__slider-button') 
            
            bg_element.wait_for(timeout=10000)
            
            download_image(bg_element.get_attribute("src"), "bg.png")
            download_image(puzzle_element.get_attribute("src"), "puzzle.png")
            
            jarak = solve_puzzle("bg.png", "puzzle.png")
            geser_slider(page, slider_btn, jarak)
            
        except Exception as e:
            print(f"⚠️ Slider tidak muncul atau error CV: {e}")
            print("👉 Mengalihkan ke mode tunggu manual...")

        print("⏳ Menunggu verifikasi masuk ke beranda (Maks 3 menit)...")
        try:
            page.wait_for_url("https://shopee.co.id/**", timeout=180000) 
            time.sleep(3)
            cookies = context.cookies()
            save_cookie_to_azure(json.dumps(cookies))
        except Exception as e:
            print("❌ Gagal mencapai beranda.")

        browser.close()

if __name__ == "__main__":
    auto_login_cv()