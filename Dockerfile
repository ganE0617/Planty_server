FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    cron \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a cron job to pull from GitHub every 5 minutes
RUN echo "*/5 * * * * cd /app && git pull origin main >> /var/log/cron.log 2>&1" > /etc/cron.d/git-pull
RUN chmod 0644 /etc/cron.d/git-pull

# Apply cron job
RUN crontab /etc/cron.d/git-pull

# Start cron in the background and run the application
CMD service cron start && uvicorn main:app --host 0.0.0.0 --port 8000 --reload 
