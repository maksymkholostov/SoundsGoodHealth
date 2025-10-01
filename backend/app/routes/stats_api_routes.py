# backend/app/routes/stats_api_routes.py
"""
API routes specifically for dashboard and statistical data.
Uses services and repositories to access centralized data.
"""
from flask import Blueprint, jsonify, current_app, abort
from flask_login import login_required # Removed current_user as not needed for global stats
from pathlib import Path
import json
import traceback # For detailed error logging
import time # Add time import
from datetime import datetime

# Import necessary types from models
from backend.app.core.models.recording import RecordingType
from backend.app.core.repositories.recording_repo import RecordingRepository
from backend.app.services.dictionary_service import DictionaryService
from backend.app.services.recording_service import RecordingService

# Create blueprint with API prefix
stats_api_bp = Blueprint('stats_api', __name__, url_prefix='/api')

@stats_api_bp.route('/dashboard/stats', methods=['GET'])
@login_required # Keep login required to access the endpoint
def dashboard_stats():
    """API: Calculate and return statistics for the dashboard using services."""
    current_app.logger.info("--- Entering dashboard_stats API endpoint ---")
    
    # Initialize stats with defaults
    stats = {
        'models': 0, 'classes': 0, 'dictionaries': 0,
        'original_recordings': 0, # Typically 'gold'
        'augmented_recordings': 0,
        'pending_recordings': 0,
        'total_recordings': 0 # Often gold + augmented
    }
    
    # We'll always recalculate stats to ensure they're up-to-date
    # Previously there was a needs_cache_update flag check, but now we always update
    global_stats_path = Path(current_app.config.get('DATA_ROOT', './data')) / 'metadata' / 'stats' / 'global_stats.json'
    current_app.logger.info(f"Stats cache file path: {global_stats_path}")
    
    try:
        # Always recalculate stats using services
        total_recalc_start_time = time.time()
        current_app.logger.info("--- Recalculating dashboard stats START ---")
        # Access services and repositories from the application context
        dictionary_repo = getattr(current_app, 'dictionary_repository', None)
        recording_service = getattr(current_app, 'recording_service', None)
        current_app.logger.info(f"DictionaryRepository available: {dictionary_repo is not None}")
        current_app.logger.info(f"RecordingService available: {recording_service is not None}")

        if not dictionary_repo:
            current_app.logger.error("Stats API: DictionaryRepository not available in app context.")
            raise RuntimeError("DictionaryRepository not configured.")
        if not recording_service:
            current_app.logger.error("Stats API: RecordingService not available in app context.")
            raise RuntimeError("RecordingService not configured.")

        # Count Dictionaries
        try:
             dict_start = time.time()
             all_dictionaries = dictionary_repo.get_all_dictionaries()
             stats['dictionaries'] = len(all_dictionaries)
             dict_duration = time.time() - dict_start
             current_app.logger.info(f"--- Dictionary Count ({stats['dictionaries']}) took {dict_duration:.4f} seconds ---")
        except Exception as e: current_app.logger.error(f"Stats API: Error counting dictionaries: {e}")

        # Count Classes
        try:
             class_start = time.time()
             all_classes = dictionary_repo.get_all_classes()
             stats['classes'] = len(all_classes)
             class_duration = time.time() - class_start
             current_app.logger.info(f"--- Class Count ({stats['classes']}) took {class_duration:.4f} seconds ---")
        except Exception as e: current_app.logger.error(f"Stats API: Error counting classes: {e}")

        # Count Recordings
        try:
             rec_start = time.time()
             # Count GOLD
             gold_rec_start = time.time()
             original_recordings = recording_service.find_recordings(
                 recording_type=RecordingType.GOLD
             )
             gold_rec_duration = time.time() - gold_rec_start
             stats['original_recordings'] = len(original_recordings)
             current_app.logger.info(f"--- Original (Gold) Recording Count ({stats['original_recordings']}) took {gold_rec_duration:.4f} seconds ---")

             # Count AUGMENTED
             aug_rec_start = time.time()
             augmented_recordings = recording_service.find_recordings(
                 recording_type=RecordingType.AUGMENTED
             )
             aug_rec_duration = time.time() - aug_rec_start
             stats['augmented_recordings'] = len(augmented_recordings)
             current_app.logger.info(f"--- Augmented Recording Count ({stats['augmented_recordings']}) took {aug_rec_duration:.4f} seconds ---")

             # Count PENDING
             pend_rec_start = time.time()
             pending_recordings = recording_service.find_recordings(
                 recording_type=RecordingType.PENDING
             )
             pend_rec_duration = time.time() - pend_rec_start
             stats['pending_recordings'] = len(pending_recordings)
             current_app.logger.info(f"--- Pending Recording Count ({stats['pending_recordings']}) took {pend_rec_duration:.4f} seconds ---")

             stats['total_recordings'] = stats['original_recordings'] + stats['augmented_recordings'] # Gold + Augmented
             rec_duration = time.time() - rec_start
             current_app.logger.info(f"--- Total Recording Counting took {rec_duration:.4f} seconds ---")
        except Exception as e: current_app.logger.error(f"Stats API: Error counting recordings: {e}")

        # Count Models
        try:
             model_start = time.time()
             model_count = 0
             models_dir = Path(current_app.config.get('DATA_ROOT', './data')) / 'models'
             if models_dir.is_dir():
                  model_files = list(models_dir.rglob('*.h5')) + list(models_dir.rglob('*.pkl')) + list(models_dir.rglob('*.onnx'))
                  model_count = len(model_files)
             stats['models'] = model_count
             model_duration = time.time() - model_start
             current_app.logger.info(f"--- Model Count ({stats['models']}) took {model_duration:.4f} seconds ---")
        except Exception as e: current_app.logger.error(f"Stats API: Error counting models: {e}")

        total_recalc_duration = time.time() - total_recalc_start_time
        current_app.logger.info(f"--- Recalculating dashboard stats END - Total Duration: {total_recalc_duration:.4f} seconds ---")

        # Save updated stats to cache
        current_app.logger.info(f"Saving recalculated stats to cache: {stats}")
        try:
            file_manager = getattr(current_app, 'file_manager', None)
            if file_manager:
                 # Use FileManager's save_json for consistency and error handling
                 file_manager.save_json(stats, global_stats_path)
                 current_app.logger.info(f"Global stats cache updated successfully using FileManager at {global_stats_path}")
            else: # Fallback if file_manager is not available for some reason
                 current_app.logger.warning("FileManager not found, attempting manual save for stats cache.")
                 global_stats_path.parent.mkdir(parents=True, exist_ok=True)
                 with open(global_stats_path, 'w', encoding='utf-8') as f:
                      json.dump(stats, f, indent=2)
                 current_app.logger.info(f"Global stats cache updated successfully using manual save at {global_stats_path}")
        except Exception as save_e:
            # Log error but don't fail the request, just serve the calculated stats
            current_app.logger.error(f"Stats API: Error saving global stats cache: {save_e}")

        # Return the freshly calculated stats
        current_app.logger.info(f"--- Returning stats: {stats} ---")
        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        current_app.logger.error(f"API Error gathering dashboard stats: {str(e)}\n{traceback.format_exc()}")
        # Return default stats on major error
        default_stats = {key: 0 for key in stats}
        current_app.logger.info(f"--- Returning default stats due to error: {default_stats} ---")
        return jsonify({"success": False, "error": f"Failed to calculate stats: {str(e)}", "stats": default_stats}), 500

# --- Old File System Helpers Removed ---
# The functions _load_json_static, _count_dictionaries_manually,
# _get_all_class_definitions, and _get_all_class_sample_counts_detailed
# have been removed as the logic is now handled using services and repositories.