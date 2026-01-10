# Gunakan base image Python yang ringan (Slim version)
FROM python:3.9-slim

# Set folder kerja di dalam container
WORKDIR /app

# Copy requirements dulu (agar caching layer docker efisien)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy sisa source code (main.py)
COPY . .

# Expose port yang digunakan FastAPI
EXPOSE 8000

# Perintah untuk menjalankan aplikasi saat container start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]