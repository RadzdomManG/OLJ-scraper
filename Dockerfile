FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script and config
COPY . .

# Make data folder
RUN mkdir -p data

# Run the watcher
CMD ["python", "watcher.py"]

