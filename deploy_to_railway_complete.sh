#!/bin/bash
#
# Complete Railway Deployment Script for SoundClassifiers v10
# This script deploys the ENTIRE codebase including all data files to Railway
# Created: August 9, 2025
#
# IMPORTANT: This will COMPLETELY REPLACE the current Railway deployment
# Make sure you have:
# 1. Railway CLI installed (npm install -g @railway/cli)
# 2. Logged into Railway (railway login)
# 3. Linked to your project (railway link)
#

set -e  # Exit on any error

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Railway Complete Deployment Script${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Function to check if Railway CLI is installed
check_railway_cli() {
    if ! command -v railway &> /dev/null; then
        echo -e "${RED}Railway CLI is not installed!${NC}"
        echo "Please install it with: npm install -g @railway/cli"
        exit 1
    fi
    echo -e "${GREEN}✓ Railway CLI found${NC}"
}

# Function to check Railway login status
check_railway_login() {
    echo "Checking Railway login status..."
    if ! railway whoami &> /dev/null; then
        echo -e "${YELLOW}Not logged into Railway. Please login:${NC}"
        railway login
    else
        echo -e "${GREEN}✓ Logged into Railway${NC}"
    fi
}

# Function to check if project is linked
check_project_link() {
    echo "Checking project link..."
    if ! railway status &> /dev/null; then
        echo -e "${YELLOW}Project not linked. Attempting to link...${NC}"
        railway link
    else
        echo -e "${GREEN}✓ Project is linked${NC}"
    fi
}

# Function to display current status
display_status() {
    echo ""
    echo -e "${YELLOW}Current Status:${NC}"
    echo "----------------------------------------"
    git status --short
    echo "----------------------------------------"
    echo ""
}

# Function to create deployment confirmation
confirm_deployment() {
    echo -e "${YELLOW}⚠️  WARNING: This will COMPLETELY REPLACE the Railway production deployment!${NC}"
    echo ""
    echo "This deployment will include:"
    echo "  • All Python backend code"
    echo "  • All frontend templates and static files"
    echo "  • All data files (sounds, models, features, metadata)"
    echo "  • All configuration files"
    echo ""
    echo -e "${YELLOW}Are you absolutely sure you want to continue? (yes/no)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
}

# Function to prepare deployment
prepare_deployment() {
    echo ""
    echo -e "${GREEN}Preparing deployment...${NC}"
    
    # Check for uncommitted changes
    if [[ -n $(git status -s) ]]; then
        echo -e "${YELLOW}You have uncommitted changes. Committing them now...${NC}"
        git add .
        echo "Enter commit message:"
        read -r commit_message
        git commit -m "$commit_message" || true
    fi
    
    echo -e "${GREEN}✓ Repository is ready for deployment${NC}"
}

# Function to set environment variables
set_environment_variables() {
    echo ""
    echo -e "${GREEN}Setting environment variables...${NC}"
    
    # Set production environment variables
    railway variables set FLASK_ENV=production
    railway variables set FLASK_APP=flask_app.py
    railway variables set DATA_ROOT=/app/backend/data
    railway variables set DEFAULT_MODEL_TYPE=CNN
    railway variables set ENABLE_RF_MODELS=true
    railway variables set ENABLE_SVM_MODELS=true
    railway variables set ENABLE_ENSEMBLE_MODELS=true
    
    echo -e "${GREEN}✓ Environment variables set${NC}"
}

# Function to deploy to Railway
deploy_to_railway() {
    echo ""
    echo -e "${GREEN}Starting deployment to Railway...${NC}"
    echo "This may take several minutes..."
    echo ""
    
    # Deploy using Railway CLI
    railway up --detach
    
    echo ""
    echo -e "${GREEN}✓ Deployment initiated${NC}"
}

# Function to monitor deployment
monitor_deployment() {
    echo ""
    echo -e "${GREEN}Monitoring deployment...${NC}"
    echo "Press Ctrl+C to stop monitoring (deployment will continue)"
    echo ""
    
    # Show logs
    railway logs --tail
}

# Function to verify deployment
verify_deployment() {
    echo ""
    echo -e "${GREEN}Verifying deployment...${NC}"
    
    # Get the deployment URL
    DEPLOY_URL=$(railway open --dry-run 2>/dev/null | grep -o 'https://[^ ]*' || echo "https://www.soundsgood.health")
    
    echo "Deployment URL: $DEPLOY_URL"
    echo ""
    echo "Please verify the following:"
    echo "  1. Visit $DEPLOY_URL"
    echo "  2. Test login functionality"
    echo "  3. Check that all pages load correctly"
    echo "  4. Test API endpoints:"
    echo "     - $DEPLOY_URL/api/health"
    echo "     - $DEPLOY_URL/api/custom_speech/status"
    echo ""
}

# Function to show post-deployment info
post_deployment_info() {
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Useful commands:"
    echo "  • View logs:        railway logs --tail"
    echo "  • Open app:         railway open"
    echo "  • Check status:     railway status"
    echo "  • View variables:   railway variables"
    echo "  • Rollback:         railway deployments list && railway deployments rollback [id]"
    echo ""
    echo "Dashboard: https://railway.app/dashboard"
    echo ""
}

# Main deployment flow
main() {
    echo "Starting complete Railway deployment process..."
    echo ""
    
    # Pre-flight checks
    check_railway_cli
    check_railway_login
    check_project_link
    
    # Display current status
    display_status
    
    # Confirm deployment
    confirm_deployment
    
    # Prepare for deployment
    prepare_deployment
    
    # Set environment variables
    set_environment_variables
    
    # Deploy to Railway
    deploy_to_railway
    
    # Show deployment info
    post_deployment_info
    
    # Option to monitor
    echo -e "${YELLOW}Would you like to monitor the deployment logs? (y/n)${NC}"
    read -r monitor_response
    if [[ "$monitor_response" =~ ^[Yy]$ ]]; then
        monitor_deployment
    fi
    
    # Verify deployment
    verify_deployment
}

# Run main function
main