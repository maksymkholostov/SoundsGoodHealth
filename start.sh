#!/bin/bash
# This is a start script for Railway deployment

# Make sure this script is executable
# chmod +x start.sh

echo "Starting application with gunicorn..."
gunicorn wsgi:app 