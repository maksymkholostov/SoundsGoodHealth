"""
Debug routes for checking server state
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from pathlib import Path
import os
from backend.utils.volume_init import check_volume_status

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/api/debug/check-data', methods=['GET'])
@login_required
def check_data_structure():
    """Check what data exists on the server"""
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        data_root = Path('backend/data')
        
        result = {
            "data_exists": data_root.exists(),
            "structure": {}
        }
        
        if data_root.exists():
            # Check each subdirectory
            for subdir in ['sounds', 'features', 'models', 'metadata', 'users']:
                subpath = data_root / subdir
                if subpath.exists():
                    # Count files
                    if subpath.is_dir():
                        all_files = list(subpath.rglob('*'))
                        result["structure"][subdir] = {
                            "exists": True,
                            "total_files": len([f for f in all_files if f.is_file()]),
                            "total_dirs": len([f for f in all_files if f.is_dir()])
                        }
                        
                        # Sample files
                        sample_files = [str(f.relative_to(data_root)) for f in all_files if f.is_file()][:5]
                        result["structure"][subdir]["sample_files"] = sample_files
                else:
                    result["structure"][subdir] = {"exists": False}
        
        # Check current working directory
        result["cwd"] = os.getcwd()
        result["cwd_contents"] = os.listdir('.')[:20]
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@debug_bp.route('/api/debug/volume-status', methods=['GET'])
@login_required
def get_volume_status():
    """Check Railway volume configuration and status"""
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        status = check_volume_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500