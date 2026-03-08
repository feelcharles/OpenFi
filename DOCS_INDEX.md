# OpenFi Documentation Index

Complete documentation for OpenFi - Your Intelligent Trading Copilot

---

## Getting Started

- **[README.md](README.md)** - Main documentation (English)
- **[README_CN.md](README_CN.md)** - 主要文档（中文）
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick command reference

---

## Deployment

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[quick_deploy.sh](quick_deploy.sh)** - One-command deployment script

**Quick Deploy**:
```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh | sudo bash
```

---

## API Documentation

- **[API.md](API.md)** - API reference
- **Swagger UI**: http://localhost:8686/docs
- **ReDoc**: http://localhost:8686/redoc

---

## Configuration

Configuration files in `config/` directory:
- `llm_config.yaml` - AI/LLM settings
- `fetch_sources.yaml` - Data sources
- `ea_config.yaml` - Expert Advisors
- `factor_config.yaml` - Quantitative factors
- `push_config.yaml` - Notifications
- `security_config.yaml` - Security settings
- `alerting_config.yaml` - Alert rules

**Edit via Web**: http://localhost:8686/app#/system

---

## Features

### AI & Agents
- Market analysis and daily summaries
- News filtering and sentiment analysis
- Trading signal generation
- Risk management and monitoring
- Automated report generation

### Quantitative Engine
- 100+ built-in factors
- Custom factor creation
- Multi-factor screening
- Historical backtesting
- Performance metrics

### Trading
- MT4/MT5 integration
- TradingView support
- EA deployment
- Position tracking
- Risk control

---

## Testing

```bash
# Run all tests
python run_all_tests.py

# Unit tests
pytest tests/
```

---

## Project Structure

```
OpenFi/
├── system_core/          # Core modules
│   ├── ai_engine/       # AI processing
│   ├── auth/            # Authentication
│   ├── backtest/        # Backtesting
│   ├── factor_system/   # Factors
│   ├── execution_engine/# Trading
│   └── web_backend/     # Web API
├── config/              # Configuration
├── tests/               # Unit tests
└── examples/            # Code examples
```

---

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Read the full documentation
- **Examples**: Check `examples/` directory

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

**Disclaimer**: This software is for educational and research purposes. Trading involves risk. Always do your own research and consult with financial advisors.

---

**Last Updated**: 2026-03-08  
**Version**: 1.0.0
