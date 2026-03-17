FROM python:3.12-slim-bookworm

# Install system dependencies for PrusaSlicer
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    curl \
    jq \
    libgl1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpng16-16 \
    libjpeg62-turbo \
    libgomp1 \
    libfuse2 \
    && rm -rf /var/lib/apt/lists/*

# Install PrusaSlicer - download the correct AppImage from GitHub releases API
RUN ASSET_URL=$(curl -s https://api.github.com/repos/prusa3d/PrusaSlicer/releases/tags/version_2.9.1 \
    | jq -r '.assets[] | select(.name | test("linux-x64-GTK3.*\\.AppImage$")) | .browser_download_url' \
    | head -1) \
    && echo "Downloading: $ASSET_URL" \
    && wget -q "$ASSET_URL" -O /opt/prusaslicer.AppImage \
    && chmod +x /opt/prusaslicer.AppImage \
    && cd /opt && ./prusaslicer.AppImage --appimage-extract \
    && ln -s /opt/squashfs-root/usr/bin/prusa-slicer /usr/local/bin/prusa-slicer \
    && rm /opt/prusaslicer.AppImage

# Set up Python app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
