# Railway Deployment Guide - SoundClassifiers v10
Updated August 9, 2025
## Complete Guide for Current Code Structure

## Overview
This comprehensive guide covers deploying the SoundClassifiers v10 application to Railway. The application is currently deployed at https://www.soundsgood.health and includes:
- Flask backend with REST API for audio processing and classification
- Web frontend interface
- Support for multiple ML models (CNN, Random Forest, SVM, Ensemble)
- C# client integration via custom API

## Current Deployment Configuration

### Configuration Files
- **`railway.json`**: Configures Nixpacks builder with gunicorn deployment
- **`Procfile`**: Specifies `web: gunicorn wsgi:app` as the start command
- **`wsgi.py`**: Entry point for the WSGI server
- **`requirements.txt`**: Python dependencies

## Prerequisites

### Required Tools
1. **Railway CLI**: Install with `npm install -g @railway/cli`
2. **Git**: For version control and deployment
3. **Railway Account**: Sign up at https://railway.app
4. **Access**: Ensure you have access to the Railway project

### Local Development Requirements
- Python 3.8+ with pip
- Node.js and npm (for Railway CLI)
- .NET SDK 6+ (for C# client testing)

## Deployment Methods

### Method 1: GitHub Integration (Recommended)
1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Your descriptive commit message"
   git push origin main
   ```

2. **Automatic Deployment**
   - If configured, Railway automatically deploys when you push to main
   - Monitor deployment at https://railway.app/dashboard

### Method 2: Railway CLI Deployment
1. **Login to Railway**
   ```bash
   railway login
   ```

2. **Link to Project** (first time only)
   ```bash
   railway link
   ```

3. **Deploy Current Directory**
   ```bash
   railway up
   ```

4. **Monitor Logs**
   ```bash
   railway logs
   ```

### Method 3: Railway Dashboard
1. Navigate to https://railway.app/dashboard
2. Select your project
3. Click "Deploy" → "Deploy from GitHub"
4. Select branch and commit
5. Confirm deployment

## Environment Variables

### Required Variables
Configure these in Railway dashboard under Settings → Variables:

```bash
# Flask Configuration
FLASK_APP=flask_app.py
FLASK_ENV=production
SECRET_KEY=your_secure_secret_key_here

# Database
DATABASE_URL=your_database_url_here

# Data Storage
DATA_ROOT=/app/backend/data

# Optional: Model Configuration
DEFAULT_MODEL_TYPE=CNN
ENABLE_RF_MODELS=true
ENABLE_SVM_MODELS=true
ENABLE_ENSEMBLE_MODELS=true
```

### Setting Variables via CLI
```bash
railway variables set FLASK_ENV=production
railway variables set SECRET_KEY="your_secure_key"
railway variables set DATA_ROOT=/app/backend/data
```

## Application Structure

### Key Directories
```
SoundClassifiers_v10/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── ml/           # ML models (CNN, RF, SVM)
│   │   ├── routes/       # Flask routes
│   │   └── services/     # Business logic
│   └── data/            # Data storage
├── frontend/
│   ├── static/          # CSS, JS, images
│   └── templates/       # HTML templates
├── flask_app.py         # Main Flask application
├── wsgi.py             # WSGI entry point
├── run.py              # Local development runner
├── requirements.txt     # Python dependencies
├── railway.json        # Railway configuration
└── Procfile           # Deployment commands
```

### Model Types Available
- **CNN (Convolutional Neural Network)**: Default, best for complex patterns
- **Random Forest**: Tree-based ensemble, good for interpretability
- **SVM (Support Vector Machine)**: Effective for high-dimensional data
- **Ensemble**: Combines multiple models for better accuracy

## Step-by-Step Deployment Process

### 1. Pre-Deployment Checklist
- [ ] All changes committed to git
- [ ] Tests passing locally
- [ ] requirements.txt updated with new dependencies
- [ ] Environment variables documented
- [ ] Database migrations prepared (if needed)

### 2. Deploy Changes
```bash
# Check current status
git status

# Add and commit changes
git add .
git commit -m "Deploy: [feature description]"

# Push to GitHub (triggers auto-deploy if configured)
git push origin main

# OR deploy directly via CLI
railway up
```

### 3. Post-Deployment Verification

#### Check Application Health
1. Visit https://www.soundsgood.health
2. Verify login functionality
3. Test key features:
   - Recording upload
   - Model training (all types)
   - Inference/prediction
   - Developer downloads page

#### API Endpoint Testing
```bash
# Test API health
curl https://www.soundsgood.health/api/health

# Test custom speech API (for C# client)
curl https://www.soundsgood.health/api/custom_speech/status
```

#### Monitor Logs
```bash
# View real-time logs
railway logs --tail

# View last 100 lines
railway logs --lines 100
```

## Database Management

### Initial Setup
```bash
# Connect to Railway shell
railway run python

# Initialize database
from flask_app import app
from backend.app.database import db
with app.app_context():
    db.create_all()
```

### Migrations
```bash
# Run migrations if using Flask-Migrate
railway run flask db upgrade
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Deployment Fails
- **Check logs**: `railway logs`
- **Verify requirements.txt**: Ensure all dependencies are listed
- **Check Python version**: Railway uses Python 3.8+ by default
- **Syntax errors**: Run `python -m py_compile flask_app.py` locally

#### 2. Application Crashes
- **Memory issues**: Check if app exceeds Railway limits
- **Missing env vars**: Verify all required variables are set
- **Port binding**: Ensure app uses `PORT` env variable

#### 3. Models Not Working
- **Data directory**: Verify DATA_ROOT is correctly set
- **File permissions**: Check Railway has write access
- **Model files**: Ensure trained models are present

#### 4. API Connection Issues
- **CORS settings**: Check Flask CORS configuration
- **SSL/HTTPS**: Ensure clients use HTTPS URLs
- **Authentication**: Verify API keys/tokens are valid

### Debug Commands
```bash
# Check environment variables
railway variables

# Run shell in Railway environment
railway shell

# Test specific command
railway run python -c "from flask_app import app; print(app.config)"
```

## Rollback Procedure

### Via Dashboard
1. Go to https://railway.app/dashboard
2. Select your project
3. Navigate to "Deployments"
4. Find previous working deployment
5. Click "Rollback to this deployment"

### Via CLI
```bash
# List recent deployments
railway deployments list

# Rollback to specific deployment
railway deployments rollback [deployment-id]
```

## Performance Optimization

### Recommended Settings
1. **Workers**: Gunicorn uses multiple workers
2. **Memory**: Monitor usage in Railway dashboard
3. **Caching**: Enable Redis for session/cache storage
4. **Static files**: Consider CDN for frontend assets

### Scaling
```bash
# Increase replicas (if on paid plan)
railway scale --replicas 2
```

## Security Best Practices

1. **Never commit secrets**: Use environment variables
2. **HTTPS only**: Railway provides SSL by default
3. **Update dependencies**: Regular security updates
4. **Access control**: Implement proper authentication
5. **Data encryption**: Encrypt sensitive data at rest

## Monitoring and Maintenance

### Health Checks
- Set up monitoring at https://www.soundsgood.health/health
- Use external monitoring services (UptimeRobot, Pingdom)
- Configure alerts for downtime

### Regular Maintenance
- Review logs weekly
- Update dependencies monthly
- Backup data regularly
- Monitor disk usage

## C# Client Integration

### API Endpoints
The deployed application provides custom speech API at:
- Base URL: `https://www.soundsgood.health`
- API Path: `/api/custom_speech/recognize`

### Testing C# Client
```csharp
var client = new SoundClassifiersClient(
    "https://www.soundsgood.health",
    "your-model-id"
);
```

## Support Resources

### Railway
- Documentation: https://docs.railway.app
- Status Page: https://status.railway.app
- Community: https://discord.gg/railway
- Dashboard: https://railway.app/dashboard

### Application
- Logs: https://railway.app/project/[project-id]/logs
- Metrics: Available in Railway dashboard
- Health: https://www.soundsgood.health/health

## Quick Reference Commands

```bash
# Deploy
railway up

# View logs
railway logs --tail

# Set variable
railway variables set KEY=value

# Connect to shell
railway shell

# Run command
railway run [command]

# Check status
railway status

# List deployments
railway deployments list

# Rollback
railway deployments rollback [id]
```

## Contact and Support

For deployment issues:
1. Check Railway status page
2. Review application logs
3. Verify environment variables
4. Test locally with production settings

For application issues:
1. Check error logs in Railway dashboard
2. Verify all services are running
3. Test API endpoints manually
4. Review recent code changes

---

Last Updated: August 2025
Version: SoundClassifiers v10
Deployment: Railway (https://www.soundsgood.health)