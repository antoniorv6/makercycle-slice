FROM python:3.12-slim-bookworm

# Install system dependencies for PrusaSlicer (OpenGL/EGL/GTK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    libgl1 \
    libglu1-mesa \
    libegl1 \
    libgles2 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpng16-16 \
    libjpeg62-turbo \
    libgomp1 \
    libfuse2 \
    libwebkit2gtk-4.0-37 \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Install PrusaSlicer 2.8.1 (last version with Linux binary on GitHub)
# Note: 2.9.x moved Linux distribution to Flathub only
RUN wget -q "https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.8.1/PrusaSlicer-2.8.1%2Blinux-x64-older-distros-GTK3-202409181354.AppImage" \
    -O /opt/prusaslicer.AppImage \
    && chmod +x /opt/prusaslicer.AppImage \
    && cd /opt && ./prusaslicer.AppImage --appimage-extract \
    && rm /opt/prusaslicer.AppImage

# Debug: list AppImage binary structure
RUN echo "=== AppImage binaries ===" \
    && find /opt/squashfs-root -maxdepth 4 -type f \( -name "prusa-slicer*" -o -name "PrusaSlicer*" \) 2>/dev/null \
    && echo "=== usr/bin contents ===" \
    && ls -la /opt/squashfs-root/usr/bin/ 2>/dev/null | head -20 \
    && echo "=== End ==="

# Create wrapper - call binary directly (AppRun has path bugs with --appimage-extract)
RUN echo '#!/bin/bash' > /usr/local/bin/prusa-slicer \
    && echo 'export LD_LIBRARY_PATH="/opt/squashfs-root/usr/lib:${LD_LIBRARY_PATH}"' >> /usr/local/bin/prusa-slicer \
    && echo 'exec xvfb-run -a /opt/squashfs-root/usr/bin/prusa-slicer "$@"' >> /usr/local/bin/prusa-slicer \
    && chmod +x /usr/local/bin/prusa-slicer \
    && cat /usr/local/bin/prusa-slicer

# Verify PrusaSlicer can at least show version
RUN prusa-slicer --help 2>&1 | head -5 || echo "Warning: PrusaSlicer help check returned non-zero (may still work for slicing)"

# Set up Python app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
