# Railway Volume Setup for Persistent Data

## Steps to Set Up Persistent Storage

### 1. Via Railway Dashboard (Recommended)

1. Go to your Railway project dashboard at https://railway.app
2. Select your production environment
3. Click on your service (the Flask app)
4. Go to the "Settings" tab
5. Scroll down to "Volumes"
6. Click "Add Volume"
7. Configure the volume:
   - **Mount Path**: `/app/backend/data`
   - **Size**: 10GB (or more as needed)
8. Click "Create Volume"
9. Redeploy your service

### 2. Via Railway CLI (Alternative)

Run these commands in your terminal:

```bash
# Link to your service first
railway link

# Select your project and service when prompted
# Then create and attach the volume
railway volume add --mount /app/backend/data

# Check volume status
railway volume
```

### 3. Update Application Code

The application needs to be updated to use the mounted volume path. Create this initialization script:

```python
# backend/utils/volume_init.py
import os
from pathlib import Path

def init_data_volume():
    """Initialize data volume structure if it doesn't exist"""
    data_root = Path('/app/backend/data')
    
    # Create directory structure if it doesn't exist
    directories = [
        'sounds/gold',
        'sounds/augmented',
        'features',
        'models',
        'metadata/feature_extractions',
        'metadata/augmentations',
        'users'
    ]
    
    for dir_path in directories:
        full_path = data_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
    
    return data_root
```

### 4. Environment Variables

Add these to your Railway environment variables:

```
USE_VOLUME=true
DATA_VOLUME_PATH=/app/backend/data
```

### 5. Verify Volume Setup

After deployment, SSH into your Railway instance to verify:

```bash
railway run railway shell

# In the shell:
ls -la /app/backend/data/
```

## Important Notes

1. **First Deployment**: The volume will be empty initially. You'll need to either:
   - Re-upload your data through the web interface
   - Use `railway run` to copy data files directly

2. **Data Migration**: To migrate existing data:
   ```bash
   # On your local machine
   tar -czf data_backup.tar.gz backend/data/
   
   # Upload to Railway instance
   railway run scp data_backup.tar.gz /app/
   railway run tar -xzf /app/data_backup.tar.gz -C /app/
   ```

3. **Backups**: Set up regular backups of your volume data:
   - Use Railway's backup features
   - Or create a scheduled job to backup to external storage

4. **Cost**: Volumes incur additional charges on Railway. Check pricing at https://railway.app/pricing

## Testing Persistence

After setting up the volume:

1. Upload a test file through your web interface
2. Redeploy your application
3. Check if the file still exists after redeployment

The data should persist across deployments once the volume is properly configured.