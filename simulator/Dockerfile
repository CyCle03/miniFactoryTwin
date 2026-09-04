FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY simulator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY simulator ./simulator
CMD ["python", "-m", "simulator.main"]

