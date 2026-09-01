# Menggunakan image resmi Microsoft Playwright yang sudah berisi Chromium
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Menentukan direktori kerja di dalam kontainer
WORKDIR /app

# Menyalin file daftar dependensi dan menginstalnya
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Kembalikan ke port 8000
EXPOSE 8000

# Jalankan Uvicorn di port 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]