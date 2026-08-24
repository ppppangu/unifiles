FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV UNIFILES_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health', timeout=2)"
CMD ["unifiles-server", "--host", "0.0.0.0", "--port", "8088"]
