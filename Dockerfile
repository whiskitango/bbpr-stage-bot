# A small always-on image, meant to run next to AzuraCast on the same server.
# Uses the system ffmpeg; ffmpeg-static's download is skipped.
FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY index.js ./
COPY src ./src

# Joined channels are saved here; docker-compose.yml keeps it in a volume.
RUN mkdir -p /data && chown node:node /data
ENV FFMPEG_PATH=/usr/bin/ffmpeg DATA_DIR=/data
USER node
CMD ["node", "index.js"]
