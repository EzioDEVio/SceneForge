FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 git && rm -rf /var/lib/apt/lists/*
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8881
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8881"]
