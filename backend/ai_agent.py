import json
import os
from google import genai

# --- FUNGSI 1: MENGUBAH KALIMAT USER MENJADI PARAMETER SCRAPING ---
def parse_scraping_intent(user_prompt: str):
    """
    Membaca kalimat natural dari user dan mengubahnya menjadi parameter terstruktur (JSON).
    Juga melakukan validasi jika ada parameter penting yang kurang.
    """
    print(f"🧠 [AI Agent] Menganalisis intent dari prompt: '{user_prompt}'")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        prompt = f"""Kamu adalah asisten pintar ekstraksi data e-commerce. Tugasmu adalah membaca perintah user dan mengubahnya menjadi parameter JSON.

        Perintah User: "{user_prompt}"

        Aturan Ekstraksi:
        1. "username": Ekstrak nama toko (misal dari "toko ibox" -> "ibox"). Jika tidak ada, kembalikan null.
        2. "keyword": Ekstrak kata kunci produk yang dicari (misal "iphone 17" atau "keripik pedas"). Jika tidak spesifik, kembalikan string kosong "".
        3. "limit": Ekstrak jumlah angka target produk (misal "2 produk", "sebanyak 2" -> 2). Jika meminta "semua produk", jadikan null. Jika tidak menyebutkan angka, jadikan null.
        4. "isAll": true jika user secara eksplisit meminta "semua produk", jika tidak kembalikan false.
        5. "custom_rules": Ekstrak instruksi tambahan (batasan eksklusif). Misal: "tanpa aksesoris", "hanya warna merah", "jangan ambil yang rasa manis". Jika user TIDAK memberikan batasan eksplisit, kembalikan string kosong "".
        6. "is_valid": true JIKA "username" TIDAK null DAN ("limit" TIDAK null ATAU "isAll" bernilai true). False jika ada salah satu yang kurang.
        7. "message": Jika is_valid false, buatkan pesan ramah beritahu apa yang kurang. (Contoh: "Mohon sebutkan nama toko dan jumlah target produknya ya."). Jika is_valid true, kembalikan string kosong "".

        KEMBALIKAN HANYA FORMAT JSON MURNI TANPA MARKDOWN ```json."""

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )
        
        # Bersihkan format markdown
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        intent_data = json.loads(clean_text)
        
        print(f"🎯 [AI Agent] Hasil Parsing Intent: {intent_data}")
        return intent_data
        
    except Exception as e:
        print(f"❌ [AI Agent] Error Parsing Intent: {e}")
        return {
            "is_valid": False, 
            "message": "Maaf, AI gagal memproses perintahmu. Silakan isi form secara manual."
        }


# --- FUNGSI 2: FILTER PRODUK DINAMIS BERDASARKAN PRIORITAS ---
def filter_urls_with_gemini(raw_products, keyword, target_limit, custom_rules=""):
    """
    Agen AI untuk menyaring produk e-commerce berdasarkan relevansi semantik.
    """
    if not keyword or not raw_products:
        return [p['url'] for p in raw_products][:target_limit]
    
    print(f"🧠 [AI Agent] Menyaring {len(raw_products)} produk '{keyword}' | Aturan: '{custom_rules}'")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Logika Injeksi Aturan Dinamis Berbasis Prioritas
        if custom_rules and custom_rules.strip() != "":
            rule_text = f"""
            ATURAN KHUSUS DARI USER: "{custom_rules}"
            Kamu WAJIB mematuhi aturan ini dengan ketat saat menyeleksi produk.
            """
        else:
            rule_text = f"""
            ATURAN DEFAULT (Sangat Ketat):
            - PRIORITAS MUTLAK: Hanya pilih produk yang BENAR-BENAR merupakan item utama dari keyword "{keyword}".
            - TOLAK SEMUA produk pendamping (aksesoris, casing, kabel, tempered glass, dll) KECUALI keyword tersebut memang secara eksplisit menyebutkan nama aksesorisnya (misal: "casing iphone 17").
            - Kualitas data lebih penting daripada kuantitas. Jika dari daftar hanya ada 1 produk yang benar-benar sesuai dengan keyword utama, KEMBALIKAN 1 SAJA. Jangan pernah mengisi sisa kuota dengan aksesoris yang tidak relevan.
            """

        prompt = f"""Kamu adalah filter mesin pencari e-commerce tingkat lanjut. User mencari produk: "{keyword}".
        Pahami bahwa penjual sering menyingkat seri (contoh "iPhone" menjadi "IP").
        
        Tugasmu:
        1. Evaluasi daftar produk di bawah ini berdasarkan judulnya.
        {rule_text}
        
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
        print(f"🎯 [AI Agent] Gemini meloloskan {len(valid_urls)} URL yang benar-benar relevan.")
        return valid_urls[:target_limit]
        
    except Exception as e:
        print(f"❌ [AI Agent] Error Gemini Filter: {e}")
        return [p['url'] for p in raw_products][:target_limit]