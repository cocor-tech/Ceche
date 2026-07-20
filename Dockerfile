FROM python:3.12-slim AS builder

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir pymysql bcrypt && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos '' ceche

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/ceche /usr/local/bin/ceche

USER ceche
EXPOSE 8080
CMD ["ceche", "server", "serve", "--port", "8080", "--host", "0.0.0.0"]
