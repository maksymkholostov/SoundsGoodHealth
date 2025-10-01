# Dockerfile for SoundClassifiers v10
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    portaudio19-dev \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 5001

# Command to run the application (production server)
# Bind to the platform PORT if provided (default 5001)
CMD ["sh", "-c", "gunicorn -w 1 -k gthread --threads 4 --timeout 0 -b 0.0.0.0:${PORT:-5001} wsgi:app"] 