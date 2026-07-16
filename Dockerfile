FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "ceche[cli,web]" && \
    adduser --disabled-password --gecos '' ceche

USER ceche

ENTRYPOINT ["ceche"]
CMD ["--help"]
