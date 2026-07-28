FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (including CrewAI)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && \
    rm -rf /root/.cache/pip

# Install frontend dependencies and build
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm install

COPY . .

# Build frontend
RUN cd frontend && npm run build

EXPOSE 8000

CMD ["python", "backend/main.py"]
