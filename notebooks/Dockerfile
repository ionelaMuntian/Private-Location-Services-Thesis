FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

RUN echo "setuptools<82" > /tmp/constraints.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "setuptools<82" wheel && \
    pip install --no-cache-dir --timeout 300 \
    torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu

RUN PIP_CONSTRAINT=/tmp/constraints.txt pip install --no-cache-dir --timeout 300 \
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
