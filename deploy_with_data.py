#!/usr/bin/env python3
"""
Complete Railway Deployment with Data Files
This script ensures ALL data files are included in the deployment
Created: August 9, 2025

Usage: python deploy_with_data.py
"""

import os
import sys
import subprocess
import json
from pathlib import Path
import shutil
from datetime import datetime

# Color codes for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def print_colored(message, color=NC):
    """Print colored message to terminal"""
    print(f"{color}{message}{NC}")

def check_railway_cli():
    """Check if Railway CLI is installed"""
    try:
        result = subprocess.run(['railway', '--version'], 
                              capture_output=True, text=True, check=True)
        print_colored("✓ Railway CLI found", GREEN)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_colored("✗ Railway CLI not found!", RED)
        print("Please install with: npm install -g @railway/cli")
        return False

def check_railway_auth():
    """Check if logged into Railway"""
    try:
        result = subprocess.run(['railway', 'whoami'], 
                              capture_output=True, text=True, check=True)
        print_colored("✓ Logged into Railway", GREEN)
        return True
    except subprocess.CalledProcessError:
        print_colored("Not logged into Railway. Logging in...", YELLOW)
        subprocess.run(['railway', 'login'])
        return True

def check_project_link():
    """Check if project is linked"""
    try:
        result = subprocess.run(['railway', 'status'], 
                              capture_output=True, text=True, check=True)
        print_colored("✓ Project is linked", GREEN)
        return True
    except subprocess.CalledProcessError:
        print_colored("Linking to Railway project...", YELLOW)
        subprocess.run(['railway', 'link'])
        return True

def analyze_data_files():
    """Analyze data files to be deployed"""
    data_dir = Path('backend/data')
    
    if not data_dir.exists():
        print_colored("Warning: backend/data directory not found!", YELLOW)
        return {}
    
    stats = {
        'sounds': {'count': 0, 'size': 0},
        'models': {'count': 0, 'size': 0},
        'features': {'count': 0, 'size': 0},
        'metadata': {'count': 0, 'size': 0},
        'total': {'count': 0, 'size': 0}
    }
    
    print("\nAnalyzing data files...")
    
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            file_path = Path(root) / file
            file_size = file_path.stat().st_size
            
            # Categorize files
            if 'sounds' in str(file_path):
                stats['sounds']['count'] += 1
                stats['sounds']['size'] += file_size
            elif 'models' in str(file_path):
                stats['models']['count'] += 1
                stats['models']['size'] += file_size
            elif 'features' in str(file_path):
                stats['features']['count'] += 1
                stats['features']['size'] += file_size
            elif 'metadata' in str(file_path):
                stats['metadata']['count'] += 1
                stats['metadata']['size'] += file_size
            
            stats['total']['count'] += 1
            stats['total']['size'] += file_size
    
    # Display statistics
    print("\nData Files Summary:")
    print("-" * 50)
    for category, data in stats.items():
        if category != 'total':
            size_mb = data['size'] / (1024 * 1024)
            print(f"  {category.capitalize():10} {data['count']:6} files  {size_mb:8.2f} MB")
    print("-" * 50)
    total_mb = stats['total']['size'] / (1024 * 1024)
    print(f"  {'TOTAL':10} {stats['total']['count']:6} files  {total_mb:8.2f} MB")
    print()
    
    return stats

def check_gitignore():
    """Ensure data files are not ignored"""
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        return
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    # Check for data exclusions
    data_patterns = ['backend/data/', '*.npz', '*.pkl', '*.h5', '*.wav']
    ignored_patterns = []
    
    for pattern in data_patterns:
        if pattern in content and not pattern.startswith('!'):
            ignored_patterns.append(pattern)
    
    if ignored_patterns:
        print_colored("Warning: Some data files might be ignored by git!", YELLOW)
        print("The following patterns in .gitignore might exclude data files:")
        for pattern in ignored_patterns:
            print(f"  - {pattern}")
        print("\nConsider adding exceptions with '!' prefix if needed.")
        print()

def create_deployment_config():
    """Create or update Railway configuration"""
    railway_json = {
        "build": {
            "builder": "NIXPACKS",
            "buildCommand": "pip install -r requirements.txt"
        },
        "deploy": {
            "startCommand": "gunicorn wsgi:app",
            "restartPolicyType": "ON_FAILURE",
            "restartPolicyMaxRetries": 10
        }
    }
    
    with open('railway.json', 'w') as f:
        json.dump(railway_json, f, indent=2)
    
    print_colored("✓ Railway configuration updated", GREEN)

def commit_changes():
    """Commit any uncommitted changes"""
    # Check for uncommitted changes
    result = subprocess.run(['git', 'status', '--porcelain'], 
                          capture_output=True, text=True)
    
    if result.stdout.strip():
        print_colored("Uncommitted changes detected. Committing...", YELLOW)
        
        # Add all changes
        subprocess.run(['git', 'add', '.'])
        
        # Create commit message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Deploy to Railway: Complete deployment with data files - {timestamp}"
        
        # Commit
        subprocess.run(['git', 'commit', '-m', commit_msg])
        print_colored("✓ Changes committed", GREEN)
    else:
        print_colored("✓ No uncommitted changes", GREEN)

def deploy_to_railway():
    """Deploy to Railway"""
    print()
    print_colored("=" * 60, GREEN)
    print_colored("Starting Railway Deployment", GREEN)
    print_colored("=" * 60, GREEN)
    print()
    
    # Set environment variables
    print("Setting environment variables...")
    env_vars = {
        'FLASK_ENV': 'production',
        'FLASK_APP': 'flask_app.py',
        'DATA_ROOT': '/app/backend/data',
        'DEFAULT_MODEL_TYPE': 'CNN',
        'ENABLE_RF_MODELS': 'true',
        'ENABLE_SVM_MODELS': 'true',
        'ENABLE_ENSEMBLE_MODELS': 'true'
    }
    
    for key, value in env_vars.items():
        subprocess.run(['railway', 'variables', 'set', f'{key}={value}'])
    
    print_colored("✓ Environment variables set", GREEN)
    print()
    
    # Deploy
    print("Deploying to Railway...")
    print("This will upload ALL files including data files.")
    print("This may take several minutes depending on data size...")
    print()
    
    try:
        # Use railway up to deploy everything
        result = subprocess.run(['railway', 'up', '--detach'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print_colored("✓ Deployment initiated successfully!", GREEN)
            print()
            
            # Extract deployment URL if available
            if "Deployment live at" in result.stdout:
                url = result.stdout.split("Deployment live at")[1].strip()
                print(f"Deployment URL: {url}")
        else:
            print_colored("Deployment may have issues. Check logs:", YELLOW)
            print(result.stderr)
    
    except Exception as e:
        print_colored(f"Error during deployment: {e}", RED)
        return False
    
    return True

def verify_deployment():
    """Provide verification steps"""
    print()
    print_colored("=" * 60, GREEN)
    print_colored("Deployment Verification", GREEN)
    print_colored("=" * 60, GREEN)
    print()
    
    print("Please verify your deployment:")
    print()
    print("1. Check deployment status:")
    print("   railway status")
    print()
    print("2. View deployment logs:")
    print("   railway logs --tail")
    print()
    print("3. Open your application:")
    print("   railway open")
    print()
    print("4. Test API endpoints:")
    print("   • https://www.soundsgood.health/api/health")
    print("   • https://www.soundsgood.health/api/custom_speech/status")
    print()
    print("5. Verify data files are accessible:")
    print("   • Login to the application")
    print("   • Check that recordings load")
    print("   • Test model training")
    print("   • Test inference/prediction")
    print()
    
    print_colored("If there are issues, you can rollback:", YELLOW)
    print("   railway deployments list")
    print("   railway deployments rollback [deployment-id]")
    print()

def main():
    """Main deployment process"""
    print_colored("=" * 60, GREEN)
    print_colored("Railway Complete Deployment Script", GREEN)
    print_colored("Including ALL Data Files", GREEN)
    print_colored("=" * 60, GREEN)
    print()
    
    # Pre-flight checks
    if not check_railway_cli():
        sys.exit(1)
    
    if not check_railway_auth():
        sys.exit(1)
    
    if not check_project_link():
        sys.exit(1)
    
    # Analyze what will be deployed
    stats = analyze_data_files()
    
    if stats['total']['size'] > 500 * 1024 * 1024:  # 500 MB
        print_colored("Warning: Large data size detected!", YELLOW)
        print("Railway has deployment size limits on free tier.")
        print("Consider using Railway's volume storage for large data files.")
        print()
    
    # Check gitignore
    check_gitignore()
    
    # Confirm deployment
    print_colored("⚠️  This will COMPLETELY REPLACE the Railway production!", YELLOW)
    print_colored("⚠️  All existing data will be overwritten!", YELLOW)
    print()
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Deployment cancelled.")
        sys.exit(0)
    
    # Prepare deployment
    create_deployment_config()
    commit_changes()
    
    # Deploy
    if deploy_to_railway():
        verify_deployment()
        print_colored("Deployment complete! 🚀", GREEN)
    else:
        print_colored("Deployment failed. Check logs for details.", RED)
        sys.exit(1)

if __name__ == "__main__":
    main()