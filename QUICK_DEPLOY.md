# Quick Reference

---

## 🚀 One-Command Deployment

```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh | sudo bash
```

**What it does**:
- Auto-detects OS (Ubuntu/Debian/CentOS/RHEL/Fedora)
- Installs Python 3.11+, PostgreSQL, Redis, Nginx
- Creates default admin account (admin/admin123)
- Starts all services automatically

**Access**: http://YOUR_SERVER_IP:8686/app

---

## 📋 Common Commands

### Service Management
```bash
# Start server
systemctl start openfi

# Stop server
systemctl stop openfi

# Restart server
systemctl restart openfi

# Check status
systemctl status openfi

# View live logs
journalctl -u openfi -f

# View last 50 log entries
journalctl -u openfi -n 50
```

### System Reset
⚠️ **Dangerous Operation**: Deletes all data, configuration, and logs!

```bash
# Reset entire system
sudo bash /opt/openfi/scripts/reset_system.sh
```

**Reset process**:
1. Enter `YES` (uppercase) for first confirmation
2. Enter `RESET` (uppercase) for second confirmation
3. Enter administrator password
4. Wait 5 seconds (or press Ctrl+C to cancel)

**What gets deleted**:
- PostgreSQL database and user
- Redis cache
- All log files
- Configuration files (.env, JWT keys)
- Backup files
- Python cache

**After reset**: Re-run deployment script to reinstall

### Testing
```bash
# Run all tests
python run_all_tests.py

# Module tests
python test_system_modules.py

# Workflow tests
python test_workflow.py

# Integration tests
python test_integration.py
```

### Web Server (Manual)
```bash
# Start server
python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686

# Check health
curl http://localhost:8686/health

# Access dashboard
open http://localhost:8686/app
```

---

## 🌐 Web Endpoints

```
http://localhost:8686/app           # Main dashboard
http://localhost:8686/health        # Health check
http://localhost:8686/docs          # API documentation (Swagger)
http://localhost:8686/redoc         # API documentation (ReDoc)
http://localhost:8686/api/v1/...    # API endpoints
```

---

## ⚙️ Configuration Files

```
config/llm_config.yaml              # AI/LLM settings
config/fetch_sources.yaml           # Data sources
config/factor_config.yaml           # Quantitative factors
config/ea_config.yaml               # Expert Advisors
config/push_config.yaml             # Push notifications
config/security_config.yaml         # Security settings
config/alerting_config.yaml         # Alert rules
```

**Edit via Web**: http://localhost:8686/app#/system

---

## 🔐 Default Credentials

```
Username: admin
Password: admin123
```

⚠️ **Must change password on first login**

---

## 📁 Key Directories

```
system_core/        # Core application code
config/             # Configuration files
tests/              # Unit tests
examples/           # Code examples
alembic/            # Database migrations
ea/                 # Expert Advisors
logs/               # Log files
```

---

## 🐛 Troubleshooting

### Check Python Version
```bash
python3 --version  # Should be 3.11+
```

### Port Already in Use
```bash
sudo lsof -i :8686
sudo kill -9 <PID>
```

### Database Connection Error
```bash
systemctl status postgresql
psql -U openfi -d openfi -h localhost
```

### View Logs
```bash
# Service logs
journalctl -u openfi -n 50

# Application logs
tail -f logs/openfi.log
```

### Restart Services
```bash
sudo systemctl restart openfi
sudo systemctl restart postgresql
sudo systemctl restart redis
```

---

## � Update

```bash
cd /opt/openfi
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart openfi
```

---

## 📊 Bot Commands

Available in Telegram/Discord:

```
/ea_refresh         # Scan and update EA list
/ea_test <name>     # Test specific EA
/ea_list            # List all EAs
/status             # System status
/signals            # Recent signals
/positions          # Open positions
/help               # Show help
```

---

## 🔥 Firewall

### Ubuntu/Debian
```bash
sudo ufw allow 8686/tcp
sudo ufw reload
```

### CentOS/RHEL
```bash
sudo firewall-cmd --permanent --add-port=8686/tcp
sudo firewall-cmd --reload
```

---

## 📞 Quick Help

- **Documentation**: http://localhost:8686/docs
- **GitHub**: https://github.com/feelcharles/OpenFi
- **Issues**: https://github.com/feelcharles/OpenFi/issues

---

**Last Updated**: 2026-03-08  
**Python**: 3.11+  
**Port**: 8686  
**Status**: ✅ Production Ready
