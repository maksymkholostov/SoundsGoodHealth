#!/bin/bash

# Railway Data Migration Script
# This script helps migrate your local data to Railway's persistent volume

echo "Railway Data Migration Tool"
echo "=========================="

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Error: Railway CLI not installed. Please install it first:"
    echo "brew install railway (on macOS)"
    echo "or visit: https://docs.railway.app/develop/cli"
    exit 1
fi

# Function to backup local data
backup_data() {
    echo "Creating backup of local data..."
    if [ -d "backend/data" ]; then
        timestamp=$(date +%Y%m%d_%H%M%S)
        backup_file="data_backup_${timestamp}.tar.gz"
        
        # Create backup excluding large model files if needed
        tar -czf "$backup_file" \
            --exclude='*.pkl' \
            --exclude='*.h5' \
            --exclude='*.onnx' \
            backend/data/
        
        echo "Backup created: $backup_file"
        echo "Size: $(du -h "$backup_file" | cut -f1)"
        return 0
    else
        echo "Error: backend/data directory not found"
        return 1
    fi
}

# Function to upload data to Railway
upload_to_railway() {
    local backup_file=$1
    
    echo "Uploading data to Railway..."
    echo "This will:"
    echo "1. Upload the backup file to your Railway instance"
    echo "2. Extract it to the volume mount point"
    echo ""
    read -p "Continue? (y/n): " confirm
    
    if [ "$confirm" != "y" ]; then
        echo "Upload cancelled"
        return 1
    fi
    
    # Upload and extract in Railway environment
    echo "Uploading $backup_file to Railway..."
    railway run --service web "mkdir -p /app/backend/data"
    
    # Copy file to Railway
    echo "Copying backup file..."
    cat "$backup_file" | railway run --service web "cat > /tmp/data_backup.tar.gz"
    
    # Extract in Railway
    echo "Extracting data on Railway..."
    railway run --service web "cd /app && tar -xzf /tmp/data_backup.tar.gz"
    
    # Clean up
    railway run --service web "rm /tmp/data_backup.tar.gz"
    
    echo "Data migration complete!"
    return 0
}

# Function to verify volume setup
verify_volume() {
    echo "Verifying volume setup..."
    railway run --service web "ls -la /app/backend/data/" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "Volume appears to be mounted correctly"
        
        # Count files
        file_count=$(railway run --service web "find /app/backend/data -type f | wc -l" 2>/dev/null)
        echo "Total files in volume: $file_count"
    else
        echo "Warning: Could not verify volume. It may not be mounted yet."
        echo "Please ensure you've added a volume in Railway dashboard with mount path: /app/backend/data"
    fi
}

# Main menu
echo ""
echo "Select an option:"
echo "1) Backup local data"
echo "2) Upload data to Railway volume"
echo "3) Verify volume setup"
echo "4) Full migration (backup + upload)"
echo "5) Exit"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        backup_data
        ;;
    2)
        read -p "Enter backup file name: " backup_file
        if [ -f "$backup_file" ]; then
            upload_to_railway "$backup_file"
        else
            echo "Error: File $backup_file not found"
            exit 1
        fi
        ;;
    3)
        verify_volume
        ;;
    4)
        if backup_data; then
            # Get the latest backup file
            backup_file=$(ls -t data_backup_*.tar.gz | head -1)
            upload_to_railway "$backup_file"
            verify_volume
        fi
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "Done!"