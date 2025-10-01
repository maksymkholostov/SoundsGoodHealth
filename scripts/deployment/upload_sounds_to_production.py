#!/usr/bin/env python3
"""
Upload Sounds to Production

Purpose: Package and upload sound files to Railway production server
Usage: python scripts/deployment/upload_sounds_to_production.py [--include-augmented]
Note: Creates a ZIP archive of sound files and uploads via Railway CLI
Updated: August 9, 2025

Requirements:
- Railway CLI installed and configured
- Access to the production Railway project
"""

import os
import sys
import zipfile
import tempfile
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def create_sounds_archive(data_root, include_augmented=False):
    """Create a ZIP archive of sound files"""
    
    sounds_dir = os.path.join(data_root, 'sounds')
    if not os.path.exists(sounds_dir):
        print(f"Error: Sounds directory not found at {sounds_dir}")
        return None
    
    # Create temporary archive
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"sounds_upload_{timestamp}.zip"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    
    print(f"Creating archive: {archive_name}")
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(sounds_dir):
            # Skip augmented if not included
            if not include_augmented and 'augmented' in root:
                continue
            
            # Skip discarded sounds
            if 'discarded' in root:
                continue
            
            for file in files:
                if file.endswith(('.wav', '.json')):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, data_root)
                    zipf.write(file_path, arcname)
                    file_count += 1
                    total_size += os.path.getsize(file_path)
                    
                    if file_count % 100 == 0:
                        print(f"  Added {file_count} files...")
    
    archive_size = os.path.getsize(archive_path)
    print(f"Archive created: {file_count} files, {archive_size / 1024 / 1024:.2f} MB")
    
    return archive_path

def upload_to_railway(archive_path):
    """Upload archive to Railway production"""
    
    print("\nUploading to Railway...")
    
    # Check if Railway CLI is available
    try:
        subprocess.run(['railway', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Railway CLI not found. Please install it first:")
        print("  npm install -g @railway/cli")
        return False
    
    # Create upload script
    upload_script = f"""
#!/bin/bash
# Extract sounds archive to production
echo "Extracting sounds archive..."
unzip -o /tmp/$(basename {archive_path}) -d backend/data/
echo "Extraction complete!"
ls -la backend/data/sounds/
"""
    
    script_path = os.path.join(tempfile.gettempdir(), 'upload_sounds.sh')
    with open(script_path, 'w') as f:
        f.write(upload_script)
    
    # Upload archive
    print("Uploading archive to production...")
    try:
        # Copy archive to production
        subprocess.run([
            'railway', 'run',
            f'cp {archive_path} /tmp/'
        ], check=True)
        
        # Execute extraction script
        subprocess.run([
            'railway', 'run',
            'bash', '-c', upload_script
        ], check=True)
        
        print("Upload complete!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error uploading to Railway: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Upload sound files to production')
    parser.add_argument('--include-augmented', action='store_true', 
                       help='Include augmented sound files')
    parser.add_argument('--data-root', default='backend/data',
                       help='Path to data directory')
    parser.add_argument('--dry-run', action='store_true',
                       help='Create archive but do not upload')
    args = parser.parse_args()
    
    # Adjust path if running from scripts directory
    data_root = args.data_root
    if not os.path.exists(data_root):
        data_root = os.path.join(Path(__file__).parent.parent.parent, data_root)
    
    if not os.path.exists(data_root):
        print(f"Error: Data directory not found at {data_root}")
        sys.exit(1)
    
    print("="*60)
    print("UPLOAD SOUNDS TO PRODUCTION")
    print("="*60)
    print(f"Data directory: {data_root}")
    print(f"Include augmented: {args.include_augmented}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Create archive
    archive_path = create_sounds_archive(data_root, args.include_augmented)
    if not archive_path:
        sys.exit(1)
    
    # Upload to Railway
    if not args.dry_run:
        success = upload_to_railway(archive_path)
        if not success:
            print("\nUpload failed!")
            sys.exit(1)
    else:
        print(f"\nDry run complete. Archive created at: {archive_path}")
        print("Run without --dry-run to upload to production")
    
    # Cleanup
    if not args.dry_run and os.path.exists(archive_path):
        os.remove(archive_path)
        print(f"Cleaned up temporary archive")
    
    print("\nDone!")

if __name__ == "__main__":
    main()