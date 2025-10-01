#!/usr/bin/env python3
"""
WSGI Entry Point for SoundClassifiers v10

Purpose: Production deployment entry point for WSGI servers (Gunicorn, uWSGI, etc.)
Usage: gunicorn wsgi:app
Note: This file is ESSENTIAL for production deployment on Railway and other platforms
"""

from flask_app import app

if __name__ == "__main__":
    app.run() 