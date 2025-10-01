"""
Web service for SoundClassifiers v10.

This module provides web-related utility functions such as browser launching.
"""
import logging
import threading
import time
import webbrowser

logger = logging.getLogger(__name__)

class WebService:
    """Service for web-related utilities."""
    
    @staticmethod
    def open_browser(port=5000, delay=1.5, path="/"):
        """
        Open a web browser after a short delay.
        
        Args:
            port: Port number the application is running on
            delay: Delay in seconds before opening the browser
            path: Specific path to open (default: "/" for home page)
        """
        def _open_browser():
            time.sleep(delay)  # Wait for the server to start
            url = f"http://localhost:{port}{path}"
            logger.info("Opening web browser at %s", url)
            webbrowser.open(url)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
        
        browser_thread = threading.Thread(target=_open_browser)
        browser_thread.daemon = True
        browser_thread.start()
