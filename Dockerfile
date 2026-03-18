FROM python:3.12-slim-bookworm

# Install system dependencies for PrusaSlicer
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    libgl1 \
    libglu1-mesa \
    libglib2.0-0 \
    libgtk-3-0 \
    libpng16-16 \
    libjpeg62-turbo \
    libgomp1 \
    libfuse2 \
    && rm -rf /var/lib/apt/lists/*

# Install PrusaSlicer 2.8.1 (last version with Linux binary on GitHub)
# Note: 2.9.x moved Linux distribution to Flathub only
RUN wget -q "https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.8.1/PrusaSlicer-2.8.1%2Blinux-x64-older-distros-GTK3-202409181354.AppImage" \
    -O /opt/prusaslicer.AppImage \
    && chmod +x /opt/prusaslicer.AppImage \
    && cd /opt && ./prusaslicer.AppImage --appimage-extract \
    && ls -la /opt/squashfs-root/usr/bin/ \
    && find /opt/squashfs-root -name "prusa-slicer" -o -name "PrusaSlicer" | head -10 \
    && ln -sf /opt/squashfs-root/usr/bin/prusa-slicer /usr/local/bin/prusa-slicer \
    && rm /opt/prusaslicer.AppImage

# Set up Python app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
