FROM python:3.11-slim
WORKDIR /app
COPY audiosocket_relay/ ./audiosocket_relay/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python3", "-m", "app.py"]
