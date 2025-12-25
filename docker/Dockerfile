FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Default config path
ENV CONFIG_PATH=/app/config/config.yaml

CMD ["python", "-m", "src.main", "--config", "/app/config/config.yaml"]
