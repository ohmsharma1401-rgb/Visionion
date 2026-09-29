FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
COPY backend backend
COPY alembic.ini alembic.ini
COPY config config
COPY ml/models ml/models
RUN mkdir data
EXPOSE 8000
CMD ["sh","-c","python -m alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
