# Если Docker Hub недоступен с сервера, задайте зеркало в .env: DOCKER_REGISTRY=mirror.gcr.io
ARG DOCKER_REGISTRY=docker.io
FROM ${DOCKER_REGISTRY}/library/python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt
COPY bot ./bot
COPY assets ./assets
CMD ["python", "-m", "bot"]
