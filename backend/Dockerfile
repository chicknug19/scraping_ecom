# Menggunakan image resmi Microsoft Playwright yang sudah berisi Chromium (Ubuntu Jammy 22.04)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# --- TAMBAHKAN BLOK INI: Menginstal Microsoft ODBC Driver 17 untuk PyODBC ---
RUN apt-get update && apt-get install -y curl apt-transport-https gnupg2 unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17
# ----------------------------------------------------------------------------

# Menyalin file daftar dependensi dan menginstalnya
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Kembalikan ke port 8000
EXPOSE 8000

# Jalankan Uvicorn di port 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]