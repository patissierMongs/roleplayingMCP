FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source
COPY src/ ./src/
COPY server.py ./

# Make server executable
RUN chmod +x server.py

# Factor III: Config via environment variables
ENV DICE_SERVER_NAME=dice-server
ENV DICE_SERVER_VERSION=5.0.0
ENV DICE_HISTORY_MAX_SIZE=100
ENV DICE_LOG_LEVEL=INFO

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
