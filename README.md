# OpenFi - Your Intelligent Trading Copilot

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](.)

> **Cutting through noise with valuable intelligence news**  
> **Mastering markets with multi-dimensional analytics**  
> **Operating within a bank-secure private space**

**[English](README.md)** | **[中文](README_CN.md)**

---

## 🚀 Quick Start

### One-Command Deployment

```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh -o deploy.sh && sudo bash deploy.sh
```

**Start service after deployment**:
```bash
systemctl start openfi
```

**Access after deployment**:
- **Main App**: `http://YOUR_SERVER_IP:8686/app`
- API Docs: `http://YOUR_SERVER_IP:8686/docs`
- Health Check: `http://YOUR_SERVER_IP:8686/health`

**Default Credentials**: 
- Username: `admin`
- Password: `admin123`
- ⚠️ **Must change password on first login**

**Requirements**: 
- OS: Ubuntu 20.04+ / CentOS 7+ / Debian 11+
- CPU: 2+ cores
- RAM: 2+ GB
- Python: 3.11+

### Server Management

**Start Server**:
```bash
systemctl start openfi
```

**Stop Server**:
```bash
systemctl stop openfi
```

**Restart Server**:
```bash
systemctl restart openfi
```

**Check Service Status**:
```bash
systemctl status openfi
```

**View Live Logs**:
```bash
journalctl -u openfi -f
```

### System Reset

⚠️ **Dangerous Operation**: This will delete all data including database, configuration files, and logs. Cannot be recovered!

```bash
sudo bash /opt/openfi/scripts/reset_system.sh
```

Reset process requires:
1. Enter `YES` (uppercase) for first confirmation
2. Enter `RESET` (uppercase) for second confirmation
3. Enter administrator password for verification
4. Wait for 5-second countdown (press Ctrl+C to cancel)

After reset, you can re-run the one-command deployment script to reinstall the system.

---

## 📋 Features

### 🎯 Intelligence Hub
- **AI-Powered News Filtering**: Automatically filter and analyze market news
- **Multi-Source Data Aggregation**: Collect data from various financial sources
- **Sentiment Analysis**: Real-time market sentiment tracking
- **Event Detection**: Identify high-impact market events

### 📊 Market Monitoring
- **Real-Time Data**: Multi-asset price monitoring
- **Watchlist Management**: Track your favorite symbols
- **Technical Indicators**: Built-in technical analysis tools
- **Alert System**: Customizable price and indicator alerts

### ⚡ Quantitative Engine
- **Factor System**: 100+ built-in quantitative factors
- **Backtesting**: Historical strategy testing with detailed metrics
- **Factor Screening**: Multi-factor stock screening
- **Performance Analytics**: Comprehensive performance reports

### 🤖 AI Agents
- **Autonomous Analysis**: AI agents analyze market data 24/7
- **Trading Signals**: Generate high-confidence trading signals
- **Risk Assessment**: Automatic risk evaluation
- **Report Generation**: Daily and weekly market reports

### 💰 Trading Management
- **Multi-Platform Support**: MT4, MT5, TradingView
- **EA Management**: Expert Advisor deployment and monitoring
- **Position Tracking**: Real-time position and P&L tracking
- **Risk Control**: Comprehensive risk management system

### 🔒 Security & Privacy
- **Bank-Grade Encryption**: End-to-end data encryption
- **JWT Authentication**: Secure token-based authentication
- **Rate Limiting**: API rate limiting and DDoS protection
- **Audit Logging**: Complete audit trail for all operations

---

## 🎓 Getting Started

### 1. Installation

#### Option A: One-Command Deployment (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh -o deploy.sh && sudo bash deploy.sh
```

#### Option B: Manual Installation
```bash
# Clone repository
git clone https://github.com/feelcharles/OpenFi.git
cd OpenFi

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/db_migrate.py

# Start server
python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686
```

### 2. First Login

1. Open browser and navigate to `http://YOUR_SERVER_IP:8686/app`
2. Login with default credentials: `admin` / `admin123`
3. **Change password immediately** when prompted
4. Complete initial setup

### 3. Configuration

#### API Keys Setup
1. Navigate to **System** → **Configuration**
2. Select `llm_config.yaml`
3. Add your API keys:
   ```yaml
   llm_providers:
     openai:
       api_key: "your-openai-api-key"
       model: "gpt-4"
     anthropic:
       api_key: "your-anthropic-api-key"
       model: "claude-3-opus"
   ```
4. Changes are **auto-saved** after 2 seconds

#### Data Sources
1. Select `fetch_sources.yaml`
2. Configure your data sources:
   ```yaml
   sources:
     - name: "Alpha Vantage"
       type: "market_data"
       api_key: "your-api-key"
       enabled: true
   ```

#### Push Notifications
1. Select `push_config.yaml`
2. Configure notification channels:
   ```yaml
   channels:
     telegram:
       enabled: true
       bot_token: "your-bot-token"
       chat_id: "your-chat-id"
   ```

---

## 📱 Web Interface Guide

### Dashboard Overview
- **System Status**: Real-time system health monitoring
- **Recent Signals**: Latest AI-generated trading signals
- **Market Overview**: Quick market snapshot
- **Performance Metrics**: Portfolio performance tracking

### Intelligence Module
- **News Feed**: AI-filtered news with relevance scores
- **Event Calendar**: Upcoming market events
- **Sentiment Dashboard**: Market sentiment indicators
- **Research Reports**: AI-generated market analysis

### Market Module
- **Watchlist**: Track multiple symbols
- **Charts**: Interactive price charts with indicators
- **Quotes**: Real-time price quotes
- **Screener**: Stock screening tools

### Quant Engine
- **Factor Library**: Browse and test factors
- **Backtesting**: Run historical strategy tests
- **Screening**: Multi-factor stock screening
- **Performance**: Analyze backtest results

### AI Agents
- **Agent Dashboard**: Monitor AI agent activities
- **Signal History**: Review generated signals
- **Agent Configuration**: Customize agent behavior
- **Performance Tracking**: Agent performance metrics

### Trading
- **Accounts**: Manage trading accounts
- **Positions**: View open positions
- **Orders**: Order management
- **History**: Trade history and P&L

### System
- **Configuration**: Edit system settings (auto-save enabled)
- **Users**: User management
- **Logs**: System logs and audit trail
- **Monitoring**: System performance metrics

---

## 🤖 AI Agents Capabilities

### 1. Market Analysis Agent
- **Daily Market Summary**: Comprehensive market overview
- **Sector Analysis**: Industry-specific insights
- **Trend Detection**: Identify market trends
- **Correlation Analysis**: Asset correlation tracking

### 2. News Analysis Agent
- **News Filtering**: Filter relevant news from noise
- **Sentiment Scoring**: Quantify news sentiment
- **Impact Assessment**: Evaluate news impact on markets
- **Event Extraction**: Extract key events from news

### 3. Trading Signal Agent
- **Signal Generation**: Generate trading signals
- **Confidence Scoring**: Assign confidence levels
- **Risk Assessment**: Evaluate signal risk
- **Entry/Exit Points**: Suggest optimal entry/exit

### 4. Risk Management Agent
- **Portfolio Risk**: Monitor portfolio risk metrics
- **Position Sizing**: Recommend position sizes
- **Stop Loss**: Suggest stop loss levels
- **Exposure Analysis**: Analyze market exposure

### 5. Report Generation Agent
- **Daily Reports**: Automated daily market reports
- **Weekly Summaries**: Weekly performance summaries
- **Custom Reports**: Generate custom analysis reports
- **Performance Attribution**: Analyze return sources

---

## 🔧 API Integration

### Authentication
```python
import requests

# Login
response = requests.post(
    "http://localhost:8686/api/v1/auth/login",
    json={"username": "admin", "password": "your-password"}
)
token = response.json()["access_token"]

# Use token in subsequent requests
headers = {"Authorization": f"Bearer {token}"}
```

### Fetch Market Data
```python
# Get system status
response = requests.get(
    "http://localhost:8686/api/v1/dashboard/system-status",
    headers=headers
)
print(response.json())

# Get recent signals
response = requests.get(
    "http://localhost:8686/api/v1/dashboard/signals?limit=10",
    headers=headers
)
signals = response.json()
```

### Bot Commands
```python
# Execute bot command
response = requests.post(
    "http://localhost:8686/api/v1/bot/command",
    headers=headers,
    json={"command": "/analyze AAPL"}
)
print(response.json()["response"])
```

### Configuration Management
```python
# Get configuration
response = requests.get(
    "http://localhost:8686/api/v1/config/llm_config.yaml",
    headers=headers
)
config = response.json()["content"]

# Update configuration (auto-saved)
response = requests.put(
    "http://localhost:8686/api/v1/config/llm_config.yaml",
    headers=headers,
    json={"content": updated_config}
)
```

---

## 🛡️ Live Trading Safety

### Risk Control Features
1. **Position Limits**: Maximum position size per symbol
2. **Daily Loss Limit**: Stop trading after daily loss threshold
3. **Drawdown Protection**: Automatic trading halt on drawdown
4. **Order Validation**: Pre-trade risk checks
5. **Emergency Stop**: One-click emergency stop button

### Best Practices
- ✅ **Start Small**: Begin with small position sizes
- ✅ **Paper Trading**: Test strategies in simulation first
- ✅ **Set Limits**: Always set stop loss and position limits
- ✅ **Monitor Closely**: Watch positions during market hours
- ✅ **Review Regularly**: Review performance and adjust

### Safety Checklist
- [ ] Configured position limits
- [ ] Set daily loss limits
- [ ] Tested strategy in backtest
- [ ] Verified API connections
- [ ] Enabled risk alerts
- [ ] Reviewed emergency procedures

---

## 📊 Quantitative Engine

### Factor System
- **Technical Factors**: Price, volume, momentum indicators
- **Fundamental Factors**: Financial ratios, earnings metrics
- **Sentiment Factors**: News sentiment, social media sentiment
- **Custom Factors**: Create your own factors

### Backtesting
```python
# Example backtest configuration
backtest_config = {
    "strategy": "momentum",
    "universe": ["AAPL", "GOOGL", "MSFT"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 100000,
    "factors": ["momentum_20", "volume_ratio"],
    "rebalance": "monthly"
}
```

### Performance Metrics
- **Returns**: Total return, annualized return, CAGR
- **Risk**: Volatility, max drawdown, Sharpe ratio
- **Trading**: Win rate, profit factor, average trade
- **Attribution**: Factor contribution analysis

---

## 📚 Documentation

### Core Documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Detailed deployment guide
- [API.md](API.md) - Complete API reference
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick command reference

### Technical Documentation
- [PYTHON_VERSION_UPGRADE.md](PYTHON_VERSION_UPGRADE.md) - Python 3.11+ upgrade details
- [PORT_CONFIGURATION.md](PORT_CONFIGURATION.md) - Port configuration guide
- [LIVE_TRADING_RISK_CONTROL.md](LIVE_TRADING_RISK_CONTROL.md) - Risk control documentation

### Additional Resources
- [DOCS_INDEX.md](DOCS_INDEX.md) - Complete documentation index
- [Examples](examples/) - Code examples and tutorials
- [Simulation](simulation/) - Testing and simulation tools

---

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python run_all_tests.py

# Run specific test
python simulation/test_complete_system.py

# Run web UI tests
python test_web_ui.py
```

### Test Coverage
- ✅ Core modules (8/8 passing)
- ✅ Web UI (7/7 passing)
- ✅ API endpoints (14/14 passing)
- ✅ Integration tests (2/2 passing)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
```bash
# Clone repository
git clone https://github.com/feelcharles/OpenFi.git
cd OpenFi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python run_all_tests.py
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLAlchemy for database ORM
- OpenAI & Anthropic for AI capabilities
- All contributors and users

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/feelcharles/OpenFi/issues)
- **Documentation**: [Full Documentation](DOCS_INDEX.md)
- **Examples**: [Code Examples](examples/)

---

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading involves risk. Past performance does not guarantee future results. Always do your own research and consult with financial advisors before making investment decisions.

---

**Made with ❤️ by the OpenFi Team**

**Version**: 1.0.0  
**Last Updated**: 2026-03-08
