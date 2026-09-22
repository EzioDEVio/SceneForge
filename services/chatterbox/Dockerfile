FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 git && rm -rf /var/lib/apt/lists/*
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8881
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8881"]
