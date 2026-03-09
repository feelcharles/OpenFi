# OpenFi API Documentation

## API Endpoints

### Base URL
```
http://localhost:8686/api
```

### Authentication
All API requests require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your_token>
```

---

## Core Endpoints

### 1. Dashboard
```http
GET /api/dashboard/metrics
GET /api/dashboard/recent-signals
```

### 2. Intelligence
```http
GET /api/intelligence/news
GET /api/intelligence/calendar
GET /api/intelligence/reports
GET /api/intelligence/sentiment
```

### 3. Market Data
```http
GET /api/market/watchlist
GET /api/market/quotes/{symbol}
GET /api/market/history/{symbol}
```

### 4. Quantitative Engine
```http
GET /api/quant/ea-profiles
POST /api/quant/ea-profiles
GET /api/quant/factors
POST /api/quant/backtest
```

### 5. AI & Agents
```http
GET /api/agents/list
POST /api/agents/create
PUT /api/agents/{agent_id}
DELETE /api/agents/{agent_id}
GET /api/agents/{agent_id}/config
```

### 6. Trading
```http
GET /api/trading/accounts
POST /api/trading/orders
GET /api/trading/positions
GET /api/trading/history
```

### 7. System
```http
GET /api/system/status
GET /api/system/health
GET /api/system/config
POST /api/system/config
```

---

## WebSocket

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8686/ws');
```

### Events
- `market_update` - Real-time market data
- `signal_alert` - Trading signals
- `system_status` - System status updates
- `agent_message` - Agent notifications

---

## Configuration

### Environment Variables
```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8686
API_DEBUG=false

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openfi
DB_USER=your_user
DB_PASSWORD=your_password

# LLM API Keys
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=your-key

# Bot Tokens
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Config Files
- `config/llm_config.yaml` - LLM providers
- `config/fetch_sources.yaml` - Data sources
- `config/push_config.yaml` - Push notifications
- `config/agent_system_config.yaml` - Agent settings

---

## Examples

### Get Market Data
```python
import requests

response = requests.get(
    'http://localhost:8686/api/market/quotes/EURUSD',
    headers={'Authorization': f'Bearer {token}'}
)
data = response.json()
```

### Create Agent
```python
agent_config = {
    "name": "Trading Agent",
    "llm_provider": "openai",
    "bot_type": "telegram",
    "permissions": ["read", "analyze"]
}

response = requests.post(
    'http://localhost:8686/api/agents/create',
    json=agent_config,
    headers={'Authorization': f'Bearer {token}'}
)
```

### WebSocket Subscription
```javascript
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'market_update') {
        console.log('Market update:', data.payload);
    }
};
```

---

## API Documentation UI

Interactive API documentation available at:
- Swagger UI: http://localhost:8686/docs
- ReDoc: http://localhost:8686/redoc

---

For detailed configuration, see the config files in the `config/` directory.
