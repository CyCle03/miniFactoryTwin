FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY modbus_simulator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY simulator ./simulator
COPY backend/app/modbus_map.py ./modbus_map.py
COPY modbus_simulator ./modbus_simulator
EXPOSE 5020
CMD ["python", "-m", "modbus_simulator.main"]
