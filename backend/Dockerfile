# Vision Sentinel backend, CPU build. Context: the repository root (docker compose sets it).
# Stage 1 resolves dependencies into /venv with the CPU-only torch wheels (keeps the image well under 2.5 GB).
FROM python:3.12-slim AS build
ENV UV_LINK_MODE=copy PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir uv
WORKDIR /src
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv venv /venv \
 && uv export --frozen --no-dev --no-hashes --no-emit-project -o req.txt \
 && grep -vE '^(torch|torchvision)==' req.txt > req-notorch.txt \
 && VIRTUAL_ENV=/venv uv pip install --no-cache --index-url https://download.pytorch.org/whl/cpu torch torchvision \
 && VIRTUAL_ENV=/venv uv pip install --no-cache -r req-notorch.txt
# Fetch the fallback person model at build time so the container starts offline.
RUN mkdir -p /root/.cache/vision-sentinel && cd /root/.cache/vision-sentinel \
 && /venv/bin/python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')"

# Stage 2: runtime, non-root.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 sentinel
COPY --from=build /venv /venv
COPY --from=build --chown=sentinel /root/.cache/vision-sentinel /home/sentinel/.cache/vision-sentinel
WORKDIR /app
COPY --chown=sentinel backend/app backend/app
COPY --chown=sentinel config config
COPY --chown=sentinel data/samples data/samples
RUN mkdir -p models data/runtime && chown -R sentinel /app
USER sentinel
ENV PATH=/venv/bin:$PATH PYTHONUNBUFFERED=1 YOLO_CONFIG_DIR=/tmp/ultralytics
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
