import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, BinaryIO

from backend.app.storage.file_manager import FileManager
from backend.app.ml.utils.audio_utils import analyze_audio_bytes


class FileService:
    """
    Service for file operations.
    
    Provides higher-level file operations using relative paths,
    building on the FileManager's low-level operations.
    Ensures consistent interaction with the file system based on application logic.
    """
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the file service.
        
        Args:
            file_manager: FileManager instance for storage operations
        """
        self.file_manager = file_manager
        self.logger = logging.getLogger(__name__)
    
    def _get_absolute_path(self, relative_path: str) -> Path:
        """Helper to construct absolute path from relative path."""
        return Path(self.file_manager.data_root) / relative_path
    
    def write_file(self, relative_path: str, content: bytes) -> bool:
        """
        Write content to a file at the specified relative path.
        
        Args:
            relative_path: Path relative to data_root
            content: Binary content to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            absolute_path = self._get_absolute_path(relative_path)
            # Ensure directory exists (handled by FileManager.save_file)
            # os.makedirs(absolute_path.parent, exist_ok=True)
            
            # Write the file using file_manager
            return self.file_manager.save_file(content, absolute_path)
        except Exception as e:
            self.logger.error(f"Error writing file {relative_path}: {e}")
            return False
    
    def read_file(self, relative_path: str) -> Optional[bytes]:
        """
        Read file content from the specified relative path.
        
        Args:
            relative_path: Path relative to data_root
            
        Returns:
            Binary content if successful, None otherwise
        """
        try:
            absolute_path = self._get_absolute_path(relative_path)
            
            # Read the file using file_manager
            return self.file_manager.load_file(absolute_path)
        except Exception as e:
            self.logger.error(f"Error reading file {relative_path}: {e}")
            return None
    
    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file at the specified relative path.
        
        Args:
            relative_path: Path relative to data_root
            
        Returns:
            True if successful, False otherwise
        """
        try:
            absolute_path = self._get_absolute_path(relative_path)
            
            # Delete the file using file_manager
            return self.file_manager.delete_file(absolute_path)
        except Exception as e:
            self.logger.error(f"Error deleting file {relative_path}: {e}")
            return False
    
    def analyze_audio_file(self, file_data: bytes) -> Dict[str, Any]:
        """
        Analyze an audio file to extract basic properties using centralized utils.
        
        Args:
            file_data: Binary audio data
            
        Returns:
            Dictionary with audio properties
        """
        try:
            # Use the centralized audio analysis function
            return analyze_audio_bytes(file_data)
        except Exception as e:
            self.logger.error(f"Error analyzing audio file: {str(e)}")
            return {
                'channels': 0,
                'sample_width': 0,
                'sample_rate': 0,
                'n_frames': 0,
                'duration': 0,
                'max_amplitude': 0,
                'rms': 0,
                'error': str(e)
            }
    
    def list_files(self, relative_dir_path: str, pattern: str = "*") -> List[str]:
        """
        List files in a directory at the specified relative path.
        
        Args:
            relative_dir_path: Directory path relative to data_root
            pattern: File pattern to match (default: "*")
            
        Returns:
            List of filenames
        """
        try:
            absolute_path = self._get_absolute_path(relative_dir_path)
            
            # Ensure directory exists
            if not absolute_path.exists():
                self.logger.warning(f"Directory does not exist when listing files: {absolute_path}")
                return []
            
            # List files using file_manager
            files = self.file_manager.list_files(absolute_path, pattern)
            return [str(f.name) for f in files]
        except Exception as e:
            self.logger.error(f"Error listing files in {relative_dir_path}: {e}")
            return []
    
    def load_json(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """
        Load JSON data from the specified relative path.
        
        Args:
            relative_path: Path relative to data_root
            
        Returns:
            Dictionary if successful, None otherwise
        """
        try:
            absolute_path = self._get_absolute_path(relative_path)
            return self.file_manager.load_json(absolute_path)
        except Exception as e:
            self.logger.error(f"Error loading JSON from {relative_path}: {e}")
            return None
    
    def save_json(self, relative_path: str, data: Dict[str, Any]) -> bool:
        """
        Save JSON data to the specified relative path.
        
        Args:
            relative_path: Path relative to data_root
            data: Dictionary to save as JSON
            
        Returns:
            True if successful, False otherwise
        """
        try:
            absolute_path = self._get_absolute_path(relative_path)
            return self.file_manager.save_json(data, absolute_path)
        except Exception as e:
            self.logger.error(f"Error saving JSON to {relative_path}: {e}")
            return False
