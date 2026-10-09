# SafeVault — Automatic Backup & Restore Container Image
# Multi-platform Linux container with Python and Tkinter support
FROM python:3.11-slim

LABEL org.opencontainers.image.title="SafeVault" \
      org.opencontainers.image.description="Automatic Backup & Restore Desktop Application" \
      org.opencontainers.image.url="https://github.com/mayurchoudhary08-cloud/Safevault-Automatic-Backup-Application" \
      org.opencontainers.image.source="https://github.com/mayurchoudhary08-cloud/Safevault-Automatic-Backup-Application" \
      org.opencontainers.image.version="1.0.0"

# Install system dependencies for Tkinter and X11
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    tk-dev \
    tcl-dev \
    libx11-6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and install
COPY safevault/ safevault/
COPY tests/ tests/
COPY main.py .
RUN pip install --no-cache-dir .

ENTRYPOINT ["safevault"]
