FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATABASE_URL=sqlite:////app/data/teaguard.db
ENV UPLOAD_DIR=/app/uploads
EXPOSE 8785
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8785"]
