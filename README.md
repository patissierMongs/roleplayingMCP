# Dice MCP Server

A Model Context Protocol (MCP) server that provides dice rolling functionality, containerized with Docker.

## Features

- **Roll d20 dice**: The server provides a single dice type (d20)
- **Default behavior**: Rolls 1d20 by default
- **Configurable count**: Change the number of dice to roll
- **Negative dice support**: Can accept negative dice counts for subtraction
- **Sum calculation**: Returns the total sum of all rolls

## Installation

### Prerequisites

- Docker
- Docker Compose (optional, for easier deployment)

### Building the Docker Image

```bash
docker build -t dice-mcp-server .
```

Or using Docker Compose:

```bash
docker-compose build
```

## Usage

### Running with Docker

```bash
docker run -i dice-mcp-server
```

### Running with Docker Compose

```bash
docker-compose up
```

### MCP Tool Usage

The server exposes a single tool called `roll_dice`:

**Tool Name**: `roll_dice`

**Parameters**:
- `count` (integer, optional): Number of d20 dice to roll. Default is 1. Can be negative.

**Examples**:

1. **Default roll (1d20)**:
   ```json
   {
     "name": "roll_dice"
   }
   ```
   Output: `Rolled 1d20: 15\nSum: 15`

2. **Roll multiple dice (3d20)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 3
     }
   }
   ```
   Output: `Rolled 3d20: [12, 7, 19]\nSum: 38`

3. **Roll negative dice (-2d20)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": -2
     }
   }
   ```
   Output: `Rolled 2d20: [8, 14]\nSum: -22 = -22`

4. **Roll zero dice**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 0
     }
   }
   ```
   Output: `No dice rolled (count = 0)\nSum: 0`

## Configuration with MCP Clients

To use this server with an MCP client (like Claude Desktop), add the following to your MCP settings:

```json
{
  "mcpServers": {
    "dice": {
      "command": "docker",
      "args": ["run", "-i", "dice-mcp-server"]
    }
  }
}
```

## Development

### Project Structure

```
.
├── server.py           # Main MCP server implementation
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker container definition
├── docker-compose.yml # Docker Compose configuration
└── README.md          # This file
```

### Local Development (without Docker)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python server.py
   ```

## License

MIT

## Author

Created for roleplaying and game mechanics support.
