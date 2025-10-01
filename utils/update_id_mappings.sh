#!/bin/bash
# Script to update ID mappings
# This can be scheduled to run periodically (e.g., via cron)
# to ensure ID mappings are kept up to date
#
# Suggested crontab entry for daily updates:
# 0 3 * * * /path/to/SoundClassifiers_v10/utils/update_id_mappings.sh

# Exit on any error
set -e

# Navigate to project root (adjust this path as needed)
PROJECT_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$PROJECT_ROOT"

echo "Updating ID mappings at $(date)"
echo "Project root: $PROJECT_ROOT"

# Create log directory if it doesn't exist
mkdir -p backend/data/logs

# Run the ID discoverer
python -m utils.id_discoverer --output backend/data/logs/id_discovery_$(date +%Y%m%d).json

echo "ID mapping update completed at $(date)"

# Optional: Keep only the last 7 days of logs
find backend/data/logs -name "id_discovery_*.json" -type f -mtime +7 -delete

# Exit with success
exit 0 