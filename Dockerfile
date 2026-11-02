FROM python:3.12-slim

LABEL org.opencontainers.image.title="local-tts-bookorbit-piper-addon" \
      org.opencontainers.image.description="Local Piper text-to-speech server for BookOrbit" \
      org.opencontainers.image.source="https://github.com/crome1394/local-tts-bookorbit-piper-addon" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

ARG EXTRAS=""
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/data \
    BOOKORBIT_TTS_HOST=0.0.0.0 \
    BOOKORBIT_TTS_PORT=8765 \
    BOOKORBIT_TTS_DATA_DIR=/data \
    BOOKORBIT_TTS_ENGINE=piper \
    BOOKORBIT_TTS_THREADS=1 \
    BOOKORBIT_TTS_CONCURRENCY=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

# ffmpeg gives flac/opus/aac output and pitch-preserving speed changes.
# The server process does not run as root. A mounted /data must be writable
# by uid 10001 (see docker-compose.example.yml).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg espeak-ng \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --create-home --home-dir /data --shell /usr/sbin/nologin tts

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install ".${EXTRAS}" \
 && mkdir -p /usr/share/doc/local-tts-bookorbit-piper-addon \
 && cp LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/local-tts-bookorbit-piper-addon/ \
 && mkdir -p /data \
 && chown -R tts:tts /data

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

USER tts
VOLUME ["/data"]
EXPOSE 8765

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["bookorbit-tts", "serve"]
