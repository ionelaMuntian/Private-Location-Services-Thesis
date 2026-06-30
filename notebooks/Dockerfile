FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --timeout 300 \
    concrete-ml==1.8.0 \
    imbalanced-learn==0.12.4

RUN pip install --no-cache-dir --timeout 300 \
    jupyterlab \
    jupytext \
    pandas \
    numpy \
    "scikit-learn==1.4.0" \
    joblib \
    matplotlib \
    seaborn

WORKDIR /notebooks

COPY notebooks/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8888

ENTRYPOINT ["/entrypoint.sh"]
