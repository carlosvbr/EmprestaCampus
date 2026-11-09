FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Aplica as correções de segurança do Debian publicadas depois da imagem
# base (ex.: zlib1g, CVE-2026-85091, apontada pelo Trivy no pipeline).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

COPY . .

EXPOSE 8000