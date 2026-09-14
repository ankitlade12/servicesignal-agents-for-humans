FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng gosu && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY schemas ./schemas
COPY static ./static
COPY scripts ./scripts
RUN useradd --create-home signal && mkdir -p data && chown -R signal:signal /app
ENTRYPOINT ["bash", "scripts/container-entrypoint.sh"]
ENV SERVICESIGNAL_HOST=0.0.0.0 SERVICESIGNAL_PORT=8017
EXPOSE 8017
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD .venv/bin/python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT',os.getenv('SERVICESIGNAL_PORT','8017'))+'/api/ready', timeout=3)"
CMD ["bash", "scripts/start.sh"]
