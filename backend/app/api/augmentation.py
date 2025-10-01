"""
API endpoints for audio augmentation functionality.

This module provides API endpoints for managing sound augmentation operations.
"""
from flask import Blueprint, request, jsonify, current_app, session
from werkzeug.exceptions import BadRequest
from flask_login import login_required, current_user

# Create blueprint
augmentation_api = Blueprint('augmentation_api', __name__)

@augmentation_api.route('/status/<string:dictionary_id>/<string:class_name>', methods=['GET'])
# DB-OPERATION: read dictionary
def get_augmentation_status(dictionary_id, class_name):
    """
    Get the augmentation status for a specific class in a dictionary.
    
    This endpoint returns information about which gold standard recordings
    have been augmented and how many augmentations exist for each.
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get augmentation status from service
        status = current_app.augmentation_service.get_augmentation_status(
            user_id, dictionary_id, class_name)
        
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error getting augmentation status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@augmentation_api.route('/perform', methods=['POST'])
def perform_augmentation():
    """
    Perform augmentation on selected recordings.
    
    This endpoint accepts a list of recordings to augment and configuration
    parameters for the augmentation process.
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.json
        if not data:
            raise BadRequest("Missing request data")
        
        dictionary_id = data.get('dictionary_id')
        if not dictionary_id:
            raise BadRequest("Missing dictionary_id")
        
        # Check if this is a request to augment all classes
        include_all_classes = data.get('include_all_classes', False)
        class_name = data.get('class_name', 'all') if include_all_classes else data.get('class_name')
        
        if not include_all_classes and not class_name:
            raise BadRequest("Missing class_name")
        
        # Get number of augmentations to create
        num_augmentations = int(data.get('num_augmentations', 5))
        
        # Get custom configuration, if provided
        config = data.get('config', {})
        
        # Check if specific recordings are provided
        recording_ids = data.get('recording_ids', [])
        
        # Perform augmentation
        if include_all_classes:
            # Augment all classes in the dictionary
            result = current_app.augmentation_service.generate_augmentations(
                user_id, dictionary_id, class_name, 
                num_augmentations=num_augmentations,
                include_all_classes=True,
                config=config
            )
        elif recording_ids:
            # Augment specific recordings
            results = []
            for recording_id in recording_ids:
                result = current_app.augmentation_service.augment_single_recording(
                    user_id, dictionary_id, class_name, recording_id, 
                    num_augmentations=num_augmentations
                )
                results.append(result)
            result = {
                "augmented_recordings": len(results),
                "results": results
            }
        else:
            # Augment all recordings for a class
            result = current_app.augmentation_service.generate_augmentations(
                user_id, dictionary_id, class_name, 
                num_augmentations=num_augmentations,
                config=config
            )
        
        return jsonify(result)
    except BadRequest as e:
        current_app.logger.error(f"Bad request: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error performing augmentation: {str(e)}")
        return jsonify({"error": str(e)}), 500

@augmentation_api.route('/class-counts')
@login_required
# DB-OPERATION: read sound_class
def get_augmentation_class_counts():
    """Get class counts for a selected target."""
    try:
        target_type = request.args.get('type', 'dictionary')
        target_id = request.args.get('target_id')
        
        # Get the user ID from the current logged-in user
        user_id = current_user.id
        
        current_app.logger.info(f"Getting class counts for {target_type} {target_id}")
        
        if not target_id:
            return jsonify({
                'success': False,
                'error': 'No target ID provided'
            }), 400
            
        max_count = 0
        class_counts = {}
        
        if target_type == 'dictionary':
            # Get all classes in the dictionary
            try:
                dictionary = current_app.dictionary_service.get_dictionary(user_id, target_id)
                if not dictionary:
                    current_app.logger.warning(f"Dictionary {target_id} not found for user {user_id}")
                    return jsonify({
                        'success': False,
                        'error': f'Dictionary {target_id} not found'
                    }), 404
            except Exception as dict_error:
                current_app.logger.error(f"Error getting dictionary: {str(dict_error)}")
                return jsonify({
                    'success': False,
                    'error': f'Error accessing dictionary: {str(dict_error)}'
                }), 500
                
            # Handle dictionary being either an object or dict
            if hasattr(dictionary, 'classes'):
                classes = [cls.name for cls in dictionary.classes]
            else:
                classes = dictionary.get('classes', [])
                
            current_app.logger.info(f"Found {len(classes)} classes in dictionary {target_id}")
                
            # Get counts for each class
            for class_name in classes:
                try:
                    # Get gold recordings
                    gold_recordings = current_app.recording_service.get_gold_recordings(user_id, target_id, class_name)
                    gold_count = len(gold_recordings) if gold_recordings else 0
                    
                    # Get augmented recordings
                    augmented_recordings = current_app.augmentation_service.get_augmented_recordings(user_id, target_id, class_name)
                    augmented_count = len(augmented_recordings) if augmented_recordings else 0
                    
                    # Calculate total
                    total_count = gold_count + augmented_count
                    
                    class_counts[class_name] = {
                        'gold': gold_count,
                        'augmented': augmented_count,
                        'total': total_count
                    }
                    
                    max_count = max(max_count, total_count)
                except Exception as class_error:
                    current_app.logger.error(f"Error processing class {class_name}: {str(class_error)}")
            
        current_app.logger.info(f"Returning class counts with max count: {max_count}")
        return jsonify({
            'success': True,
            'class_counts': class_counts,
            'max_count': max_count
        })
    except Exception as e:
        current_app.logger.error(f"Error getting class counts: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@augmentation_api.route('/start', methods=['POST'])
@login_required
def start_augmentation():
    """Start an augmentation process with specified parameters."""
    try:
        data = request.get_json()
        target_type = data.get('target_type')
        target_id = data.get('target_id')
        strategy = data.get('strategy', 'add_fixed')
        fixed_number = data.get('fixed_number', 5)
        equalize_target = data.get('equalize_target')  # Get the custom equalize target if provided
        config = data.get('config', {})  # Get augmentation configuration
        
        # Get the user ID from the current logged-in user
        user_id = current_user.id
        
        current_app.logger.info("Starting augmentation: type=%s, target=%s, strategy=%s, config=%s", 
                               target_type, target_id, strategy, config)
        
        # Validate target type
        if target_type not in ['dictionary', 'class']:
            current_app.logger.error(f"Invalid target type: {target_type}")
            return jsonify({
                'success': False,
                'error': f"Unknown target type: {target_type}"
            }), 400
            
        # Process based on strategy
        try:
            if strategy == 'add_fixed':
                # Fixed number of augmentations per recording
                if target_type == 'dictionary':
                    result = current_app.augmentation_service.augment_dictionary(
                        user_id, target_id, 
                        num_augmentations_per_sample=fixed_number,
                        equalize_total=False
                    )
                elif target_type == 'class':
                    # Parse dictionary ID and class name from target_id
                    dict_id, class_name = target_id.split(':')
                    result = current_app.augmentation_service.generate_augmentations(
                        user_id, dict_id, class_name, 
                        num_augmentations=fixed_number,
                        include_all_classes=False,
                        config=config
                    )
            
            elif strategy == 'equalize':
                # Equalize classes to have similar sample counts
                if target_type == 'dictionary':
                    result = current_app.augmentation_service.augment_dictionary(
                        user_id, target_id, 
                        equalize_total=True,
                        equalize_target=equalize_target
                    )
                elif target_type == 'class':
                    # Parse dictionary ID and class name from target_id
                    dict_id, class_name = target_id.split(':')
                    result = current_app.augmentation_service.generate_augmentations(
                        user_id, dict_id, class_name, 
                        include_all_classes=True,
                        equalize_total=True,
                        equalize_target=equalize_target,
                        config=config
                    )
            else:
                raise ValueError(f"Invalid strategy: {strategy}")
        except Exception as inner_e:
            current_app.logger.error("Unexpected error during augmentation: %s", str(inner_e), exc_info=True)
            return jsonify({
                'success': False,
                'error': f"Unexpected error: {str(inner_e)}"
            }), 500
        
        if not result:
            return jsonify({
                'success': False, 
                'error': 'Failed to start augmentation - no result returned'
            }), 500
            
        current_app.logger.info("Augmentation completed successfully")
        return jsonify({
            'success': True,
            'result': result
        })
    except ValueError as ve:
        current_app.logger.error("Validation error in augmentation request: %s", str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error("Error starting augmentation: %s", str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@augmentation_api.route('/options', methods=['GET'])
@login_required
# DB-OPERATION: read unknown
def get_augmentation_options():
    """Get available augmentation methods and their parameters."""
    try:
        options = current_app.augmentation_service.get_augmentation_options()
        return jsonify({
            'success': True,
            'options': options
        })
    except Exception as e:
        current_app.logger.error(f"Error getting augmentation options: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def init_augmentation_routes(augmentation_service):
    """
    Initialize augmentation API routes with required services.
    
    Args:
        augmentation_service: Instance of AugmentationService
        
    Returns:
        Configured Blueprint
    """
    return augmentation_api 