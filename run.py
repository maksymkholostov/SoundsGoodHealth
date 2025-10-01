#!/usr/bin/env python3
"""
SoundClassifiers_v10 Application Entry Point

Usage:
  To run the application normally:
      python run.py
  To run the application in debug mode (with auto-reloading):
      python run.py --debug

Additional command-line arguments:
  --port PORT_NUMBER   Specify the port to run the application on (default: 5001)
  --host HOST_ADDRESS  Specify the host address (default: 0.0.0.0)
  --no-browser         Do not automatically open the browser
  --no-login           Do not prefill login credentials

Notes:
  - In debug mode, the parent process performs minimal initialization (to trigger the reloader)
    while the reloader child process performs full initialization (test user creation, browser opening,
    extra file watching) but skips port checking/freeing.
  - In production (non-debug) mode, the full initialization (including port checks and freeing) is run.
"""

import sys
import logging
import subprocess
import os
import socket
import time
import argparse
import re
from pathlib import Path

# Check if we're running with the correct Python environment
CORRECT_PYTHON = "/opt/anaconda3/envs/sounds_easy_py310/bin/python"
CURRENT_PYTHON = sys.executable

# If we're not running with the correct Python, re-launch with the correct one
if CURRENT_PYTHON != CORRECT_PYTHON and os.path.exists(CORRECT_PYTHON):
    # We're running with the wrong Python, re-launch with the correct one
    print(f"Detected incorrect Python environment: {CURRENT_PYTHON}")
    print(f"Re-launching with correct environment: {CORRECT_PYTHON}")
    
    # Build the command with the correct Python and all original arguments
    args = [CORRECT_PYTHON] + sys.argv
    
    # Set environment to ensure subprocesses also use correct Python
    env = os.environ.copy()
    env['PATH'] = f"/opt/anaconda3/envs/sounds_easy_py310/bin:{env.get('PATH', '')}"
    
    # Execute with the correct Python and exit
    sys.exit(subprocess.call(args, env=env))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_port_available(port):
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except OSError:
        return False

def free_port(port):
    """Free a port by killing the process using it."""
    try:
        if sys.platform == 'win32':
            cmd = f"netstat -ano | findstr :{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                pid = result.stdout.split()[-1]
                subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                logger.info(f"Killed process {pid} using port {port}")
        else:
            cmd = f"lsof -i :{port} -t"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            subprocess.run(f"kill -9 {pid.strip()}", shell=True)
                            logger.info(f"Killed process {pid.strip()} using port {port}")
                        except subprocess.CalledProcessError:
                            logger.warning(f"Failed to kill process {pid.strip()}")
        time.sleep(1)
        return check_port_available(port)
    except Exception as e:
        logger.error(f"Error freeing port: {str(e)}")
        return False

def find_available_port(start_port=5001, max_attempts=10):
    """Find an available port starting from start_port."""
    port = start_port
    for _ in range(max_attempts):
        if check_port_available(port):
            return port
        logger.info(f"Port {port} is in use, attempting to free it...")
        if free_port(port):
            return port
        logger.warning(f"Could not free port {port}, trying next port...")
        port += 1
    return None

def patch_init_py():
    """Patch the __init__.py file to fix service initialization."""
    init_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'app', '__init__.py')
    if not os.path.exists(init_path):
        logger.error(f"Cannot find __init__.py at {init_path}")
        return False
    
    logger.info("Patching app/__init__.py to fix service initialization...")
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Fix DictionaryService initialization
    content = re.sub(
        r'dictionary_service\s*=\s*DictionaryService\(dictionary_repository,\s*recording_repository\)',
        'dictionary_service = DictionaryService(dictionary_repository)',
        content
    )
    
    # Fix RecordingService initialization if needed
    content = re.sub(
        r'recording_service\s*=\s*RecordingService\(recording_repository\)',
        'recording_service = RecordingService(recording_repository, dictionary_repository, file_service)',
        content
    )
    
    # Fix AuthService initialization
    content = re.sub(
        r'auth_service\s*=\s*AuthService\(user_repository,\s*app\.config\)',
        'auth_service = AuthService(user_repository)',
        content
    )
    
    # Ensure file_manager is correctly attached to app
    if 'app.file_manager = file_manager' not in content:
        content = content.replace(
            '# Initialize repositories',
            '# Initialize repositories\n    # CRITICAL: Attach file_manager to app IMMEDIATELY\n    app.file_manager = file_manager'
        )
    
    # Fix static folder configuration
    if "app.static_folder = app.config['STATIC_FOLDER']" in content:
        content = content.replace(
            "app.static_folder = app.config['STATIC_FOLDER']",
            "app.static_folder = app.config.get('STATIC_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend/static'))"
        )
    
    # Fix template folder configuration
    if "app.template_folder = app.config['TEMPLATE_FOLDER']" in content:
        content = content.replace(
            "app.template_folder = app.config['TEMPLATE_FOLDER']",
            "app.template_folder = app.config.get('TEMPLATE_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend/templates'))"
        )
    
    with open(init_path, 'w') as f:
        f.write(content)
    
    logger.info("Successfully patched app/__init__.py")
    return True

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description='Run SoundClassifiers v10 application')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the application on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the application on')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--no-login', action='store_true', help='Do not prefill login credentials')
    args = parser.parse_args()

    debug_mode = args.debug

    # --- Initialization for Debug Mode ---
    if debug_mode:
        # Check if we're in the parent or child process.
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            # Debug parent process: minimal initialization just to trigger reloading.
            logger.info("Debug mode (parent): Minimal initialization. Waiting for reloader child to start the app.")
            try:
                from flask_app import app
            except ImportError as e:
                logger.error(f"Error importing flask_app: {str(e)}")
                sys.exit(1)
            port = args.port
            extra_files = None  # Skip extra file watching in parent process.
        else:
            # Debug reloader child process: perform additional initialization (except port checking/freeing).
            port = args.port
            logger.info("Debug mode (child): Running initialization without port checking/freeing.")
            try:
                from flask_app import app, create_test_user
                logger.info("Ensuring test user exists...")
                try:
                    create_test_user(app)
                except Exception as e:
                    logger.error(f"Error creating test user: {str(e)}")
            except ImportError as e:
                logger.error(f"Error importing flask_app: {str(e)}")
                sys.exit(1)
            
            if not args.no_browser:
                from backend.app.services.web_service import WebService
                login_path = "/login" if args.no_login else "/login?ron_mode=True"
                WebService.open_browser(port=port, path=login_path)
            
            # Build list of extra files to watch for frontend changes.
            watch_paths = [
                os.path.join(os.path.dirname(__file__), 'frontend', 'templates'),
                os.path.join(os.path.dirname(__file__), 'frontend', 'static')
            ]
            extra_files = (
                [str(p) for p in Path(watch_paths[0]).rglob('*') if p.is_file()] +
                [str(p) for p in Path(watch_paths[1]).rglob('*') if p.is_file()]
            )
    # --- Initialization for Production (Non-Debug) Mode ---
    else:
        # Do full initialization including port checking/freeing.
        port = args.port
        if not check_port_available(port):
            logger.warning(f"Port {port} is in use, attempting to free it...")
            if not free_port(port):
                logger.warning(f"Could not free port {port}, finding another available port...")
                port = find_available_port(port + 1)
                if port is None:
                    logger.error("Could not find an available port")
                    sys.exit(1)
        logger.info(f"Using port {port}")
        try:
            from flask_app import app, create_test_user
            logger.info("Ensuring test user exists...")
            try:
                create_test_user(app)
            except Exception as e:
                logger.error(f"Error creating test user: {str(e)}")
        except ImportError as e:
            logger.error(f"Error importing flask_app: {str(e)}")
            sys.exit(1)
        
        if not args.no_browser:
            from backend.app.services.web_service import WebService
            login_path = "/login" if args.no_login else "/login?ron_mode=True"
            WebService.open_browser(port=port, path=login_path)
        
        watch_paths = [
            os.path.join(os.path.dirname(__file__), 'frontend', 'templates'),
            os.path.join(os.path.dirname(__file__), 'frontend', 'static')
        ]
        extra_files = (
            [str(p) for p in Path(watch_paths[0]).rglob('*') if p.is_file()] +
            [str(p) for p in Path(watch_paths[1]).rglob('*') if p.is_file()]
        )
    
    logger.info(f"Starting application on {args.host}:{port} (Debug: {args.debug})")
    if extra_files:
        logger.info(f"Watching extra files for changes in: {watch_paths}")
    else:
        logger.info("No extra files being watched (minimal initialization).")
    
    app.run(
        host=args.host, 
        port=port, 
        debug=debug_mode, 
        extra_files=extra_files
    )

if __name__ == "__main__":
    main()
