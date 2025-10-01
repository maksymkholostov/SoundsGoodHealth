#!/bin/bash
# railway_deploy.sh - Deployment script for SoundClassifiers v10 to Railway

# Make script executable with: chmod +x railway_deploy.sh

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Installing..."
    npm i -g @railway/cli
fi

# Login to Railway if not already logged in
railway login

# Ask user if they want to create a new project or use existing
echo "Do you want to create a new Railway project or use an existing one?"
echo "1) Create new project"
echo "2) Use existing project"
read -p "Enter your choice (1/2): " choice

if [ "$choice" = "1" ]; then
    echo "Creating new Railway project..."
    railway init
else
    echo "Linking to existing Railway project..."
    railway link
fi

# Set environment variables
echo "Setting up environment variables..."
railway vars set FLASK_APP=flask_app.py
railway vars set FLASK_ENV=production

# Generate a random secret key
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(24))")
railway vars set SECRET_KEY="$SECRET_KEY"

# Prompt for database URL or use default SQLite
read -p "Enter database URL (leave blank for SQLite): " db_url
if [ -z "$db_url" ]; then
    railway vars set DATABASE_URL="sqlite:///app.db"
else
    railway vars set DATABASE_URL="$db_url"
fi

# Deploy the application
echo "Deploying application to Railway..."
railway up

# Get the deployment URL
echo "Getting deployment URL..."
DEPLOY_URL=$(railway domain)

echo "==============================================="
echo "Deployment complete!"
echo "Your application is available at: $DEPLOY_URL"
echo "==============================================="

# Ask if user wants to open the application in the browser
read -p "Do you want to open the application in your browser? (y/n): " open_browser
if [ "$open_browser" = "y" ] || [ "$open_browser" = "Y" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "$DEPLOY_URL"
    elif command -v open &> /dev/null; then
        open "$DEPLOY_URL"
    elif command -v start &> /dev/null; then
        start "$DEPLOY_URL"
    else
        echo "Could not open browser automatically. Please visit: $DEPLOY_URL"
    fi
fi

echo "Done!" 