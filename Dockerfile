FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# python:3.12-slim's pip no longer bundles setuptools/wheel, which older
# packages without a modern pyproject.toml build backend (rasterio 1.3.x's
# sdist) need at build time -- omitting this fails with
# "ModuleNotFoundError: No module named 'pkg_resources'" partway through.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir streamlit python-multipart python-jose[cryptography] passlib[bcrypt]

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV AFFI_AUTH_DISABLED=false

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
