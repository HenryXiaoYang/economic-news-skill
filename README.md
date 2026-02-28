[中文版本](README_CN.md)

# Economic News Skill

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)

A real-time economic news service for OpenClaw agents, powered by Jin10 data source.

## Features

- Top 10 important events (editor curated)
- Real-time flash news with SSE subscription
- 19 news categories with sub-categories
- Keyword search
- Global market trading status (18 markets)

## Quick Start

### Prerequisites

- Python 3.10+
- Playwright

### Installation

```bash
# Clone the repository
git clone https://github.com/HenryXiaoYang/economic-news-skill.git
cd economic-news-skill

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Start the service
python3 main.py
```

The service will be available at `http://localhost:8765`.

## Usage

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Service status |
| `GET /top10` | Top 10 important events |
| `GET /latest` | Latest flash news |
| `GET /categories` | All news categories |
| `GET /category/{id}` | News by category |
| `GET /search?q=keyword` | Search news |
| `GET /clock` | Market trading status |
| `GET /events` | SSE real-time subscription |
| `GET /health` | Health check |

### Workflow

```
Need economic news?
|
+-- Important events --> GET /top10
|
+-- Latest news
|   +-- One-time --> GET /latest
|   +-- Real-time --> GET /events (SSE)
|
+-- Category news
|   +-- 1. GET /categories (find category ID)
|   +-- 2. GET /category/{id}
|
+-- Search keyword --> GET /search?q=keyword
|
+-- Market status --> GET /clock
```

### Real-time Notifications

**Option 1: Periodic (via cron)**

```bash
openclaw cron add \
  --name "economic-news" \
  --schedule "*/10 * * * *" \
  --task "Get latest 5 economic news and send to user"
```

**Option 2: Instant (via SSE)**

```bash
python3 notify.py -t "user:ou_xxx" -c feishu
python3 notify.py -t "user:ou_xxx" -c feishu --important  # important only
```

### Common Category IDs

| ID | Category | ID | Category |
|----|----------|----|----------|
| 2 | Gold | 53 | Fed |
| 6 | Oil | 46 | Middle East |
| 12 | Forex | 167 | Russia-Ukraine |
| 27 | US Stocks | 29 | A-Shares |

## Configuration

The service runs on port 8765 by default. Modify `main.py` to change.

## License

[MIT](LICENSE)
