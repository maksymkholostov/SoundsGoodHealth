# backend/app/routes/augmentation_routes.py
"""
Routes related to data augmentation processes and management.
Includes merged routes from original web_routes.py.
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
import os # For checking template existence

# Import RecordingType
from backend.app.core.models.recording import RecordingType
from backend.app.core.exceptions import ProcessingError # Import ProcessingError for exception handling

# Create blueprint
augmentation_bp = Blueprint('augmentation', __name__) # No url_prefix needed

# --- Augmentation Pages ---

@augmentation_bp.route('/augmentation')
@login_required
def augmentation_landing_page():
    """Serve the streamlined augmentation page focused on selecting gold standards."""
    user_id = current_user.id
    gold_recordings = []
    class_counts = {}
    augmentation_options = []

    try:
        # --- Check Service Availability ---
        if not hasattr(current_app, 'recording_service'):
            raise RuntimeError("Recording service is not available.")
        if not hasattr(current_app, 'augmentation_service'):
            raise RuntimeError("Augmentation service is not available.")

        # --- Fetch All Gold Recordings Globally ---
        all_gold_objs = [] # Initialize
        try:
            all_gold_objs = current_app.recording_service.find_recordings(recording_type=RecordingType.GOLD)
            current_app.logger.info(f"Fetched {len(all_gold_objs)} global gold recording objects.")
            # Debug: log first few recordings
            for i, rec in enumerate(all_gold_objs[:3]):
                current_app.logger.info(f"Gold recording {i}: id={rec.id}, type={rec.recording_type}")
        except Exception as fetch_e:
            current_app.logger.error(f"Error fetching gold recordings: {fetch_e}", exc_info=True)
            flash("Could not load gold standard recordings.", "error")
            # Fallback: continue with empty list
            all_gold_objs = [] 
        
        # --- Fetch ALL Augmented Recordings ONCE --- 
        all_augmented_recs = [] # Initialize
        try:
            all_augmented_recs = current_app.recording_service.find_recordings(recording_type=RecordingType.AUGMENTED)
            current_app.logger.info(f"Fetched {len(all_augmented_recs)} global augmented recording objects.")
        except Exception as aug_fetch_e:
            current_app.logger.error(f"Error fetching augmented recordings: {aug_fetch_e}", exc_info=True)
            flash("Could not load augmented recordings to calculate counts.", "warning")
            # Fallback: continue with empty list
            all_augmented_recs = [] 
            
        # --- Create a lookup for counts per source ID --- 
        augs_per_source = {} 
        for aug_rec in all_augmented_recs:
            # Use .get() for safer access to attributes that might be missing
            source_id = getattr(aug_rec, 'source_sound_id', None) 
            if source_id:
                augs_per_source[source_id] = augs_per_source.get(source_id, 0) + 1
        # --- End lookup creation ---
        
        # --- Process Gold Recordings and Add Counts --- 
        gold_recordings = []
        class_names_found = set()
        for rec in all_gold_objs: # Iterate through the fetched gold objects
            # Convert to dictionary AFTER getting necessary attributes like rec.id
            rec_dict = rec.to_dict() 
            # Ensure metadata exists
            rec_meta = rec_dict.setdefault('metadata', {}) 
            
            # Ensure class_name is present in metadata
            if not rec_meta.get('class_name'):
                 if rec.class_id:
                     class_name_from_repo = current_app.recording_service.recording_repo._get_class_name(rec.class_id)
                     rec_meta['class_name'] = class_name_from_repo if class_name_from_repo else 'Unknown Class'
                 else: 
                     rec_meta['class_name'] = 'Unknown Class'
            
            # Ensure username is present in metadata
            if not rec_meta.get('username'):
                 # Placeholder - ideally look up from user_id
                 rec_meta['username'] = 'Unknown User' 
            
            # Get the augmentation count from the lookup
            # Use rec.id directly here as we know it exists
            rec_dict['augmentation_count'] = augs_per_source.get(rec.id, 0) 
                 
            class_names_found.add(rec_meta['class_name'])
            gold_recordings.append(rec_dict)
                
        current_app.logger.info(f"Processed {len(gold_recordings)} gold recordings for display.")

        # --- Fetch Class Counts for Found Classes ---
        try:
            for class_name in class_names_found:
                 if class_name != 'Unknown Class': 
                      counts = current_app.recording_service.get_class_sample_counts(class_name)
                      class_counts[class_name] = counts 
            current_app.logger.info(f"Fetched counts for {len(class_counts)} classes.")
        except Exception as count_e:
             current_app.logger.error(f"Error fetching class counts: {count_e}", exc_info=True)
             flash("Could not load class sample counts.", "warning") 

        # --- Get Augmentation Options ---
        try:
            augmentation_options = current_app.augmentation_service.get_augmentation_options()
        except Exception as options_e:
             current_app.logger.error(f"Error fetching augmentation options: {options_e}", exc_info=True)
             flash("Could not load augmentation options.", "warning") 

        # --- Render Template ---
        template_path = os.path.join(current_app.template_folder, 'augmentation_landing.html')
        if not os.path.exists(template_path): 
            return "Error: augmentation_landing.html template not found.", 404

        return render_template('augmentation_landing.html',
                               gold_recordings=gold_recordings, 
                               class_counts=class_counts, 
                               augmentation_options=augmentation_options 
                              )

    except Exception as e:
        current_app.logger.error(f"Error rendering augmentation landing page: {str(e)}", exc_info=True)
        flash("An error occurred while loading the augmentation page.", "error")
        try: 
            return redirect(url_for('core_web.index'))
        except: 
            return redirect('/')

# --- Augmentation API Endpoints ---

# --- NEW API Endpoint for Single Recording Augmentation ---
@augmentation_bp.route('/api/augmentation/start_single_augmentation', methods=['POST'])
@login_required
def api_start_single_augmentation():
    """API: Start augmentation for a single selected gold recording."""
    user_id = current_user.id
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

    try:
        # Extract required parameters from the payload
        recording_id = data.get('recording_id')
        class_name = data.get('class_name') # Passed from hidden field
        num_augmentations_str = data.get('num_augmentations')
        augmentation_config = data.get('augmentation_config') # This should be the structured dict

        # --- Validate Inputs ---
        if not recording_id:
            return jsonify({'success': False, 'error': 'Missing recording_id'}), 400
        if not class_name:
            return jsonify({'success': False, 'error': 'Missing class_name'}), 400
        if not num_augmentations_str:
            return jsonify({'success': False, 'error': 'Missing num_augmentations'}), 400
        if augmentation_config is not None and not isinstance(augmentation_config, dict):
            return jsonify({'success': False, 'error': 'Invalid augmentation_config format (must be an object)'}), 400
        if augmentation_config is None:
            augmentation_config = {} 
            
        try:
            num_augmentations = int(num_augmentations_str)
            if num_augmentations <= 0:
                raise ValueError("Number of augmentations must be positive.")
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid num_augmentations (must be a positive integer)'}), 400

        current_app.logger.info(f"API Start Single Augmentation: User={user_id}, Recording={recording_id}, Class={class_name}, N={num_augmentations}, Config={augmentation_config}")
        current_app.logger.info(f"Config type: {type(augmentation_config)}, Config empty: {not augmentation_config}")

        # Check service availability
        if not hasattr(current_app, 'augmentation_service'):
             raise RuntimeError("Augmentation service is not available.")

        # --- Delegate to Augmentation Service ---
        result = current_app.augmentation_service.augment_single_recording(
            user_id=user_id, 
            dictionary_id=None, # Placeholder 
            class_name=class_name, 
            recording_id=recording_id,
            num_augmentations=num_augmentations,
            augmentation_config=augmentation_config
        )

        current_app.logger.info(f"Augmentation completed for {recording_id}. Result: {result}")
        return jsonify({
            'success': True, 
            'message': f'Successfully created {result.get("augmentations_created", 0)} augmentations for {recording_id}.', 
            'original_id': result.get('original_id'),
            'augmentations_created': result.get('augmentations_created', 0),
            'details': result.get('details', [])
        }), 200

    except ValueError as ve: 
        current_app.logger.warning(f"API Augmentation validation error: {ve}")
        return jsonify({"success": False, "error": str(ve)}), 400 
    except FileNotFoundError as fnf:
         current_app.logger.error(f"API Augmentation error - file not found: {fnf}")
         return jsonify({"success": False, "error": str(fnf)}), 404 
    except PermissionError as pe:
         current_app.logger.error(f"API Augmentation permission error: {pe}")
         return jsonify({"success": False, "error": "Permission denied."}), 403 
    except ProcessingError as pe:
         current_app.logger.error(f"API Augmentation processing error: {pe}", exc_info=True)
         return jsonify({"success": False, "error": f"Processing failed: {str(pe)}"}), 500 
    except RuntimeError as rte: 
        current_app.logger.error(f"API Augmentation runtime error: {rte}")
        return jsonify({"success": False, "error": str(rte)}), 503 
    except Exception as e:
        current_app.logger.error(f"API Error starting single augmentation: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f"An unexpected server error occurred: {str(e)}"}), 500


@augmentation_bp.route('/api/augmentation/bulk_augmentation', methods=['POST'])
@login_required
def api_bulk_augmentation():
    """API: Perform augmentation on multiple recordings."""
    user_id = current_user.id
    
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        recordings = data.get('recordings', [])
        num_augmentations = data.get('num_augmentations', 5)
        augmentation_config = data.get('augmentation_config', {})
        
        if not recordings:
            return jsonify({'success': False, 'error': 'No recordings specified'}), 400
        
        if not isinstance(num_augmentations, int) or num_augmentations < 1:
            return jsonify({'success': False, 'error': 'Invalid number of augmentations'}), 400
        
        # Process each recording
        results = []
        success_count = 0
        error_count = 0
        
        for recording_data in recordings:
            recording_id = recording_data.get('recording_id')
            class_name = recording_data.get('class_name')
            
            if not recording_id or not class_name:
                error_count += 1
                results.append({
                    'recording_id': recording_id,
                    'success': False,
                    'error': 'Missing recording ID or class name'
                })
                continue
            
            try:
                # Call augmentation service for this recording
                result = current_app.augmentation_service.augment_recording_by_id(
                    recording_id=recording_id,
                    user_id=user_id,
                    num_augmentations=num_augmentations,
                    augmentation_config=augmentation_config
                )
                
                if result and result.get('augmentations_created', 0) > 0:
                    success_count += 1
                    results.append({
                        'recording_id': recording_id,
                        'success': True,
                        'augmentations_created': result.get('augmentations_created', 0)
                    })
                else:
                    error_count += 1
                    results.append({
                        'recording_id': recording_id,
                        'success': False,
                        'error': result.get('message', 'Augmentation failed')
                    })
                    
            except Exception as e:
                error_count += 1
                results.append({
                    'recording_id': recording_id,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(recordings)} recordings: {success_count} successful, {error_count} errors',
            'success_count': success_count,
            'error_count': error_count,
            'results': results
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"API Error in bulk augmentation: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f"Server error: {str(e)}"}), 500

