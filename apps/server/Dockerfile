FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY packages/generated/server-protocol-python ./packages/generated/server-protocol-python
COPY apps/server ./apps/server
RUN pip install --no-cache-dir ./packages/generated/server-protocol-python
RUN pip install --no-cache-dir ./apps/server

ENV UNIFILES_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health', timeout=2)"
CMD ["unifiles-server", "--host", "0.0.0.0", "--port", "8088"]
