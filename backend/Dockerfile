FROM python:3.11-slim
WORKDIR /app
ENV DATABASE_URL=sqlite:////app/storage/verirag.db
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libgl1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY .env.example ./.env
RUN mkdir -p storage/documents storage/indexes
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
