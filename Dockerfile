FROM python:3.12-slim

# Install system dependencies for PrusaSlicer
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgtk-3-0 \
    libpng16-16 \
    libjpeg62-turbo \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install PrusaSlicer (console/headless version)
ARG PRUSASLICER_VERSION=2.9.1
RUN wget -q "https://github.com/prusa3d/PrusaSlicer/releases/download/version_${PRUSASLICER_VERSION}/PrusaSlicer-${PRUSASLICER_VERSION}+linux-x64-GTK3-202502270843.tar.bz2" \
    -O /tmp/prusaslicer.tar.bz2 \
    && mkdir -p /opt/prusaslicer \
    && tar -xjf /tmp/prusaslicer.tar.bz2 -C /opt/prusaslicer --strip-components=1 \
    && rm /tmp/prusaslicer.tar.bz2 \
    && ln -s /opt/prusaslicer/prusa-slicer /usr/local/bin/prusa-slicer

# Set up Python app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
