FROM python:3.12-slim

WORKDIR /app

#Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

#Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Install yt-dlp separately (updates frequently)
RUN pip install --no-cache-dir yt-dlp

#Copy application code
COPY . .

#Create non-root user
RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

CMD ["python", "main.py"]
