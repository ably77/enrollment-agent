FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates && \
    ARCH=$(dpkg --print-architecture) && \
    curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/${ARCH}/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY demo-ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY demo-ui/ .
COPY k8s/ /app/k8s/

EXPOSE 8501
CMD ["streamlit", "run", "Homepage.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
