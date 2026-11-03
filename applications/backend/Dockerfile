FROM python:3.12-slim
WORKDIR /app
COPY applications/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY applications/backend/ ./
COPY applications/frontend/ /frontend/
ENV FRONTEND_DIR=/frontend DB_PATH=/data/antecedengue.db
ENV HOST=0.0.0.0
# HOST=:: faz a API escutar em IPv6 (dual-stack no Linux); ver docker-compose.ipv6.yml
CMD ["sh","-c","uvicorn main:app --host ${HOST} --port 8000"]
