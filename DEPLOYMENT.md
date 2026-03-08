# Deployment Guide

---

## Quick Deploy

### One-Command Installation
```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh | sudo bash
```

**Supported OS**: Ubuntu 20.04+, Debian 11+, CentOS 7+, RHEL 7+, Fedora 30+  
**Requirements**: 2 CPU cores, 2 GB RAM, Port 8686 open

**What it does**:
- Auto-detects OS and installs dependencies (Python 3.11+, PostgreSQL, Redis, Nginx)
- Configures database and services
- Creates default admin account (admin/admin123)
- Starts all services automatically

---

## First Login

1. **Access**: http://YOUR_SERVER_IP:8686/app
2. **Login**: admin / admin123
3. **Change Password**: Required on first login

---

## Service Management

### Check Status
```bash
systemctl status openfi
```

### View Logs
```bash
journalctl -u openfi -f
```

### Restart Service
```bash
sudo systemctl restart openfi
```

### Stop Service
```bash
sudo systemctl stop openfi
```

---

## Manual Installation

### 1. Install Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib redis-server nginx git

# CentOS/RHEL
sudo yum install -y python311 python311-devel \
    postgresql-server postgresql-contrib redis nginx git
```

### 2. Clone Repository
```bash
git clone https://github.com/feelcharles/OpenFi.git
cd OpenFi
```

### 3. Setup Python Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Database
```bash
sudo -u postgres psql -c "CREATE DATABASE openfi;"
sudo -u postgres psql -c "CREATE USER openfi WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE openfi TO openfi;"
```

### 5. Run Migrations
```bash
alembic upgrade head
```

### 6. Start Application
```bash
python system_core/main.py
```

---

## Configuration

### Environment Variables
Create `.env` file:
```bash
DATABASE_URL=postgresql://openfi:password@localhost/openfi
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
```

### Port Configuration
Default port: **8686**

To change port, edit `system_core/web_backend/app.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8686)
```

---

## Firewall Configuration

### Ubuntu/Debian
```bash
sudo ufw allow 8686/tcp
sudo ufw allow 80/tcp
sudo ufw reload
```

### CentOS/RHEL
```bash
sudo firewall-cmd --permanent --add-port=8686/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload
```

---

## Nginx Configuration (Optional)

To use port 80 instead of 8686:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8686;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Troubleshooting

### Service Won't Start
```bash
# Check logs
journalctl -u openfi -n 50

# Check if port is in use
sudo lsof -i :8686
```

### Database Connection Error
```bash
# Check PostgreSQL status
systemctl status postgresql

# Test connection
psql -U openfi -d openfi -h localhost
```

### Permission Issues
```bash
# Fix file permissions
sudo chown -R openfi:openfi /opt/openfi
```

---

## Update

### Update to Latest Version
```bash
cd /opt/openfi
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart openfi
```

---

## Uninstall

### Stop and Remove Service
```bash
sudo systemctl stop openfi
sudo systemctl disable openfi
sudo rm /etc/systemd/system/openfi.service
```

### Remove Files
```bash
sudo rm -rf /opt/openfi
```

### Remove Database (Optional)
```bash
sudo -u postgres psql -c "DROP DATABASE openfi;"
sudo -u postgres psql -c "DROP USER openfi;"
```

---

**Last Updated**: 2026-03-08
