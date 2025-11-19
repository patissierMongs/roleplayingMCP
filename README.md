# Dice MCP Server

A Model Context Protocol (MCP) server that provides dice rolling functionality, containerized with Docker.

## Features

- **Roll d20 dice**: The server provides a single dice type (d20)
- **Default behavior**: Rolls 1d20 by default
- **Configurable count**: Change the number of positive dice to roll
- **Negative dice support**: Can accept negative dice counts for subtraction
  - Negative dice cannot be used alone
  - Positive dice count must be greater than negative dice count
- **Sum calculation**: Returns the total sum (positive rolls - negative rolls)

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
- `count` (integer, optional): Number of positive d20 dice to roll. Default is 1. Minimum is 1. Must be greater than `negative_count`.
- `negative_count` (integer, optional): Number of negative d20 dice to roll. Default is 0. Minimum is 0. Must be less than `count`. Cannot be used alone.

**Rules**:
- Negative dice cannot be used alone (count must be at least 1)
- Positive dice count must be greater than negative dice count

**Examples**:

1. **Default roll (1d20)**:
   ```json
   {
     "name": "roll_dice"
   }
   ```
   Output: `Rolled 1d20: 15\nSum: 15`

2. **Roll multiple positive dice (3d20)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 3
     }
   }
   ```
   Output: `Rolled 3d20: [12, 7, 19]\nSum: 38`

3. **Roll with negative dice (3d20 - 1d20)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 3,
       "negative_count": 1
     }
   }
   ```
   Output:
   ```
   Rolled 3d20: [15, 8, 12]
   Rolled -1d20: [6]
   Sum: 35 - 6 = 29
   ```

4. **Roll with multiple negative dice (5d20 - 2d20)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 5,
       "negative_count": 2
     }
   }
   ```
   Output:
   ```
   Rolled 5d20: [18, 3, 11, 7, 14]
   Rolled -2d20: [9, 12]
   Sum: 53 - 21 = 32
   ```

5. **Invalid: negative dice alone (ERROR)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 0,
       "negative_count": 2
     }
   }
   ```
   Output: `Error: Positive dice count must be at least 1`

6. **Invalid: negative_count >= count (ERROR)**:
   ```json
   {
     "name": "roll_dice",
     "arguments": {
       "count": 2,
       "negative_count": 2
     }
   }
   ```
   Output: `Error: Positive dice count (2) must be greater than negative dice count (2)`

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
