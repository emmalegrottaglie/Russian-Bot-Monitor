FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TRACKER_DB=/data/tracker.db
WORKDIR /app

# Editable install: the app reads config/, web/ and the design kit relative to the source tree.
COPY pyproject.toml README.md ./
COPY tracker ./tracker
RUN pip install --no-cache-dir -e .

COPY config ./config
COPY web ./web
COPY terminal-design-system ./terminal-design-system

RUN useradd --system --uid 10001 tracker && mkdir /data && chown tracker /data
USER tracker
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python", "-m", "tracker", "serve", "--host", "0.0.0.0", "--port", "8000"]
