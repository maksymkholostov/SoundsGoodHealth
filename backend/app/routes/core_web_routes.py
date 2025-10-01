# backend/app/routes/core_web_routes.py
"""
Core web routes for index, static files, and general pages.
"""
from flask import Blueprint, render_template, send_from_directory, current_app, redirect, url_for, session, jsonify, g, request, flash, send_file, make_response
from flask_login import login_required, current_user
from pathlib import Path
import json
import traceback
import os
import time
import zipfile
import io
# Removed import of utils.id_mapper as it's no longer needed
# Ensure this path is correct relative to the execution context
from backend.app.core.models.recording import RecordingType

# Create blueprint
core_web_bp = Blueprint('core_web', __name__, template_folder='../../../frontend/templates', static_folder='../../../frontend/static')

@core_web_bp.route('/')
@login_required
def index():
    """Render the dashboard page by fetching stats via internal API call."""
    user_id = session.get('user_id', getattr(current_user, 'id', None))
    username = session.get('username', getattr(current_user, 'username', 'Unknown'))
    is_admin = session.get('is_admin', getattr(current_user, 'is_admin', False))

    current_app.logger.info(f"--- Entering dashboard route for user: {user_id}")

    # Default stats structure in case of API failure
    stats = {
        'total_recordings': 0, 'original_recordings': 0, 'gold_recordings': 0,
        'augmented_recordings': 0, 'pending_recordings': 0, 'user_id': user_id,
        'classes': 0, 'dictionaries': 0, 'models': 0 # Ensure all expected keys are present
    }

    if not user_id:
        current_app.logger.error("User ID not found in session or current_user within index route.")
        return "Error: User not identified.", 500

    try:
        current_app.logger.info(f"--- Preparing internal API call to stats endpoint for user: {user_id}")
        start_time = time.time()
        stats_api_url = url_for('stats_api.dashboard_stats') # Make sure 'stats_api' is the correct blueprint name

        with current_app.test_client() as client:
            # Set session for the test client request
            with client.session_transaction() as sess:
                sess['user_id'] = user_id
                sess['username'] = username
                sess['is_admin'] = is_admin
                # Copy other necessary session items if needed by the API

            current_app.logger.info(f"--- Making GET request to {stats_api_url} for user: {user_id}")
            response = client.get(stats_api_url)
            api_call_duration = time.time() - start_time
            current_app.logger.info(f"--- Internal API call to {stats_api_url} completed in {api_call_duration:.4f} seconds with status {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                if data and data.get('success') and 'stats' in data:
                    current_app.logger.info("Successfully retrieved stats from API for dashboard.")
                    retrieved_stats = data['stats']
                    # Ensure all keys from default are present, update with retrieved data
                    for key in stats:
                        if key in retrieved_stats:
                            stats[key] = retrieved_stats[key]
                else:
                    current_app.logger.warning(f"Dashboard stats API call success=False or missing 'stats': {data}")
            else:
                current_app.logger.warning(f"Dashboard stats API call failed with status {response.status_code}")

    except Exception as e:
        current_app.logger.error(f"Error during internal API call for dashboard stats for user {user_id}: {e}", exc_info=True)
        # Proceed with default stats if API call fails

    current_app.logger.info(f"--- Rendering dashboard.html template for user: {user_id}")
    return render_template('dashboard.html', stats=stats)


# --- Static Files ---

@core_web_bp.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files from the application's static folder."""
    if not current_app.static_folder or not os.path.isdir(current_app.static_folder):
         # Fallback if static_folder isn't configured properly
         alt_static_folder = current_app.config.get('STATIC_FOLDER', 'static') # Check config
         if os.path.isdir(alt_static_folder):
              current_app.logger.debug(f"Serving static file using configured STATIC_FOLDER: {alt_static_folder}")
              return send_from_directory(alt_static_folder, filename)
         else:
              current_app.logger.error(f"Static folder not found at app.static_folder ('{current_app.static_folder}') or config STATIC_FOLDER ('{alt_static_folder}').")
              return "Static file not found.", 404 # Or handle differently
    else:
         # Use the app's primary static folder
         return send_from_directory(current_app.static_folder, filename)


# --- General Pages ---

@core_web_bp.route('/how_it_works')
def how_it_works_page():
    """Serve the How It Works page."""
    return render_template('how_it_works.html')

@core_web_bp.route('/trained_models')
@login_required
def trained_models_page():
    """Display all trained models with option to train new ones."""
    current_app.logger.info("--- Entering /trained_models route ---")
    current_user_id = getattr(current_user, 'id', None)
    view_all_mode = True  # Always show all models as requested
    
    models = []
    error_loading = False
    error_message = None
    
    try:
        backend_data_path = Path(current_app.config['DATA_ROOT'])
        metadata_base_path = backend_data_path / 'metadata' / 'models'
        models_base_path = backend_data_path / 'models'
        
        if not metadata_base_path.is_dir():
            current_app.logger.warning(f"Metadata directory not found: {metadata_base_path}")
            flash("Could not find the model metadata directory.", "warning")
        else:
            # Scan all users and models
            user_ids_to_scan = [d.name for d in metadata_base_path.iterdir() if d.is_dir()]
            
            for user_id in user_ids_to_scan:
                user_metadata_path = metadata_base_path / user_id
                if not user_metadata_path.is_dir(): 
                    continue
                    
                for dict_dir_path in user_metadata_path.iterdir():
                    if not dict_dir_path.is_dir(): 
                        continue
                    dict_id = dict_dir_path.name
                    
                    for metadata_file_path in dict_dir_path.glob('*.json'):
                        if not metadata_file_path.is_file(): 
                            continue
                        model_id = metadata_file_path.stem
                        model_dir_path = models_base_path / dict_id / model_id
                        
                        if model_dir_path.is_dir() and _model_dir_contains_valid_files(model_dir_path):
                            model_info = _get_model_info_from_paths(
                                str(model_dir_path), 
                                str(metadata_file_path), 
                                user_id, 
                                dict_id, 
                                model_id
                            )
                            if model_info:
                                models.append(model_info)
                                
    except Exception as e:
        current_app.logger.error(f"Error loading models for trained_models page: {e}", exc_info=True)
        error_loading = True
        error_message = f"An error occurred while loading model data: {str(e)}"
        flash("Error loading model data. Please check application logs.", "error")
        models = []
    
    if not models and not error_loading:
        flash("No trained models found. Train your first model to get started!", "info")
    
    # Sort models by creation date (newest first)
    try:
        models.sort(key=lambda m: m.get('created_at', '0'), reverse=True)
    except Exception as sort_e:
        current_app.logger.warning(f"Could not sort models: {sort_e}")
    
    return render_template(
        'trained_models.html',
        models=models,
        error_loading=error_loading,
        error_message=error_message,
        view_all_mode=view_all_mode
    )

@core_web_bp.route('/play')
@login_required
def play_page():
    """Redirect to the games selection page."""
    # Redirect to the games page
    return redirect(url_for('games.games_page'))

# --- MODIFIED: Training Sounds Page ---
@core_web_bp.route('/training_sounds')
@login_required
def training_sounds_page():
    """Render the page listing gold and augmented sounds for training."""
    user_id = getattr(current_user, 'id', None)
    if not user_id:
        current_app.logger.error("Cannot fetch training sounds: User ID not found.")
        flash("User session error. Please log in again.", "error")
        return redirect(url_for('auth_web.login_page')) # Example: redirect to login

    # Determine scope based on session setting
    view_all = session.get('view_all_mode', False)
    scope = 'all' if view_all else 'user'
    target_user_id = user_id # Only used if scope is 'user'

    current_app.logger.info(f"Rendering training_sounds.html for user: {user_id}, scope: {scope}")

    # Get the recording service from the app context
    recording_service = current_app.recording_service # Assuming service is attached to app

    # Log service availability
    current_app.logger.info(f"RecordingService instance found in route: {recording_service is not None}")

    # Define the types we want to fetch
    target_types = [RecordingType.GOLD, RecordingType.AUGMENTED]

    sounds_data = [] # Default to empty list
    if recording_service:
        try:
            # Call the modified service method
            sounds_data = recording_service.get_sound_instances(
                types=target_types,
                user_id=target_user_id if scope == 'user' else None, # Pass user_id only if scope is 'user'
                scope=scope
            )
            # Sort by timestamp descending (most recent first)
            # Ensure timestamp exists and handle potential None values or different formats
            sounds_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

            # Log the number of sounds found
            current_app.logger.info(f"Found {len(sounds_data)} training sounds for user {user_id}, scope {scope}.")

            # TODO: Add check for 'features_extracted' flag - This needs FeatureService integration later
            # For now, the template handles a missing/false flag gracefully.

        except Exception as e:
            current_app.logger.error(f"Error fetching training sounds via service for user {user_id}, scope {scope}: {e}", exc_info=True)
            flash("Error loading training sounds data.", "error") # Flash error message
    else:
        current_app.logger.error("RecordingService not found on current_app.")
        flash("Internal server error: Recording service unavailable.", "error") # Flash error message

    # Pass the fetched (and sorted) data to the template
    return render_template('training_sounds.html', sounds=sounds_data)
# --- END MODIFIED ---

# --- RENAMED: Full Developer Guide Page ---
@core_web_bp.route('/developer') # Renamed URL
@login_required
def developer_guide(): # Renamed function
    """Render the full developer guide page."""
    current_app.logger.info("--- Entering /developer route (Full Guide) ---")
    current_user_id = getattr(current_user, 'id', None)
    view_all_mode = True

    models = []
    processed_model_ids = set()
    error_loading = False
    error_message = None

    try:
        backend_data_path   = Path(current_app.config['DATA_ROOT'])
        metadata_base_path  = backend_data_path / 'metadata' / 'models'
        models_base_path    = backend_data_path / 'models'

        current_app.logger.info(f"Metadata base path: {metadata_base_path}")
        current_app.logger.info(f"Models base path:   {models_base_path}")

        if not metadata_base_path.is_dir():
            current_app.logger.warning(f"Metadata directory not found or inaccessible: {metadata_base_path}")
            flash("Could not find the model metadata directory.", "warning")
        else:
            # Scan users
            user_ids_to_scan = [d.name for d in metadata_base_path.iterdir() if d.is_dir()]
            current_app.logger.info(f"Scanning user metadata IDs: {user_ids_to_scan}")

            for user_id in user_ids_to_scan:
                user_metadata_path = metadata_base_path / user_id
                if not user_metadata_path.is_dir(): continue
                # Scan dicts
                for dict_dir_path in user_metadata_path.iterdir():
                     if not dict_dir_path.is_dir(): continue
                     dict_id = dict_dir_path.name
                     # Scan models
                     for metadata_file_path in dict_dir_path.glob('*.json'):
                         if not metadata_file_path.is_file(): continue
                         model_id = metadata_file_path.stem
                         model_dir_path = models_base_path / dict_id / model_id

                         if model_dir_path.is_dir() and _model_dir_contains_valid_files(model_dir_path):
                              model_info = _get_model_info_from_paths(
                                  str(model_dir_path), str(metadata_file_path), user_id, dict_id, model_id
                              )
                              if model_info:
                                  models.append(model_info)
                                  processed_model_ids.add(model_id)
                         else:
                            if not model_dir_path.is_dir():
                                current_app.logger.warning(f"  INVALID: Model directory missing for {model_id} at {model_dir_path}")
                            else:
                                current_app.logger.warning(f"  INVALID: Model directory exists for {model_id} at {model_dir_path}, but contains no valid model files.")
                                
    except Exception as e:
        current_app.logger.error(f"Error loading model data for developer guide: {e}", exc_info=True)
        error_loading = True
        error_message = f"An error occurred while loading model data: {str(e)}"
        flash("Error loading model data. Please check application logs.", "error")
        models = []

    if not models and not error_loading:
        # Update flash message slightly for context
        flash("No trained models found with associated metadata and model files needed for API integration.", "info")

    # Sort models
    try:
        models.sort(key=lambda m: m.get('created_at', '0'), reverse=True)
    except Exception as sort_e:
        current_app.logger.warning(f"Could not sort models by creation date: {sort_e}")

    # --- Render the NEW full guide template ---
    return render_template(
        'developer_guide.html', # New template name
        models=models,
        error_loading=error_loading,
        error_message=error_message,
        view_all_mode=view_all_mode
    )

# --- NEW: Quick Start & Downloads Page Route ---
@core_web_bp.route('/developer/downloads') # Takes over the old URL
@login_required
def developer_downloads_quickstart(): # New function name
    """Render the Quick Start / Downloads page."""
    current_app.logger.info("--- Entering /developer/downloads route (Quick Start) ---")
    # --- Reuse the exact same model loading logic as the full guide ---
    current_user_id = getattr(current_user, 'id', None)
    view_all_mode = True

    models = []
    processed_model_ids = set()
    error_loading = False
    error_message = None

    try:
        backend_data_path   = Path(current_app.config['DATA_ROOT'])
        metadata_base_path  = backend_data_path / 'metadata' / 'models'
        models_base_path    = backend_data_path / 'models'

        if not metadata_base_path.is_dir():
            flash("Could not find the model metadata directory.", "warning") # Keep flash message
        else:
            # ...(Exact same model scanning logic as above)...
            user_ids_to_scan = [d.name for d in metadata_base_path.iterdir() if d.is_dir()]
            for user_id in user_ids_to_scan:
                user_metadata_path = metadata_base_path / user_id
                if not user_metadata_path.is_dir(): continue
                for dict_dir_path in user_metadata_path.iterdir():
                     if not dict_dir_path.is_dir(): continue
                     dict_id = dict_dir_path.name
                     for metadata_file_path in dict_dir_path.glob('*.json'):
                         if not metadata_file_path.is_file(): continue
                         model_id = metadata_file_path.stem
                         model_dir_path = models_base_path / dict_id / model_id
                         if model_dir_path.is_dir() and _model_dir_contains_valid_files(model_dir_path):
                              model_info = _get_model_info_from_paths(
                                  str(model_dir_path), str(metadata_file_path), user_id, dict_id, model_id
                              )
                              if model_info: models.append(model_info)

    except Exception as e:
        current_app.logger.error(f"Error loading model data for quick start page: {e}", exc_info=True)
        error_loading = True
        error_message = f"An error occurred while loading model data: {str(e)}"
        flash("Error loading model data. Please check application logs.", "error")
        models = []

    if not models and not error_loading:
        flash("No trained models found with associated metadata and model files.", "info") # Keep flash message

    # Sort models
    try:
        models.sort(key=lambda m: m.get('created_at', '0'), reverse=True)
    except Exception as sort_e:
        current_app.logger.warning(f"Could not sort models by creation date: {sort_e}")

    # --- Render the NEW quick start template ---
    return render_template(
        'developer_downloads_quickstart.html', # New template name
        models=models,
        error_loading=error_loading,
        error_message=error_message,
        view_all_mode=view_all_mode
    )

# --- Helper Functions ---

def _model_dir_contains_valid_files(model_dir_path: Path) -> bool:
    """Check if a directory contains recognizable model files."""
    try:
        if not model_dir_path.is_dir(): return False # Pre-check
        
        has_pkl = any(f.name.endswith('.pkl') for f in model_dir_path.iterdir())
        has_h5 = any(f.name.endswith('.h5') for f in model_dir_path.iterdir())
        has_saved_model = (model_dir_path / 'saved_model.pb').exists() or (model_dir_path / 'saved_model').is_dir()
        
        is_valid = has_pkl or has_h5 or has_saved_model
        current_app.logger.debug(f" Model dir validation for {model_dir_path.name}: pkl={has_pkl}, h5={has_h5}, saved_model={has_saved_model}. Valid={is_valid}")
        return is_valid
    except Exception as e:
        current_app.logger.error(f"Error checking model directory content for {model_dir_path.name}: {e}")
        return False # Assume invalid on error

def _get_model_info_from_paths(model_dir_path, metadata_file_path, user_id, dict_id, model_id):
    """Reads model and metadata files to create a model info object."""
    current_app.logger.debug(f"--- Processing model {model_id} --- Path: {model_dir_path}")
    try:
        # Defaults
        model_name = f"Model {model_id[:8]}..."
        model_type = "Unknown"
        created_at = "Unknown"
        dict_name = "Unknown"
        metadata_content = None
        has_metadata = False
        file_count = 0
        model_files = []
        metadata_source = None

        # 1. Read metadata file (we know it exists from the caller)
        current_app.logger.debug(f"Metadata Check for {model_id}: Reading path: {metadata_file_path}")
        try:
            with open(metadata_file_path, 'r') as f:
                metadata_content = json.load(f)
                has_metadata = True
                metadata_source = metadata_file_path
                current_app.logger.info(f"Successfully read metadata for {model_id}")
                model_name = metadata_content.get('name', model_name)
                model_type = metadata_content.get('model_type', model_type)
                if isinstance(model_type, str) and model_type.lower() == 'cnn':
                    model_type = 'Convolutional Neural Network'
                created_at = metadata_content.get('timestamp', created_at)
        except Exception as e:
            current_app.logger.error(f"Error reading metadata file {metadata_file_path}: {e}", exc_info=True)
            has_metadata = False # Reset flag if reading failed
            metadata_content = None # Clear content on error

        # 2. Get dictionary name
        if hasattr(current_app, 'dictionary_service'):
            try:
                if dict_id:
                    dict_obj = current_app.dictionary_service.get_dictionary_by_id(dict_id)
                    if dict_obj:
                        dict_name = dict_obj.name
                else:
                    current_app.logger.warning("Dictionary ID is missing or empty, cannot fetch name.")
            except Exception as e:
                current_app.logger.error(f"Error getting dictionary name for {dict_id}: {e}")

        # 3. Get model files and determine type as fallback
        try:
            model_files = [f.name for f in Path(model_dir_path).iterdir() if f.is_file() or f.is_dir()] # List files and dirs
            file_count = len(model_files)
            lowercase_files = [f.lower() for f in model_files]
            
            # Determine type from files ONLY if metadata didn't provide it or failed
            if not has_metadata or model_type == "Unknown":
                current_app.logger.debug(f"Determining model type from files for {model_id} (Metadata found: {has_metadata}, Type from meta: {model_type if has_metadata else 'N/A'})")
                if any(f.endswith('.pkl') and (f.startswith('rf_') or 'random_forest' in f.lower()) for f in model_files):
                    model_type = "Random Forest"
                    if not has_metadata: model_name = f"Random Forest Model for {dict_name}"
                elif any(f.endswith('.h5') for f in model_files) or \
                     'saved_model' in lowercase_files or \
                     any('cnn' in f for f in lowercase_files) or \
                     any(f.startswith('cnn_') for f in lowercase_files) or \
                     model_id.startswith('cnn_') or \
                     'keras' in lowercase_files or \
                     'tensorflow' in lowercase_files:
                    model_type = "Convolutional Neural Network"
                    if not has_metadata: model_name = f"Convolutional Neural Network Model for {dict_name}"
                elif any('ensemble' in f.lower() for f in lowercase_files):
                    model_type = "Ensemble"
                    if not has_metadata: model_name = f"Ensemble Model for {dict_name}"
                else:
                    current_app.logger.info(f"Could not determine model type from files in {model_dir_path}")
        except Exception as e:
            current_app.logger.error(f"Error listing files in model directory {model_dir_path}: {e}")
            
        # 4. Extract training statistics from metadata
        training_stats = {}
        if has_metadata and metadata_content:
            training_ids = metadata_content.get('training_ids', [])
            validation_ids = metadata_content.get('validation_ids', [])
            classes = metadata_content.get('classes', [])
            metrics = metadata_content.get('metrics', {})
            
            # Count samples per class
            class_counts = {}
            for class_name in classes:
                # Extract clean class name (remove 'cls_' prefix if present)
                clean_name = class_name.replace('cls_', '').upper() if class_name.startswith('cls_') else class_name.upper()
                # Count training samples for this class
                class_count = sum(1 for tid in training_ids if clean_name.lower() in tid.lower())
                class_counts[clean_name] = class_count
            
            training_stats = {
                'total_samples': len(training_ids),
                'validation_samples': len(validation_ids),
                'class_counts': class_counts,
                'classes': classes,
                'accuracy': metrics.get('accuracy'),
                'num_train_samples': metrics.get('num_train_samples', len(training_ids)),
                'num_val_samples': metrics.get('num_val_samples', len(validation_ids))
            }
        
        # 5. Create model object
        model_info = {
            'id': model_id,
            'name': model_name,
            'model_type': model_type,
            'created_at': created_at,
            'dictionary_id': dict_id,
            'dictionary_name': dict_name,
            'user_id': user_id,
            'has_metadata': has_metadata,
            'file_count': file_count,
            'metadata': metadata_content,
            'metadata_source': metadata_source,
            'model_path': model_dir_path,
            'training_stats': training_stats
        }
        current_app.logger.debug(f"Returning model info for {model_id}: {model_info}")
        return model_info

    except Exception as e:
        current_app.logger.error(f"Error creating model info for {model_id}: {e}", exc_info=True)
        return None

@core_web_bp.route('/developer/download/csharp-client')
@login_required
def download_csharp_client():
    """Download the C# client library files as a zip."""
    try:
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf: # Use compression
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            
            files_to_zip = {
                "SoundClassifiersClient.cs": "SoundClassifiersClient.cs",
                "SoundClassifiersExample.cs": "SoundClassifiersExample.cs",
                "Developer_Integration_Guide.md": "Developer_Integration_Guide.md", # Include the guide
                # Add 'modified_theo.cs' if it's still relevant and exists at the root
                 "modified_theo.cs": "modified_theo.cs" 
            }

            missing_files = []
            for src_path, arc_name in files_to_zip.items():
                full_src_path = project_root / src_path
                if full_src_path.is_file():
                    zf.write(full_src_path, arc_name)
                    current_app.logger.info(f"Adding {arc_name} to zip from {full_src_path}")
                else:
                    missing_files.append(src_path)
                    current_app.logger.warning(f"File not found for zipping: {full_src_path}")

            if missing_files:
                 flash(f"Warning: Could not find the following files to include in the download: {', '.join(missing_files)}", "warning")

        memory_file.seek(0)
        return send_file(
            memory_file,
            as_attachment=True,
            download_name='SoundClassifiers_CSharp_Client_Package.zip', # Slightly more descriptive name
            mimetype='application/zip'
        )
    except Exception as e:
        current_app.logger.error(f"Error creating C# client download: {e}", exc_info=True)
        flash("Error generating download package.", "error")
        # Redirect to the new quick start page where the download button is
        return redirect(url_for('core_web.developer_downloads_quickstart')) 

# --- Development/Test Routes ---

@core_web_bp.route('/simple')
def simple_index():
    """Serve a simple index page without complex template inheritance (for testing)."""
    try:
        template_path = os.path.join(current_app.template_folder, 'simple_index.html')
        if not os.path.exists(template_path):
             return "Error: simple_index.html template not found.", 404
        return render_template('simple_index.html')
    except Exception as e:
        current_app.logger.error(f"Error rendering simple template: {str(e)}\n{traceback.format_exc()}")
        error_info = {
            "error": "Error rendering simple template",
            "details": str(e),
            "traceback": traceback.format_exc()
        }
        return jsonify(error_info), 500

@core_web_bp.route('/test')
def test_route():
    """A simple test route that returns plain text for health checks."""
    current_app.logger.info("Test route accessed.")
    return "App is running. Test route OK.", 200

# Commented out - was using utils.id_mapper which no longer exists
# @core_web_bp.route('/api/id-mappings', methods=['GET'])
# def get_id_mappings():
#     """Return all ID mappings for frontend use."""
#     current_app.logger.info("--- Entering /api/id-mappings route ---")
#     try:
#         mappings = {
#             'class_id': get_all_classes(),
#             'model_id': get_all_models(),
#             'sound_id': get_all_sounds(),
#             'feature_id': get_all_features(),
#             'dictionary_id': get_all_dictionaries()
#         }
#         current_app.logger.info(f"--- Successfully gathered mappings: {mappings} ---")
#         return jsonify(mappings)
#     except Exception as e:
#         current_app.logger.error(f"--- Error in /api/id-mappings: {str(e)} ---", exc_info=True)
#         return jsonify({"error": "Failed to retrieve ID mappings", "details": str(e)}), 500

def process_model_directory(models_list, model_path, model_dir, dict_dir, dict_name, user_id=None):
    """Process a model directory and add model info to the models list."""
    try:
        # Determine model type based on files in the directory
        model_type = "Unknown"
        model_files = os.listdir(model_path)
        
        # Get lowercase filenames for easier detection
        lowercase_files = [f.lower() for f in model_files]
        
        # Check if it's a Random Forest model (pkl file starting with rf_)
        rf_files = [f for f in model_files if f.endswith('.pkl') and (f.startswith('rf_') or 'random_forest' in f.lower())]
        if rf_files:
            model_type = "Random Forest"
            model_name = f"Random Forest Model for {dict_name}"
        
        # Check if it's a CNN model (expanded detection criteria)
        # Look for .h5 files, saved_model dir, 'cnn' in filenames, or model_type='cnn' in metadata
        elif any(f.endswith('.h5') for f in model_files) or \
             'saved_model' in model_files or \
             any('cnn' in f for f in lowercase_files) or \
             any(f.startswith('cnn_') for f in lowercase_files) or \
             model_dir.startswith('cnn_') or \
             'keras' in str(lowercase_files) or \
             'tensorflow' in str(lowercase_files):
            model_type = "Convolutional Neural Network"
            model_name = f"Convolutional Neural Network Model for {dict_name}"
        
        # Check if it's an Ensemble model 
        elif any('ensemble' in f.lower() for f in model_files):
            model_type = "Ensemble"
            model_name = f"Ensemble Model for {dict_name}"
        
        # Default if we can't determine the type
        else:
            # Log what files are in this directory for debugging
            current_app.logger.info(f"Model of unknown type in {model_path}, contains files: {model_files}")
            model_type = "Unknown"
            model_name = f"Model for {dict_name}"
        
        # Multiple locations to check for metadata
        metadata_paths = []
        
        # 1. Check in the model directory itself
        metadata_files = [f for f in model_files if f == 'metadata.json' or f.endswith('_metadata.json')]
        if metadata_files:
            metadata_paths.append(os.path.join(model_path, metadata_files[0]))
        
        # 2. Check in parent dictionary directory
        dict_path = os.path.dirname(model_path)
        try:
            dict_files = os.listdir(dict_path)
            dict_metadata_files = [f for f in dict_files if f == f"{model_dir}_metadata.json" or f == f"{model_dir}.json"]
            if dict_metadata_files:
                metadata_paths.append(os.path.join(dict_path, dict_metadata_files[0]))
        except Exception as e:
            current_app.logger.warning(f"Error checking dictionary directory for metadata: {e}")
        
        # 3. Check in the dedicated metadata directory structure
        try:
            # Try different root paths
            data_root_paths = []
            
            # If we have a file_manager, get the data root
            if hasattr(current_app, 'file_manager') and hasattr(current_app.file_manager, 'data_root'):
                data_root_paths.append(current_app.file_manager.data_root)
            
            # Add backend/data as another possible root
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(backend_dir, 'data')
            if os.path.exists(data_dir):
                data_root_paths.append(data_dir)
            
            # Also check at the app root level
            app_root = os.path.dirname(backend_dir)
            data_root_paths.append(app_root)
            
            # Check in each possible root path
            for root_path in data_root_paths:
                # <root>/metadata/models/<dict_id>/<model_id>.json
                metadata_dir = os.path.join(root_path, 'metadata', 'models', dict_dir)
                if os.path.exists(metadata_dir) and os.path.isdir(metadata_dir):
                    meta_files = os.listdir(metadata_dir)
                    for meta_file in meta_files:
                        # Check for exact match or prefix match
                        if meta_file == f"{model_dir}.json" or meta_file == f"{model_dir}_metadata.json" or meta_file.startswith(f"{model_dir}_"):
                            metadata_paths.append(os.path.join(metadata_dir, meta_file))
                            break
        except Exception as e:
            current_app.logger.warning(f"Error checking dedicated metadata directory for {model_dir}: {e}")
        
        # Try to read metadata from any found paths
        metadata_content = None
        has_metadata = False
        metadata_source = None
        
        for metadata_path in metadata_paths:
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        import json
                        metadata_content = json.load(f)
                        has_metadata = True
                        metadata_source = metadata_path
                        current_app.logger.info(f"Found metadata for model {model_dir} at {metadata_path}")
                        
                        # If metadata has name or type info, use it
                        if metadata_content.get('name'):
                            model_name = metadata_content.get('name')
                        if metadata_content.get('model_type'):
                            model_type = metadata_content.get('model_type')
                            # Make CNN more explicit
                            if model_type.lower() == 'cnn':
                                model_type = 'Convolutional Neural Network'
                        break  # Stop once we find valid metadata
                except Exception as e:
                    current_app.logger.error(f"Error reading metadata from {metadata_path} for model {model_dir}: {e}")
        
        # Log if metadata wasn't found
        if not has_metadata:
            current_app.logger.warning(f"No metadata found for model {model_dir} after checking these paths: {metadata_paths}")
        
        # Create a model object with the info we have
        model_obj = type('ModelProxy', (), {
            'id': model_dir,
            'name': model_name,
            'model_type': model_type,
            'created_at': metadata_content.get('timestamp', 'Found in filesystem') if metadata_content else 'Found in filesystem',
            'dictionary_id': dict_dir,
            'dictionary_name': dict_name,
            'user_id': user_id,
            'has_metadata': has_metadata,
            'file_count': len(model_files),
            'metadata': metadata_content,
            'metadata_source': metadata_source
        })
        
        # Add to models list
        models_list.append(model_obj)
    except Exception as e:
        current_app.logger.error(f"Error processing model directory {model_path}: {e}")

def init_core_web_routes(dictionary_service, recording_service):
    """
    Initialize core web routes with required services.
    
    Args:
        dictionary_service: Instance of DictionaryService  
        recording_service: Instance of RecordingService
        
    Returns:
        Configured Blueprint
    """
    return core_web_bp

