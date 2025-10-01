# Connecting to Railway - SoundClassifiers v10
Updated August 9, 2025

## Overview

This guide covers how to connect to and manage the SoundClassifiers application deployed on Railway. Railway hosts the production instance at https://www.soundsgood.health.

## Prerequisites

### Install Railway CLI
```bash
npm install -g @railway/cli
```

### Verify Installation
```bash
railway --version
```

## Initial Setup

### 1. Login to Railway
```bash
railway login
```
This opens your browser for authentication.

### 2. Link to Project
Navigate to your project directory first:
```bash
cd /path/to/SoundClassifiers_v10
railway link
```

Select the SoundClassifiers project from the list.

### 3. Verify Connection
```bash
railway status
```

## Viewing Logs

### Real-Time Logs
```bash
railway logs --tail
```

### Last 100 Lines
```bash
railway logs --lines 100
```

### Filter by Time
```bash
# Last hour
railway logs --since 1h

# Last 24 hours  
railway logs --since 24h
```

## Environment Variables

### View Current Variables
```bash
railway variables
```

### Set a Variable
```bash
railway variables set KEY=value
```

### Set Multiple Variables
```bash
railway variables set FLASK_ENV=production DATA_ROOT=/app/backend/data
```

### Remove a Variable
```bash
railway variables remove KEY
```

## Database Access

### Connect to Database Shell
```bash
railway connect
```

### Run Database Commands
```bash
# Connect to Python shell with app context
railway run python

# In Python shell:
from flask_app import app
from backend.app.database import db

with app.app_context():
    # Query database
    from backend.app.core.models.user import User
    users = User.query.all()
    print(f"Total users: {len(users)}")
```

### Backup Database
```bash
# Export database
railway run python -c "
from flask_app import app
from backend.app.database import db
import json

with app.app_context():
    # Export your data
    # Add your backup logic here
"
```

## Deployment Management

### View Deployments
```bash
railway deployments list
```

### Trigger New Deployment
```bash
railway up
```

### Rollback to Previous
```bash
# List deployments with IDs
railway deployments list

# Rollback to specific deployment
railway deployments rollback [deployment-id]
```

## File System Access

### Execute Commands on Railway
```bash
# List files in production
railway run ls -la

# Check disk usage
railway run df -h

# View file contents
railway run cat backend/data/classes/global_registry.json
```

### Upload Files
```bash
# Not directly supported - use git push instead
git add .
git commit -m "Update files"
git push origin main
```

## Monitoring

### Check Application Health
```bash
# Via CLI
railway run curl http://localhost:$PORT/health

# Or directly
curl https://www.soundsgood.health/health
```

### Resource Usage
View in Railway dashboard:
1. Go to https://railway.app/dashboard
2. Select your project
3. View metrics tab

### Performance Monitoring
```bash
# Check memory usage
railway run ps aux

# Check Python processes
railway run ps aux | grep python
```

## Troubleshooting

### Common Commands for Debugging

#### Check if app is running
```bash
railway run ps aux | grep gunicorn
```

#### View error logs
```bash
railway logs --lines 500 | grep ERROR
```

#### Check environment
```bash
railway run python -c "import sys; print(sys.version)"
railway run pip list
```

#### Test specific endpoints
```bash
railway run python -c "
import requests
response = requests.get('http://localhost:5000/health')
print(response.status_code, response.text)
"
```

### Fix Common Issues

#### Application Won't Start
```bash
# Check logs for errors
railway logs --tail

# Verify environment variables
railway variables

# Check if port is set
railway variables | grep PORT
```

#### Database Connection Issues
```bash
# Check DATABASE_URL
railway variables | grep DATABASE_URL

# Test connection
railway run python -c "
from flask_app import app
print(app.config.get('SQLALCHEMY_DATABASE_URI'))
"
```

#### File/Directory Issues
```bash
# Check data directory exists
railway run ls -la backend/data

# Check permissions
railway run ls -la backend/data/sounds
```

## Maintenance Tasks

### Clear Temporary Files
```bash
railway run python -c "
import os
import shutil

# Clear temp directory
temp_dir = '/tmp/soundclassifiers'
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
    print('Cleared temp files')
"
```

### Reset Feature Cache
```bash
railway run python -c "
from backend.app.services.training_service import TrainingService
# Add cache reset logic
print('Feature cache reset')
"
```

### Database Maintenance
```bash
# Vacuum database (if using SQLite)
railway run python -c "
from flask_app import app
from backend.app.database import db

with app.app_context():
    db.engine.execute('VACUUM')
    print('Database vacuumed')
"
```

## Security Best Practices

### Viewing Sensitive Information
Never log sensitive data:
```bash
# DON'T DO THIS
railway variables | grep SECRET

# DO THIS INSTEAD (shows only variable names)
railway variables | grep SECRET | cut -d'=' -f1
```

### Rotating Secrets
```bash
# Generate new secret
NEW_SECRET=$(openssl rand -hex 32)

# Update on Railway
railway variables set SECRET_KEY=$NEW_SECRET

# Trigger redeployment
railway up
```

## Quick Reference

### Essential Commands
```bash
# Login
railway login

# Link project
railway link

# View logs
railway logs --tail

# Deploy
railway up

# View variables
railway variables

# Set variable
railway variables set KEY=value

# Run command
railway run [command]

# List deployments
railway deployments list

# Rollback
railway deployments rollback [id]

# Check status
railway status
```

### Useful Aliases
Add to your `.bashrc` or `.zshrc`:
```bash
alias rw='railway'
alias rwl='railway logs --tail'
alias rwv='railway variables'
alias rwu='railway up'
alias rws='railway status'
alias rwr='railway run'
```

## Getting Help

### Railway Documentation
- Official Docs: https://docs.railway.app
- CLI Reference: https://docs.railway.app/develop/cli

### Check Service Status
- Railway Status: https://status.railway.app
- Application Health: https://www.soundsgood.health/health

### Support Channels
- Railway Discord: https://discord.gg/railway
- GitHub Issues: For application-specific issues

---

*Last Updated: August 2025*
*Railway CLI Version: Latest*