"""
File utilities for safe file and directory operations, especially on Windows.
"""
import shutil
import os
import time
import stat
import logging


def safe_rmtree(path, retries=5, delay=0.5, logger=None):
    """
    Safely remove a directory tree with retry logic for Windows file locking.
    
    On Windows, files may be locked by processes even after they're closed.
    This function retries the deletion with delays to allow file handles to be released.
    
    Args:
        path: Path to directory to remove
        retries: Number of retry attempts (default: 5)
        delay: Delay in seconds between retries (default: 0.5)
        logger: Optional logger instance for logging warnings
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(path):
        return True
    
    for attempt in range(retries):
        try:
            # First attempt: standard removal
            shutil.rmtree(path)
            return True
            
        except PermissionError as e:
            if attempt < retries - 1:
                # Wait and retry
                if logger:
                    logger.warning(f"Permission error removing {path}, retrying in {delay}s... (attempt {attempt + 1}/{retries})")
                time.sleep(delay)
                
                # Try to fix permissions before retrying (Windows workaround)
                try:
                    _fix_permissions(path)
                except Exception:
                    pass
            else:
                # Final attempt failed
                if logger:
                    logger.error(f"Failed to remove {path} after {retries} attempts: {e}")
                return False
                
        except Exception as e:
            if attempt < retries - 1:
                if logger:
                    logger.warning(f"Error removing {path}, retrying... (attempt {attempt + 1}/{retries}): {e}")
                time.sleep(delay)
            else:
                if logger:
                    logger.error(f"Failed to remove {path} after {retries} attempts: {e}")
                return False
    
    return False


def _fix_permissions(path):
    """
    Attempt to fix file permissions for deletion (Windows workaround).
    Recursively removes read-only flags from files.
    """
    def remove_readonly(func, path, excinfo):
        """Error handler for shutil.rmtree to handle read-only files."""
        os.chmod(path, stat.S_IWRITE)
        func(path)
    
    # Walk through directory and remove read-only flags
    for root, dirs, files in os.walk(path):
        for fname in files:
            full_path = os.path.join(root, fname)
            try:
                os.chmod(full_path, stat.S_IWRITE)
            except Exception:
                pass
