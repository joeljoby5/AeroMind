# Build context is the repository root:  docker build -f backend/Dockerfile .
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/srv:/srv/backend
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai ./ai
COPY data ./data
COPY backend ./backend
WORKDIR /srv/backend
EXPOSE 8000
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
