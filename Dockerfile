FROM python:3.11-slim

WORKDIR /app

# Install the package (src layout)
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Run the MCP server
ENTRYPOINT ["roleplaying-dice-mcp"]
