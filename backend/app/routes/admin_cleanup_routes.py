"""
Admin cleanup routes for fixing data inconsistencies
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from pathlib import Path
import json

admin_cleanup_bp = Blueprint('admin_cleanup', __name__)

@admin_cleanup_bp.route('/api/admin/cleanup/feature-metadata', methods=['POST'])
@login_required
def cleanup_feature_metadata():
    """
    Clean up orphaned feature metadata that doesn't match actual files.
    Only accessible to admin users.
    """
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        feature_repo = current_app.feature_repository
        data_root = Path(current_app.config['DATA_ROOT'])
        
        # Count issues
        orphaned_metadata = 0
        missing_files = 0
        fixed = 0
        
        # Get all feature extractions from metadata
        all_extractions = feature_repo.get_all_extractions()
        
        for extraction in all_extractions:
            # Check if the actual feature file exists
            feature_path = data_root / extraction.filename if extraction.filename else None
            
            if feature_path and not feature_path.exists():
                # Metadata exists but file doesn't
                missing_files += 1
                # Remove the orphaned metadata
                if feature_repo.delete_extraction(extraction.id):
                    fixed += 1
                    current_app.logger.info(f"Removed orphaned feature metadata: {extraction.id}")
        
        # Now check for feature files without metadata
        feature_files = list(data_root.glob("features/**/*.npz"))
        for npz_file in feature_files:
            # Extract recording ID from filename
            # Format: gold_eh_ronrubin_20250807_152240076_2_features.npz
            filename = npz_file.stem  # Remove .npz
            if filename.endswith("_features"):
                filename = filename[:-9]  # Remove _features suffix
                # Check if metadata exists for this
                if not feature_repo.get_extraction_by_recording_id(filename):
                    orphaned_metadata += 1
                    current_app.logger.warning(f"Found feature file without metadata: {npz_file}")
        
        return jsonify({
            "success": True,
            "missing_files": missing_files,
            "orphaned_metadata": orphaned_metadata,
            "fixed": fixed,
            "message": f"Cleaned up {fixed} orphaned metadata entries"
        })
        
    except Exception as e:
        current_app.logger.error(f"Error during feature metadata cleanup: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@admin_cleanup_bp.route('/api/admin/cleanup/reset-features', methods=['POST'])
@login_required
def reset_all_features():
    """
    Reset all feature extractions - remove all feature files and metadata.
    DANGEROUS: Only for admin users.
    """
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    # Require confirmation
    data = request.get_json()
    if not data or data.get('confirm') != 'DELETE_ALL_FEATURES':
        return jsonify({
            "error": "Confirmation required",
            "message": "Send {\"confirm\": \"DELETE_ALL_FEATURES\"} to proceed"
        }), 400
    
    try:
        data_root = Path(current_app.config['DATA_ROOT'])
        features_dir = data_root / 'features'
        metadata_dir = data_root / 'metadata' / 'feature_extractions'
        
        # Count what we're deleting
        feature_files = list(features_dir.glob("**/*.npz"))
        metadata_files = list(metadata_dir.glob("**/*.json"))
        
        files_deleted = 0
        metadata_deleted = 0
        
        # Delete feature files
        for f in feature_files:
            try:
                f.unlink()
                files_deleted += 1
            except Exception as e:
                current_app.logger.error(f"Failed to delete {f}: {e}")
        
        # Delete metadata files
        for m in metadata_files:
            try:
                m.unlink()
                metadata_deleted += 1
            except Exception as e:
                current_app.logger.error(f"Failed to delete {m}: {e}")
        
        return jsonify({
            "success": True,
            "feature_files_deleted": files_deleted,
            "metadata_files_deleted": metadata_deleted,
            "message": "All features reset successfully"
        })
        
    except Exception as e:
        current_app.logger.error(f"Error during feature reset: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@admin_cleanup_bp.route('/api/admin/status/features', methods=['GET'])
@login_required
def get_feature_status():
    """
    Get detailed status of features vs recordings.
    Shows what's consistent and what's not.
    """
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        recording_repo = current_app.recording_repository
        feature_repo = current_app.feature_repository
        data_root = Path(current_app.config['DATA_ROOT'])
        
        # Get all recordings
        all_recordings = recording_repo.get_all()
        
        # Check each recording's feature status
        status = {
            "total_recordings": len(all_recordings),
            "recordings_with_features": 0,
            "recordings_without_features": 0,
            "orphaned_features": 0,
            "details": []
        }
        
        for recording in all_recordings:
            has_metadata = feature_repo.has_features(recording.user_id, recording.id)
            
            # Check for actual file
            feature_pattern = f"*{recording.id}*features.npz"
            feature_files = list(data_root.glob(f"features/**/{feature_pattern}"))
            has_file = len(feature_files) > 0
            
            if has_metadata and has_file:
                status["recordings_with_features"] += 1
                state = "OK"
            elif has_metadata and not has_file:
                status["orphaned_features"] += 1
                state = "METADATA_ONLY"
            elif not has_metadata and has_file:
                status["orphaned_features"] += 1
                state = "FILE_ONLY"
            else:
                status["recordings_without_features"] += 1
                state = "NO_FEATURES"
            
            if state != "OK":
                status["details"].append({
                    "recording_id": recording.id,
                    "class": recording.class_id,
                    "state": state,
                    "has_metadata": has_metadata,
                    "has_file": has_file
                })
        
        return jsonify(status)
        
    except Exception as e:
        current_app.logger.error(f"Error getting feature status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500