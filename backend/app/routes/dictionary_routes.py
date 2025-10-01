print("--- Executing dictionary_routes.py VERSION_MARKER_123 ---")


# backend/app/routes/dictionary_routes.py
"""
Routes for managing Dictionaries (pages and API).
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import login_required, current_user
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import json
import os # For path joining/checking
from ..core.models.dictionary import Dictionary # Assuming model location relative to app
from backend.app.core.models.recording import RecordingType
from backend.app.services.dictionary_service import DictionaryService
from backend.app.services.recording_service import RecordingService
from backend.app.forms.dictionary_forms import NewDictionaryForm # Added import
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
from backend.app.core.repositories.recording_repo import RecordingRepository

# Create blueprint
dictionary_web_bp = Blueprint('dictionary_web', __name__, template_folder='../../../frontend/templates') # No url_prefix needed here

# --- Dictionary Pages ---

@dictionary_web_bp.route('/dictionaries')
@login_required
def dictionaries_page():
    """Serve the dictionaries management page. Shows ALL dictionaries."""
    current_request_user_id = current_user.id
    # --- FORCE SCOPE TO ALL --- 
    scope = 'all' 
    # scope = request.args.get('scope', 'user') # Original line commented out
    # --- 

    dictionaries_data = []
    dictionaries_to_process = []
    error_msg = None 

    try:
        if not hasattr(current_app, 'dictionary_service'):
            current_app.logger.error("Dictionary service not found.")
            raise RuntimeError("Dictionary service not configured.")

        # --- Fetch ALL Dictionaries from Service --- 
        current_app.logger.info(f"[DictPage] Fetching ALL dictionaries from service (forced scope=all)...")
        all_dictionaries = current_app.dictionary_service.get_all_dictionaries() 
        current_app.logger.info(f"[DictPage] Service returned {len(all_dictionaries)} total dictionaries.")

        # --- Use all dictionaries (Scope is forced to 'all') --- 
        dictionaries_to_process = all_dictionaries
        current_app.logger.debug(f"[DictPage] Processing {len(dictionaries_to_process)} dictionaries (forced scope=all).")

        # --- Format Dictionaries for Template --- 
        for i, dict_data_raw in enumerate(dictionaries_to_process):
            current_app.logger.debug(f"[DictPage] Processing dictionary {i+1}...")
            try:
                is_object = hasattr(dict_data_raw, 'id') and hasattr(dict_data_raw, 'name')
                dict_id = dict_data_raw.id if is_object else dict_data_raw.get('id', 'unknown_id')
                dict_name = dict_data_raw.name if is_object else dict_data_raw.get('name', 'Unnamed')
                description = dict_data_raw.description if is_object else dict_data_raw.get('description', '')
                created_at = dict_data_raw.created_at if is_object else dict_data_raw.get('created_at')
                updated_at = dict_data_raw.updated_at if is_object else dict_data_raw.get('updated_at')
                owner_id = dict_data_raw.creator_user_id if is_object else dict_data_raw.get('creator_user_id')
                class_ids = dict_data_raw.class_ids if is_object else dict_data_raw.get('class_ids', [])
                classes_in_dict_names = []
                class_details_for_template = []
                total_samples_in_dict = 0
                if not class_ids:
                     current_app.logger.warning(f"[DictPage] Dict ID: {dict_id} has an empty class_ids list.")
                for class_id in class_ids:
                    current_app.logger.debug(f"[DictPage] --- Processing Class ID: {class_id} for Dict ID: {dict_id} ---")
                    try:
                        sound_class = current_app.dictionary_service.get_global_class_by_id(class_id)
                        if sound_class:
                            cls_is_object = hasattr(sound_class, 'name')
                            cls_name = sound_class.name if cls_is_object else sound_class.get('name')
                            cls_id = sound_class.id if cls_is_object else sound_class.get('id')
                            cls_desc = sound_class.description if cls_is_object else sound_class.get('description', '')
                            if cls_name:
                                classes_in_dict_names.append(cls_name)
                                sample_count_for_class = 0
                                if hasattr(current_app, 'recording_service'):
                                     try:
                                          counts = current_app.recording_service.get_class_sample_counts(cls_name)
                                          sample_count_for_class = counts.get('total', 0)
                                     except Exception as service_count_e:
                                          current_app.logger.error(f"[DictPage] Error getting counts for class '{cls_name}' via service: {service_count_e}")
                                else:
                                     current_app.logger.warning("[DictPage] RecordingService not available for sample counts.")
                                class_details_for_template.append({
                                    'id': cls_id,
                                    'name': cls_name,
                                    'description': cls_desc,
                                    'sample_count': sample_count_for_class
                                })
                                total_samples_in_dict += sample_count_for_class
                            else:
                                 current_app.logger.warning(f"[DictPage]     Class object found for ID {class_id}, but name was empty.")
                        else:
                            current_app.logger.warning(f"[DictPage]     Could not find class object for ID {class_id} in global registry.")
                    except Exception as e:
                        current_app.logger.error(f"Error processing details for class {class_id} in dict {dict_id}", exc_info=True)
                current_app.logger.debug(f"[DictPage] Finished processing classes for Dict ID: {dict_id}. Total samples: {total_samples_in_dict}")
                dictionaries_data.append({
                    'id': dict_id, 'name': dict_name,
                    'description': description,
                    'classes': classes_in_dict_names,
                    'class_details': class_details_for_template,
                    'sample_count': total_samples_in_dict,
                    'total_samples': total_samples_in_dict,  # Add for backward compatibility with templates
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'safe_name': dict_name.replace(' ', '_').lower(),
                    'owner': owner_id,  # This is the username (creator_user_id from Dictionary model)
                    'owner_username': owner_id,  # Template expects this field
                    'creator_user_id': owner_id,  # Keep original field name too
                    'is_owner': (str(owner_id) == str(current_request_user_id))
                })
            except Exception as dict_e:
                current_app.logger.error(f"[DictPage] Error processing dictionary item {i+1}: {str(dict_e)}", exc_info=True)
                continue

        dictionaries_data.sort(key=lambda x: x['name'].lower())
        current_app.logger.info(f"Prepared {len(dictionaries_data)} dictionaries (forced scope=all) for display for user {current_request_user_id}.")

    except Exception as e:
        current_app.logger.error(f"Error preparing dictionaries page (forced scope=all): {str(e)}", exc_info=True)
        error_msg = f"An error occurred while loading dictionaries: {str(e)}"
        flash("An error occurred while loading dictionaries. Please try again.", "error")
        return render_template('dictionaries.html',
                              dictionaries=[],
                              class_samples={},
                              current_scope='all', # Force scope in template too
                              error=error_msg)

    return render_template('dictionaries.html',
                          dictionaries=dictionaries_data,
                          current_scope='all', # Force scope in template
                          error=error_msg)


@dictionary_web_bp.route('/dictionaries/new', methods=['GET'])
@login_required
def new_dictionary_page():
    """Render the page to create a new dictionary."""
    form = NewDictionaryForm() # Create form instance
    existing_classes_data = []
    try:
        # --- Use Service Method --- 
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        all_classes = current_app.dictionary_service.get_all_classes() # Get list of SoundClass objects
        # Format for template (assuming template needs id, name, description)
        existing_classes_data = [
             {'id': cls.id, 'name': cls.name, 'description': cls.description} 
             for cls in all_classes
        ]
        existing_classes_data.sort(key=lambda x: x['name'].lower())
        # --------------------------
    except Exception as e:
         current_app.logger.warning(f"Could not load existing classes for new dictionary page: {e}")
         flash("Could not load existing class list.", "warning") # Non-fatal

    return render_template('dictionary_new.html',
                           form=form, # Pass form to template
                           existing_classes=existing_classes_data, # Use renamed variable
                           session=session)


@dictionary_web_bp.route('/dictionaries/<string:dictionary_identifier>')
@login_required
def dictionary_detail_page(dictionary_identifier):
    """Serve the dictionary detail page, finding dict by ID."""
    user_id = current_user.id
    
    try:
        # --- Ensure Services Exist ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")
             
        # --- Get Dictionary Object by ID ---
        dictionary_obj = current_app.dictionary_service.get_dictionary_by_id(dictionary_identifier) 

        if not dictionary_obj:
            flash(f"Dictionary with ID '{dictionary_identifier}' not found.", "danger")
            return redirect(url_for('dictionary_web.dictionaries_page'))

        dictionary_owner_id = dictionary_obj.creator_user_id if hasattr(dictionary_obj, 'creator_user_id') else None
        if not dictionary_owner_id:
             current_app.logger.error(f"Dictionary {dictionary_identifier} found but is missing creator_user_id.")
             flash(f"Could not determine owner for dictionary '{dictionary_identifier}'.", "danger")
             return redirect(url_for('dictionary_web.dictionaries_page'))

        # --- Prepare Dictionary Info for Template ---
        dict_data = dictionary_obj.to_dict() # Includes id, name, desc, creator, timestamps, class_ids
        class_ids = dictionary_obj.class_ids if hasattr(dictionary_obj, 'class_ids') else []
        dict_data['class_count'] = len(class_ids)
        dict_data['models_trained_count'] = "N/A" # Placeholder

        # --- Get Per-Class Details and Calculate Total Sound Counts ---
        total_counts = {'raw': 0, 'pending': 0, 'gold': 0, 'augmented': 0}
        classes_details_list = [] # Store details for each class

        for class_id in class_ids:
            try:
                sound_class = current_app.dictionary_service.get_global_class_by_id(class_id)
                if not sound_class:
                    current_app.logger.warning(f"Skipping details for unknown class ID {class_id} in dictionary {dictionary_identifier}")
                    continue 

                cls_name = sound_class.name
                cls_id = sound_class.id
                cls_desc = sound_class.description

                # Get counts for this class using RecordingService
                gold_aug_counts = current_app.recording_service.get_class_sample_counts(cls_name)
                
                # Correctly count both types of RAW recordings
                raw_recorded_recs = current_app.recording_service.find_recordings(class_id=cls_id, recording_type=RecordingType.RAW_RECORDED)
                raw_uploaded_recs = current_app.recording_service.find_recordings(class_id=cls_id, recording_type=RecordingType.RAW_UPLOADED)
                class_raw_count = len(raw_recorded_recs) + len(raw_uploaded_recs)
                
                pending_recs = current_app.recording_service.find_recordings(class_id=cls_id, recording_type=RecordingType.PENDING)
                class_pending_count = len(pending_recs)
                class_gold_count = gold_aug_counts.get('gold', 0) # Verified
                class_augmented_count = gold_aug_counts.get('augmented', 0)

                # Add to totals for the dictionary
                total_counts['raw'] += class_raw_count
                total_counts['pending'] += class_pending_count
                total_counts['gold'] += class_gold_count
                total_counts['augmented'] += class_augmented_count

                # Store detailed counts per class for display within the info section
                classes_details_list.append({
                    'id': cls_id, 
                    'name': cls_name, 
                    'description': cls_desc,
                    'raw_count': class_raw_count,
                    'pending_count': class_pending_count,
                    'gold_count': class_gold_count, # Verified
                    'augmented_count': class_augmented_count,
                })

            except Exception as e:
                # Log the full traceback to pinpoint the error
                current_app.logger.error(f"Error processing details for class {class_id} in dict {dictionary_identifier}", exc_info=True) 
                # Keep original short log message if needed for quick scanning, but traceback is key
                # current_app.logger.error(f"Short error message: {str(e)}")
        
        # Add the aggregate counts and the per-class details list to the main dictionary data
        dict_data['total_sound_counts'] = total_counts
        dict_data['classes_details'] = sorted(classes_details_list, key=lambda x: x['name'].lower()) # Sort classes alphabetically

        # Prepare final template variables
        template_vars = {
            'dictionary': dict_data, # Now contains base info + totals + list of class details
            'is_owner': (str(dictionary_owner_id) == str(user_id)) 
        }

        return render_template('dictionary_detail.html', **template_vars)
    
    except Exception as e:
        current_app.logger.error(f"Error displaying dictionary detail '{dictionary_identifier}': {str(e)}", exc_info=True)
        flash(f"Error loading dictionary details: {str(e)}", "danger")
        return redirect(url_for('dictionary_web.dictionaries_page'))


# --- Dictionary API Endpoints ---
# Note: These mostly use @login_required (session auth) based on the original file structure.
# If JWT is preferred for APIs, change decorators and use get_jwt_identity().

@dictionary_web_bp.route('/api/dictionary/create', methods=['POST'])
@login_required
def api_create_dictionary_with_classes():
    """API: Create a dictionary with classes (session auth)."""
    user_id = current_user.id
    # Handle both JSON and Form data
    data = request.get_json() if request.is_json else request.form
    is_json_request = request.is_json

    try:
        name = data.get('name', '').strip()
        description = data.get('description', '')

        # Extract classes based on input type
        new_classes_input = data.get('classes', []) if is_json_request else data.getlist('classes[]')
        # Ensure existing_class_ids are handled correctly whether from JSON (list) or Form (list)
        existing_class_ids_raw = data.get('existing_classes', []) if is_json_request else data.getlist('existing_classes[]')
        # Flatten if nested list might come from JSON/JS
        existing_class_ids = [item for sublist in existing_class_ids_raw if isinstance(sublist, list) for item in sublist] \
                             if any(isinstance(el, list) for el in existing_class_ids_raw) \
                             else existing_class_ids_raw

        # Clean inputs
        new_classes = [cls.strip() for cls in new_classes_input if isinstance(cls, str) and cls.strip()]
        existing_class_ids = [str(cid).strip() for cid in existing_class_ids if cid] # Ensure strings, remove empty

        current_app.logger.debug(f"API Create Dict: User={user_id}, Name={name}, NewCls={new_classes}, ExistCls={existing_class_ids}")

        # --- Validation ---
        if not name:
            return jsonify({"success": False, "error": "Dictionary name is required"}), 400
        if not new_classes and not existing_class_ids:
             return jsonify({"success": False, "error": "At least one new or existing class is required"}), 400

        # --- Check for duplicate name USING SERVICE ---
        if not hasattr(current_app, 'dictionary_service'):
            current_app.logger.error("API Create Dict Error: Dictionary service not available.")
            return jsonify({"success": False, "error": "Dictionary service unavailable"}), 503

        try:
            if current_app.dictionary_service.dictionary_name_exists(user_id, name):
                 current_app.logger.warning(f"API Create Dict Failed: Name '{name}' already exists for user {user_id}")
                 return jsonify({"success": False, "error": f"Dictionary name '{name}' already exists."}), 409 # Conflict
        except Exception as e:
            current_app.logger.error(f"Error checking existing dictionary name: {str(e)}")
            # Optionally proceed or return error?
            return jsonify({"success": False, "error": "Error checking for duplicate name."}), 500

        # --- Create Dictionary and Add Classes (Service should handle transactionally if possible) ---
        # Note: The service logic might need adjustment based on how it handles new vs existing classes.
        # Assuming dictionary_service.create_dictionary only takes name, user_id, desc
        # and a separate method dictionary_service.add_classes_to_dictionary handles adding/linking classes.

        # 1. Create the dictionary object/record via service
        dictionary = current_app.dictionary_service.create_dictionary(name, user_id, description)
        if not dictionary: # Check if service indicated failure
             current_app.logger.error(f"API Create Dict Failed: Service failed to create dictionary '{name}' for user {user_id}")
             return jsonify({"success": False, "error": "Failed to create dictionary record."}), 500

        # 2. Add/Link Classes
        # Add new classes to the dictionary
        failed_classes = []
        class_addition_success = True
        
        # Process new classes
        for class_name in new_classes:
            try:
                # First find or create the global class to get its ID
                global_class = current_app.dictionary_service.find_or_create_global_class(class_name)
                
                # Then add the class ID to the dictionary
                dictionary.add_class(global_class.id)
                current_app.logger.info(f"Added class '{class_name}' (ID: {global_class.id}) to dictionary {dictionary.id}")
            except Exception as e:
                failed_classes.append(class_name)
                class_addition_success = False
                current_app.logger.warning(f"Failed to add class '{class_name}' to dictionary {dictionary.id}: {str(e)}")
        
        # Process existing classes by ID
        for class_id in existing_class_ids:
            if class_id:
                try:
                    # Add the existing class ID directly to the dictionary
                    dictionary.add_class(class_id)
                    current_app.logger.info(f"Added existing class with ID '{class_id}' to dictionary {dictionary.id}")
                except Exception as e:
                    failed_classes.append(f"ID:{class_id}")
                    class_addition_success = False
                    current_app.logger.warning(f"Failed to add existing class ID '{class_id}' to dictionary {dictionary.id}: {str(e)}")
        
        # Save the dictionary with the added classes
        if current_app.dictionary_service.update_dictionary(dictionary):
            current_app.logger.info(f"Successfully saved dictionary {dictionary.id} with added classes")
        else:
            class_addition_success = False
            current_app.logger.error(f"Failed to save dictionary {dictionary.id} with added classes")

        # --- Prepare Response ---
        if class_addition_success:
            response_data = {"success": True, "message": "Dictionary created successfully.", "dictionary_id": dictionary.id}
            # Redirect only on success
            response_data["redirect"] = url_for('dictionary_web.dictionary_detail_page', dictionary_identifier=dictionary.id)
            if failed_classes:
               response_data["warning"] = f"Could not add some classes: {', '.join(failed_classes)}"
            status_code = 201 # 201 Created
        else:
            # If class addition failed, maybe delete the dictionary record created? Or leave it empty?
            # For now, just report failure.
             response_data = {"success": False, "error": "Dictionary record created, but failed to add/link classes."}
             status_code = 500

        return jsonify(response_data), status_code

    except Exception as e:
        current_app.logger.error(f"API Create Dict Error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500


@dictionary_web_bp.route('/api/dictionary/<dictionary_id>', methods=['GET'])
@login_required
def api_get_dictionary_by_id(dictionary_id):
    """API: Get a single dictionary by ID (session auth)."""
    user_id = current_user.id
    try:
        # --- Use DictionaryService (V10) ---
        # Get by ID, performs no permission check internally
        dictionary_obj = current_app.dictionary_service.get_dictionary_by_id(dictionary_id)

        if not dictionary_obj:
            return jsonify({"success": False, "error": "Dictionary not found"}), 404

        # Perform permission check here (or enhance service method)
        owner_id = dictionary_obj.creator_user_id
        is_owner = (str(owner_id) == str(user_id))
        # TODO: Add admin check if required for viewing others' dictionaries via API
        is_admin = session.get('is_admin', False)
        can_view = is_owner or is_admin # Example permission logic

        if not can_view:
            # Return 404 even if it exists but user can't access, avoid leaking info
            current_app.logger.warning(f"User {user_id} denied access to dictionary {dictionary_id} owned by {owner_id}")
            return jsonify({"success": False, "error": "Dictionary not found or access denied"}), 404 
        
        # Convert to dictionary representation
        dict_data = dictionary_obj.to_dict()

        # Add ownership info for context
        dict_data['owner'] = owner_id
        dict_data['is_owner'] = is_owner

        return jsonify({"success": True, "dictionary": dict_data})

    except Exception as e:
        current_app.logger.error(f"API Error getting dictionary {dictionary_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionary/<dictionary_id>', methods=['DELETE'])
@login_required
def api_delete_dictionary(dictionary_id):
    """API: Delete a dictionary (session auth)."""
    user_id = current_user.id
    try:
        # Ensure service exists
        if not hasattr(current_app, 'dictionary_service'):
             current_app.logger.error("api_delete_dictionary: DictionaryService not available.")
             return jsonify({"success": False, "error": "Service configuration error"}), 500

        # Assuming service method is delete_dictionary(dictionary_id) and it handles permissions internally
        # OR delete_dictionary(user_id, dictionary_id) if it needs user for permission check.
        # Let's try the version that takes dictionary_id only first, as it aligns with get_dictionary_by_id
        delete_method = None
        if hasattr(current_app.dictionary_service, 'delete_dictionary'):
            delete_method = current_app.dictionary_service.delete_dictionary
        # Add more checks here if method signature might vary (e.g., check arity)

        if not delete_method:
             current_app.logger.error("api_delete_dictionary: delete_dictionary method not found in DictionaryService.")
             return jsonify({"success": False, "error": "Service configuration error"}), 500

        # Call the delete method (adapt parameters based on actual method signature)
        # Assuming it takes only dict_id for now, based on repository structure
        success = delete_method(dictionary_id=dictionary_id) 
        # If it required user_id for permissions: success = delete_method(user_id=user_id, dictionary_id=dictionary_id)


        if not success:
            # Check if it failed because it wasn't found vs. permission denied
            dict_exists = current_app.dictionary_service.get_dictionary_by_id(dictionary_id)
            if not dict_exists:
                 return jsonify({"success": False, "error": "Dictionary not found"}), 404
            else:
                 # If it exists but deletion failed, assume permission issue or other backend error
                 current_app.logger.warning(f"API Delete failed for dictionary {dictionary_id}. Might be permission issue or repository error.")
                 # Returning 403, but could be 500 depending on repository behavior
                 return jsonify({"success": False, "error": "Failed to delete dictionary (permission denied or internal error)"}), 403 

        current_app.logger.info(f"API Dictionary {dictionary_id} deleted successfully.")
        
        # --- Trigger stats update after successful deletion ---
        # _trigger_stats_recalculation() # Removed direct call
        # --- End Trigger ---

        return jsonify({"success": True, "message": f"Dictionary deleted successfully"}) 

    except Exception as e:
        # Catch-all for unexpected errors
        current_app.logger.error(f"API Error deleting dictionary {dictionary_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionary/<dictionary_id>', methods=['PUT'])
@login_required
def api_update_dictionary(dictionary_id):
    """API: Update a dictionary's properties (name, description) (session auth)."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    try:
        # Get existing dictionary (service MUST check ownership)
        dictionary = current_app.dictionary_service.get_dictionary(user_id, dictionary_id)
        if not dictionary:
            # If service enforces ownership, 404 implies not found or not owned
            return jsonify({"success": False, "error": "Dictionary not found or permission denied"}), 404

        # Extract update data
        new_name = data.get('name', '').strip()
        new_description = data.get('description') # Allow None or empty string

        updated = False
        # Update name if provided and different
        if new_name and new_name != dictionary.name:
             # Check for name conflict with *other* dictionaries owned by the user
             if current_app.dictionary_service.dictionary_name_exists(user_id, new_name, exclude_id=dictionary.id):
                  return jsonify({"success": False, "error": f"Dictionary name '{new_name}' already exists."}), 409 # Conflict
             dictionary.name = new_name
             updated = True

        # Update description if provided and different (allows setting to empty)
        if new_description is not None and new_description != dictionary.description:
            dictionary.description = new_description
            updated = True

        if not updated:
             # Return 200 OK but indicate no changes made
             return jsonify({"success": True, "message": "No changes detected", "dictionary": dictionary.to_dict()}), 200

        # Save the updated dictionary object (service handles persistence)
        success = current_app.dictionary_service.update_dictionary(dictionary)

        if not success:
             # This suggests a persistence error in the service/DB layer
             current_app.logger.error(f"API Failed to save updates for dictionary {dictionary_id}")
             return jsonify({"success": False, "error": "Failed to save dictionary updates"}), 500

        # Get the final state to return (optional, could just return success message)
        updated_dict_obj = current_app.dictionary_service.get_dictionary(user_id, dictionary.id)
        updated_dict_data = updated_dict_obj.to_dict() if updated_dict_obj else None

        current_app.logger.info(f"API Dictionary {dictionary_id} updated by user {user_id}")
        return jsonify({
            "success": True,
            "message": "Dictionary updated successfully",
            "dictionary": updated_dict_data
        })

    except Exception as e:
        current_app.logger.error(f"API Error updating dictionary {dictionary_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionary/<dictionary_identifier>/add_class', methods=['POST'])
@login_required
def api_add_class_to_dictionary(dictionary_identifier):
    """API: Add a class (new or existing global) to a dictionary (session auth)."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    try:
        class_name = data.get('class_name', '').strip()
        description = data.get('description', '') # Optional description for new classes

        if not class_name:
            return jsonify({"success": False, "error": "Class name is required"}), 400

        # --- Use DictionaryService (V10) ---
        # Find the target dictionary by ID
        dictionary = current_app.dictionary_service.get_dictionary_by_id(dictionary_identifier)
        if not dictionary:
             return jsonify({"success": False, "error": f"Dictionary '{dictionary_identifier}' not found"}), 404
        dict_id = dictionary.id 
        owner_id = dictionary.creator_user_id # Get owner for permission check

        # Universal access policy: allow any logged-in user to modify
        user_id_for_service = user_id

        # Add the class using the service (service handles if class needs global creation)
        success, sound_class_obj = current_app.dictionary_service.add_sound_class(
            user_id_for_service, dict_id, class_name, description
        )

        if not success or not sound_class_obj:
            current_app.logger.warning(f"API failed to add class '{class_name}' to dictionary {dict_id}")
            # Check if class already exists in this dictionary for a better error
            dict_classes_raw = dictionary.classes if hasattr(dictionary, 'classes') else dictionary.get('classes', [])
            already_exists = any((c.name if hasattr(c,'name') else c.get('name')) == class_name for c in dict_classes_raw)
            error_msg = f"Class '{class_name}' already exists in this dictionary." if already_exists else "Failed to add class (internal error?)."
            status_code = 409 if already_exists else 500 # 409 Conflict
            return jsonify({"success": False, "error": error_msg}), status_code

        # Get updated dictionary state to return
        # Use service.get_dictionary as it handles permissions
        updated_dictionary = current_app.dictionary_service.get_dictionary(user_id_for_service, dict_id)

        current_app.logger.info(f"API Added class '{class_name}' to dictionary {dict_id} by user {user_id}")
        return jsonify({
            "success": True,
            "message": f"Added class '{class_name}'",
            "class": sound_class_obj.to_dict(), # Return details of the added/found class
            "dictionary": updated_dictionary.to_dict() if updated_dictionary else None # Return updated dict state
        }), 200 # Or 201 if class was newly created globally? Service might tell us.


    except Exception as e:
        current_app.logger.error(f"API Error adding class to dictionary '{dictionary_identifier}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionary/list', methods=['GET'])
@login_required
def api_list_dictionaries():
    """API: List ALL dictionaries (scope forced to all)."""
    current_request_user_id = current_user.id # User making the request
    # --- FORCE SCOPE TO ALL --- 
    scope = 'all'
    # scope = request.args.get('scope', 'user') # Original line commented out
    # --- 

    current_app.logger.info(f"API request to list dictionaries for user {current_request_user_id} (forced scope=all)")

    try:
        if not hasattr(current_app, 'dictionary_service'):
            current_app.logger.error("Dictionary service not available for listing.")
            return jsonify({"success": False, "error": "Service unavailable"}), 503

        # --- Fetch ALL dictionaries --- 
        current_app.logger.info(f"Fetching ALL dictionaries from service (forced scope=all)...")
        all_dictionaries = current_app.dictionary_service.get_all_dictionaries() 
        current_app.logger.info(f"Service returned {len(all_dictionaries)} total dictionaries.")

        # --- Use all dictionaries --- 
        dictionaries_to_return = all_dictionaries

        # --- Format results --- 
        result = []
        for item in dictionaries_to_return:
            dict_data = item.to_dict() if hasattr(item, 'to_dict') else item
            if isinstance(dict_data, dict):
                 dict_data_cleaned = {
                      'id': dict_data.get('id'),
                      'name': dict_data.get('name'),
                      'description': dict_data.get('description'),
                      'created_at': dict_data.get('created_at'),
                      'updated_at': dict_data.get('updated_at'),
                      'class_count': len(dict_data.get('class_ids', [])),
                      'owner_id': dict_data.get('creator_user_id')
                 }
                 current_app.logger.debug(f"Checking dict_data_cleaned: ID='{dict_data_cleaned['id']}', Name='{dict_data_cleaned['name']}'")
                 if dict_data_cleaned['id'] and dict_data_cleaned['name']:
                      result.append(dict_data_cleaned)
                 else:
                      current_app.logger.warning(f"Skipping dictionary due to missing ID or Name: {dict_data}")

        result.sort(key=lambda x: x['name'].lower())
        current_app.logger.info(f"API returning {len(result)} dictionaries for user {current_request_user_id} (forced scope=all).")
        return jsonify({"success": True, "dictionaries": result})

    except Exception as e:
        current_app.logger.error(f"API Error listing dictionaries (forced scope=all): {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to list dictionaries: {str(e)}"}), 500


@dictionary_web_bp.route('/api/dictionary/list-with-models', methods=['GET'])
@login_required
def api_list_dictionaries_with_models():
    """API: List dictionaries that have trained models."""
    current_request_user_id = current_user.id
    current_app.logger.info(f"API request to list dictionaries with models for user {current_request_user_id}")

    try:
        if not hasattr(current_app, 'dictionary_service'):
            current_app.logger.error("Dictionary service not available for listing.")
            return jsonify({"success": False, "error": "Service unavailable"}), 503
            
        if not hasattr(current_app, 'model_repository'):
            current_app.logger.error("Model repository not available for checking models.")
            return jsonify({"success": False, "error": "Service unavailable"}), 503

        # Fetch ALL dictionaries
        current_app.logger.info(f"Fetching all dictionaries from service...")
        all_dictionaries = current_app.dictionary_service.get_all_dictionaries()
        current_app.logger.info(f"Service returned {len(all_dictionaries)} total dictionaries.")

        # Filter to only include dictionaries with trained models
        result = []
        for item in all_dictionaries:
            dict_data = item.to_dict() if hasattr(item, 'to_dict') else item
            if isinstance(dict_data, dict):
                dict_id = dict_data.get('id')
                dict_owner = dict_data.get('creator_user_id')
                
                if dict_id and dict_owner:
                    # Check if this dictionary has any trained models
                    try:
                        # If shared models are enabled (InferenceService flag), include models from all users
                        inference_service = getattr(current_app, 'inference_service', None)
                        allow_shared = getattr(inference_service, 'ALLOW_SHARED_MODELS', False)
                        if allow_shared:
                            models = []
                            try:
                                metadata_root = current_app.model_repository.models_meta_dir
                                if metadata_root and metadata_root.exists():
                                    for user_dir in metadata_root.iterdir():
                                        if not user_dir.is_dir():
                                            continue
                                        dict_dir = user_dir / dict_id
                                        if not dict_dir.is_dir():
                                            continue
                                        for meta_file in dict_dir.glob('*.json'):
                                            data = current_app.file_service.file_manager.load_json(meta_file)
                                            if not data:
                                                continue
                                            try:
                                                from backend.app.core.models.model import ModelVersion, ModelStatus
                                                mv = ModelVersion.from_dict(data)
                                                if mv.status == ModelStatus.TRAINED:
                                                    models.append(mv)
                                            except Exception:
                                                continue
                            except Exception as e:
                                current_app.logger.warning(f"Shared model scan failed for dict {dict_id}: {e}")
                        else:
                            models = current_app.model_repository.get_for_dictionary(
                                user_id=dict_owner,
                                dict_id=dict_id
                            )
                        # Filter for trained models only
                        trained_models = [m for m in models if hasattr(m, 'status') and str(m.status) == 'ModelStatus.TRAINED']
                        
                        if trained_models:
                            dict_data_cleaned = {
                                'id': dict_id,
                                'name': dict_data.get('name'),
                                'description': dict_data.get('description'),
                                'created_at': dict_data.get('created_at'),
                                'updated_at': dict_data.get('updated_at'),
                                'class_count': len(dict_data.get('class_ids', [])),
                                'owner_id': dict_owner,
                                'model_count': len(trained_models)
                            }
                            current_app.logger.debug(f"Dictionary '{dict_data_cleaned['name']}' has {len(trained_models)} trained models")
                            if dict_data_cleaned['id'] and dict_data_cleaned['name']:
                                result.append(dict_data_cleaned)
                    except Exception as model_check_error:
                        current_app.logger.warning(f"Error checking models for dictionary {dict_id}: {model_check_error}")
                        # Skip this dictionary if we can't check its models

        result.sort(key=lambda x: x['name'].lower())
        current_app.logger.info(f"API returning {len(result)} dictionaries with trained models.")
        return jsonify({"success": True, "dictionaries": result})

    except Exception as e:
        current_app.logger.error(f"API Error listing dictionaries with models: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to list dictionaries: {str(e)}"}), 500


@dictionary_web_bp.route('/api/dictionary/check-name', methods=['GET'])
@login_required
def api_check_dictionary_name():
    """API: Check if a dictionary name exists for the current user (session auth)."""
    user_id = current_user.id
    name = request.args.get('name', '').strip()
    exclude_id = request.args.get('exclude_id') # Optional ID to exclude (for updates)

    if not name:
        return jsonify({"success": False, "error": "Dictionary name query parameter is required"}), 400

    try:
        # Use service method to check for name existence, optionally excluding an ID
        exists = current_app.dictionary_service.dictionary_name_exists(user_id, name, exclude_id=exclude_id)
        return jsonify({"success": True, "exists": exists})

    except Exception as e:
        current_app.logger.error(f"API Error checking dictionary name '{name}' for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionary/<dictionary_id>/classes/<class_id>', methods=['DELETE'])
@login_required
def api_remove_class_from_dictionary(dictionary_id, class_id):
    """API: Remove a class association from a dictionary (session auth)."""
    user_id = current_user.id
    try:
        if not hasattr(current_app, 'dictionary_service'):
            current_app.logger.error("DictionaryService not available for class removal.")
            return jsonify({"success": False, "error": "Service unavailable"}), 503

        success = current_app.dictionary_service.remove_class_from_dictionary(user_id, dictionary_id, class_id)

        if success:
            return jsonify({"success": True, "message": "Class removed from dictionary successfully."})
        else:
            # Service method logs specific reasons (not found, permission, save error)
            # Determine appropriate status code - maybe 404 if class/dict not found, 403 if permission?
            # For now, return a generic error, service logs provide details.
             return jsonify({"success": False, "error": "Failed to remove class from dictionary. Check logs for details."}), 400 # Bad Request or 500?

    except Exception as e:
        current_app.logger.error(f"API Error removing class {class_id} from dict {dictionary_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dictionary_web_bp.route('/api/dictionaries/stats', methods=['GET'])
@login_required
def api_get_dictionaries_stats():
    """API: Get basic statistics about dictionaries."""
    # Implementation placeholder - replace with actual logic
    current_app.logger.info("Received request for dictionary stats.")
    # Example: You might query the dictionary service/repo for counts
    try:
        all_dicts = current_app.dictionary_service.get_all_dictionaries()
        # This part still might cause the TypeError if called with user_id
        # user_dicts = current_app.dictionary_service.get_all_dictionaries(user_id=current_user.id)
        # Correct way: Filter after getting all
        user_dicts = [d for d in all_dicts if hasattr(d, 'creator_user_id') and str(d.creator_user_id) == str(current_user.id)]

        stats = {
            "total_dictionaries": len(all_dicts),
            "user_dictionaries": len(user_dicts)
        }
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        current_app.logger.error(f"API Error getting dictionary stats: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to retrieve dictionary stats."}), 500


# --- Helper Functions ---
# ... (Removed helpers - _load_json_static, _trigger_stats_recalculation) ...

def init_dictionary_web_routes(dictionary_service):
    """Initialize dictionary web routes with the dictionary service."""
    return dictionary_web_bp

