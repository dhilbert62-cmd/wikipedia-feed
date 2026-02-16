# Wikipedia Infinite Feed

A self-hosted Wikipedia reader with infinite scroll and intelligent article recommendations.

## Features

- **Infinite scroll** - Never run out of Wikipedia to read
- **Multiple algorithms** - Random, Category, Jeopardy, User-Based
- **Dual modes** - Local (ZIM file) or Live (Wikipedia API)
- **Click tracking** - Learns your preferences over time
- **Dark theme** - Easy on the eyes

## Quick Start

```bash
# Clone and install
pip install -r requirements.txt

# Run server
python server.py

# Open browser
http://localhost:8080
```

## Requirements

- Python 3.8+
- Wikipedia ZIM file (optional, for offline mode)
- Flask

## Modes

| Mode | Description |
|------|-------------|
| Random | Pure random articles |
| Category | Filter by topic (Science, History, etc.) |
| Jeopardy | Weighted distribution |
| User-Based | Learns from your clicks |

## Configuration

Edit `config.py` to customize:
- Server port
- ZIM file path
- Default algorithm
- Click history database

## License

MIT
