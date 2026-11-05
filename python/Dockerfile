# A small always-on image for the Python Stage bot, meant to run next to
# AzuraCast on the same server. Uses the system ffmpeg.
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
COPY stagebot ./stagebot

# Joined channels are saved here; docker-compose.yml keeps it in a volume.
RUN useradd --system --uid 10001 bot && mkdir -p /data && chown bot:bot /data
ENV FFMPEG_PATH=/usr/bin/ffmpeg DATA_DIR=/data PYTHONUNBUFFERED=1
USER bot
CMD ["python", "main.py"]
