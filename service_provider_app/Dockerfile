FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    binutils \
    && rm -rf /var/lib/apt/lists/*

COPY service_provider_app/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY proto ./proto
COPY service_provider_app/app ./app
COPY service_provider_app/.env ./.env
COPY client_app/.artifacts ./client_app/.artifacts

RUN mkdir -p ./app/generated && \
    python -m grpc_tools.protoc \
      -I./proto \
      --python_out=./app/generated \
      --grpc_python_out=./app/generated \
      ./proto/service_provider.proto && \
    touch ./app/generated/__init__.py && \
    sed -i 's/import service_provider_pb2 as service__provider__pb2/from . import service_provider_pb2 as service__provider__pb2/' ./app/generated/service_provider_pb2_grpc.py

EXPOSE 8001
EXPOSE 50051

CMD ["sh", "-c", "python -m app.grpc_server & uvicorn app.main:app --host 0.0.0.0 --port 8001"]