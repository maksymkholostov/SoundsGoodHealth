import os
import inspect

import logging
from flask import Flask, session, Blueprint, url_for, redirect, request, current_app, g
from logging.handlers import RotatingFileHandler
from datetime import timedelta, datetime
from flask_jwt_extended import JWTManager
from flask_login import LoginManager, current_user
from flask_moment import Moment

from .core.repositories.dictionary_repo import DictionaryRepository
from .core.repositories.recording_repo import RecordingRepository
from .core.repositories.feature_repo import FeatureRepository
from .core.repositories.model_repo import ModelRepository
from .core.repositories.user_repo import UserRepository

from .storage.file_manager import FileManager
from .services.file_service import FileService
from .services.dictionary_service import DictionaryService
from .services.recording_service import RecordingService
from .services.processing_service import ProcessingService
from .services.feature_service import FeatureService
from .services.training_service import TrainingService
from .services.inference_service import InferenceService
from .auth.service import AuthService
from .services.augmentation_service import AugmentationService
from .auth.models import User
from .analysis.training_analyzer import TrainingAnalyzer

# Add imports for audio preprocessing
from .ml.preprocessing.segmentation import AudioSegmenter
from .ml.preprocessing.normalization import AudioNormalizer
from .ml.preprocessing.filtering import AudioFilter

# Import admin utilities (temporary)
from .api.admin_utils import admin_utils_bp

from .services.developer_tools_service import DeveloperToolsService
from .services.system_service import SystemService
from .routes.developer_routes import developer_bp
from backend.app.routes.user_routes import user_bp
import backend.app.routes.dictionary_routes 
from backend.app.routes.file_routes import file_bp
from backend.app.routes.feature_routes import feature_bp

# Import optimized routes
try:
    from backend.app.routes.feature_routes_improved import feature_improved_bp
    from backend.app.routes.training_routes_improved import training_improved_bp
except ImportError:
    feature_improved_bp = None
    training_improved_bp = None

# DB-OPERATION: create unknown
def create_app(config_name=None):
    """
    Application factory for creating Flask application instances
    with different configurations based on environment.
    
    Args:
        config_name: Name of configuration to use (development, production, testing)
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
                
    # Configure app
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # TODO: Fix config imports - they seem to be causing errors unrelated to routes
    if config_name == 'development':
        from backend.config.development import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)
    elif config_name == 'production':
        from backend.config.production import ProductionConfig
        app.config.from_object(ProductionConfig)
    elif config_name == 'testing':
        from backend.config.testing import TestingConfig
        app.config.from_object(TestingConfig)
    else:
        # Default to development
        from backend.config.development import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)
    
    # Ensure SECRET_KEY is set directly on the app
    app.secret_key = app.config.get('SECRET_KEY', os.urandom(24))
    
    # Explicitly disable Jinja template caching for debugging
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.cache = None # Or set to {} or 0, setting to None disables it

    # Configure logging EARLY to suppress noise during initialization
    configure_logging(app)
    
    # Initialize directories
    # TODO: Fix config import
    # from backend.config import Config 
    # Config.init_directories() # Pass app to init_directories # Commented out as FileManager handles this
    
    # Initialize volume if configured
    from backend.utils.volume_init import init_data_volume, check_volume_status
    
    # Check if we should use volume
    use_volume = os.environ.get('USE_VOLUME', 'false').lower() == 'true'
    if use_volume:
        # Initialize volume and get path
        volume_path = init_data_volume()
        app.config['DATA_ROOT'] = str(volume_path)
        app.logger.info(f"Using Railway volume at: {volume_path}")
        
        # Log volume status
        status = check_volume_status()
        app.logger.info(f"Volume status: {status}")
    
    # Initialize file manager
    file_manager = FileManager(app.config['DATA_ROOT'])

    # Directly attach file_manager to app immediately
    app.file_manager = file_manager

    # Initialize repositories
    dictionary_repository = DictionaryRepository(file_manager)
    recording_repository = RecordingRepository(file_manager, dictionary_repository)
    user_repository = UserRepository(file_manager)
    feature_repository = FeatureRepository(file_manager)
    model_repository = ModelRepository(file_manager)
    auth_service = AuthService(user_repository)
    # Initialize services
    file_service = FileService(file_manager)
    dictionary_service = DictionaryService(dictionary_repository)

    

    recording_service = RecordingService(
        recording_repo=recording_repository, 
        dictionary_repo=dictionary_repository, 
        file_service=file_service
    )
    processing_service = ProcessingService(recording_repository, file_service, dictionary_repository)
    augmentation_service = AugmentationService(file_manager, recording_repository, dictionary_service, user_repository)
    feature_service = FeatureService(feature_repository, recording_repository, file_service, dictionary_repository)
    # Ensure default feature set exists
    if feature_service.get_feature_set('v0.1') is None:
        app.logger.info("Default feature set 'v0.1' not found, creating it.")
        try:
            feature_service.create_default_feature_set()
        except Exception as fe_e:
            app.logger.error(f"Failed to create default feature set: {fe_e}", exc_info=True)

    # Instantiate TrainingAnalyzer
    training_analyzer = TrainingAnalyzer() 

    # Correct TrainingService instantiation with all required args
    # Make sure the required arguments match the TrainingService.__init__ signature
    # Example: Assuming it needs dict_repo, feat_repo, model_repo, file_service, aug_service
    training_service = TrainingService(
        dictionary_repo=dictionary_repository, # Use the created repo instance
        feature_repo=feature_repository,       # Use the created repo instance
        model_repo=model_repository,           # Use the created repo instance
        recording_repo=recording_repository,   # Added missing repo instance
        file_service=file_service,             # Use the created service instance
        augmentation_service=augmentation_service, # Use the created service instance
        training_analyzer=training_analyzer      # Pass the analyzer instance
    )
    
    # Create optimized training service wrapper if available
    optimized_training_service = None
    try:
        from backend.app.services.training_service_optimized import OptimizedTrainingService
        optimized_training_service = OptimizedTrainingService(training_service)
        app.logger.info("Optimized training service initialized")
    except ImportError:
        app.logger.warning("Optimized training service not available")
    inference_service = InferenceService(model_repository, feature_repository, dictionary_repository, file_service, feature_service)
    developer_tools_service = DeveloperToolsService(file_manager, user_repository, dictionary_repository)
    system_service = SystemService(file_manager, dictionary_repository, user_repository, recording_repository)
    
    # Import developer blueprint directly (no init function exists)
    from backend.app.routes.developer_routes import developer_bp
    
    # Initialize API routes
    from backend.app.api.admin import init_admin_routes
    admin_api_bp = init_admin_routes(system_service)
    
    # Initialize WebUI routes
    from backend.app.api.custom_speech import init_custom_speech_routes
    custom_speech_api_bp = init_custom_speech_routes(
        inference_service=inference_service,
        model_repo=model_repository if hasattr(app, 'model_repository') else None
    )
    
    from backend.app.routes.auth_routes import init_auth_web_routes
    auth_web_bp = init_auth_web_routes(auth_service)
    
    from backend.app.routes.core_web_routes import init_core_web_routes
    core_web_bp = init_core_web_routes(dictionary_service, recording_service)
    
    from backend.app.routes.class_routes import init_class_web_routes
    class_web_bp = init_class_web_routes(dictionary_service)
    
    # --- DEBUG: Check dictionary_routes import path and content ---
    try:
        print(f"--- DEBUG: App importing dictionary_routes from: {backend.app.routes.dictionary_routes.__file__} ---")
        with open(backend.app.routes.dictionary_routes.__file__, 'r') as f_check:
             print(f"--- DEBUG: First line of that file: {f_check.readline().strip()} ---")
    except Exception as e_debug:
        print(f"--- DEBUG: Error inspecting dictionary_routes: {e_debug} ---")
    # --- END DEBUG ---

    from backend.app.routes.dictionary_routes import init_dictionary_web_routes
    dictionary_web_bp = init_dictionary_web_routes(dictionary_service)
    
    from backend.app.routes.recording_routes import init_recording_web_routes
    recording_web_bp = init_recording_web_routes(recording_service, processing_service)
    
    from backend.app.routes.training_routes import init_training_web_routes
    training_web_bp = init_training_web_routes(training_service)
    
    # Import and register the blueprint directly
    from backend.app.routes.augmentation_routes import augmentation_bp
    # augmentation_web_bp = init_augmentation_web_routes(augmentation_service) # Removed this line
    
    from backend.app.routes.inference_routes import init_inference_web_routes
    inference_web_bp = init_inference_web_routes(inference_service)
    
    # Initialize game routes
    from backend.app.routes.game_routes import init_game_routes
    game_bp = init_game_routes()
    
    # Initialize API routes
    from backend.app.api.recordings import init_recording_routes
    recording_api_bp = init_recording_routes(recording_service, processing_service)
    
    # from backend.app.api.dictionaries import init_dictionary_routes
    # dictionary_api_bp = init_dictionary_routes(dictionary_service)
    
    from backend.app.api.training import init_training_routes
    training_api_bp = init_training_routes(training_service)
    
    from backend.app.api.inference import init_inference_routes
    from backend.app.api.prediction_events import init_prediction_events_routes
    inference_api_bp = init_inference_routes(inference_service)
    prediction_events_bp = init_prediction_events_routes()
    
    from backend.app.api.augmentation import init_augmentation_routes
    from backend.app.api.id_mappings import init_id_mappings_routes
    augmentation_api_bp = init_augmentation_routes(augmentation_service)
    id_mappings_api_bp = init_id_mappings_routes()
    
    from backend.app.api.auth import init_auth_routes
    auth_api_bp = init_auth_routes(auth_service)
    
    from backend.app.routes.stats_api_routes import stats_api_bp
    
    # Use get() with fallback for configuration values
    app.static_folder = app.config.get('STATIC_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend/static'))
    app.template_folder = app.config.get('TEMPLATE_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend/templates'))
    
    
    
    # Set session lifetime
    app.permanent_session_lifetime = timedelta(hours=5)
    
    # Register extensions
    # jwt = JWTManager(app) # Removed as it seems unused
    JWTManager(app) # Initialize JWTManager but don't assign if unused
    login_manager = LoginManager()
    login_manager.init_app(app)
    # Update login view to use the correct blueprint name from auth_routes.py
    login_manager.login_view = 'auth_web.login_page' 
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    # Set session protection to strong to prevent session hijacking
    login_manager.session_protection = "strong"
    
    # Initialize Flask-Moment
    moment = Moment(app) # Initialize Moment after app and other extensions
    
    @login_manager.user_loader
    # read user
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        try:
            # Get user from repository
            user = user_repository.get_by_id(user_id)
            
            # If we got a dictionary rather than User object, convert it
            if isinstance(user, dict):
                user = User.from_dict(user)
                
            return user
        except Exception as e:
            app.logger.error("Error loading user %s: %s", user_id, str(e))
            return None

    @app.context_processor
    def inject_user_view_settings():
        """Injects user role and view settings into templates."""
        is_admin = False
        current_view_all_mode = False
        user_logged_in = False
    
        from flask_login import current_user # Keep import inside if needed for context
        if current_user.is_authenticated:
            user_logged_in = True
            # Log session contents for debugging
            app.logger.debug(f"Session items for context processor: {dict(session.items())}") 
            is_admin = session.get('is_admin', False) 
            current_view_all_mode = session.get('view_all_mode', False) 
    
        allow_non_admin_global = current_app.config.get('ALLOW_ALL_USERS_VIEW_FOR_NON_ADMINS', False)
        can_toggle_view = is_admin or allow_non_admin_global

        # --- DEBUG LOGGING ---
        app.logger.debug(f"[ContextInject] user_logged_in: {user_logged_in}")
        app.logger.debug(f"[ContextInject] is_admin: {is_admin}")
        app.logger.debug(f"[ContextInject] allow_global_view: {allow_non_admin_global}")
        app.logger.debug(f"[ContextInject] can_toggle_view: {can_toggle_view}")
        app.logger.debug(f"[ContextInject] current_view_all_mode: {current_view_all_mode}")
        # --- END DEBUG ---

        return dict(
            user_logged_in=user_logged_in,
            is_admin=is_admin,
            allow_global_view=allow_non_admin_global,
            can_toggle_view=can_toggle_view,
            current_view_all_mode=current_view_all_mode 
        )

    # Add this filter function
    def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
        """Format a datetime object for display."""
        if value is None:
            return ""
        if isinstance(value, str):
            # Attempt to parse if it's a string (e.g., from JSON)
            try:
                value = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return value # Return original string if parsing fails
        if isinstance(value, datetime):
            return value.strftime(format)
        return value # Return as-is if not a datetime object

    # Attach services to app
    app.file_service = file_service
    app.dictionary_service = dictionary_service
    app.recording_service = recording_service
    app.processing_service = processing_service
    app.feature_service = feature_service
    app.training_service = training_service
    app.optimized_training_service = optimized_training_service
    app.inference_service = inference_service
    app.auth_service = auth_service
    app.augmentation_service = augmentation_service
    app.developer_tools_service = developer_tools_service
    app.system_service = system_service
    
    # Attach repositories needed by routes/services directly
    app.dictionary_repository = dictionary_repository
    app.recording_repository = recording_repository
    app.feature_repository = feature_repository
    app.model_repository = model_repository # Attach model repo if needed elsewhere
    app.user_repository = user_repository   # Attach user repo if needed elsewhere
    # app.file_manager is already attached earlier

    # Import the central blueprint registration function
    # from .routes import register_all_blueprints
    
    # Register API blueprints
    app.register_blueprint(recording_api_bp)
    #app.register_blueprint(dictionary_api_bp)
    app.register_blueprint(training_api_bp)
    app.register_blueprint(inference_api_bp)
    app.register_blueprint(prediction_events_bp)
    app.register_blueprint(augmentation_api_bp)
    app.register_blueprint(id_mappings_api_bp)
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(stats_api_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(feature_bp)
    
    # Register optimized blueprints if available
    if feature_improved_bp:
        app.register_blueprint(feature_improved_bp)
        app.logger.info("Registered feature_improved_bp")
    if training_improved_bp:
        app.register_blueprint(training_improved_bp)
        app.logger.info("Registered training_improved_bp")
    
    app.register_blueprint(custom_speech_api_bp)
    
    # Register admin cleanup routes
    from backend.app.routes.admin_cleanup_routes import admin_cleanup_bp
    app.register_blueprint(admin_cleanup_bp)
    
    # Register debug routes
    from backend.app.routes.debug_routes import debug_bp
    app.register_blueprint(debug_bp)
    
    # Register web application blueprints
    app.register_blueprint(auth_web_bp)
    app.register_blueprint(core_web_bp)
    app.register_blueprint(class_web_bp)
    app.register_blueprint(dictionary_web_bp)
    app.register_blueprint(recording_web_bp)
    app.register_blueprint(training_web_bp)
    app.register_blueprint(augmentation_bp)
    app.register_blueprint(inference_web_bp)
    app.register_blueprint(game_bp)
    
    # Register the filter with the Jinja environment
    app.jinja_env.filters['format_datetime'] = format_datetime_filter
    
    # TEMPORARY: Admin utilities for migration
    app.register_blueprint(admin_utils_bp)
    
    # Clear Jinja template cache to prevent stale blueprint references
    app.jinja_env.cache = {}
    
    # Add before_request handler to enforce login for all pages except auth pages
    @app.before_request
    def check_valid_login():
        # Skip for static files, login, register, logout, favicon, how_it_works, AND API calls
        if (request.endpoint and
            not request.endpoint.startswith('static') and
            request.endpoint != 'auth_web.login_page' and
            request.endpoint != 'auth_web.register_page' and
            request.endpoint != 'auth_web.logout' and
            request.endpoint != 'auth_web.forgot_password' and
            request.endpoint != 'auth_web.reset_password_confirm' and
            request.endpoint != 'core_web.how_it_works_page' and
            not request.path.startswith('/static/') and
            not request.path.startswith('/api/') and
            '/favicon.ico' not in request.path):
            # If user is not authenticated and not requesting excluded pages
            if not current_user.is_authenticated:
                # Log the unauthorized access attempt
                app.logger.warning(f"Unauthorized access attempt to non-API page: {request.path}") # Clarify log
                session.clear()
                return redirect(url_for('auth_web.login_page'))
                
    # Add before_request handler to update user's last_active timestamp
    @app.before_request
    def update_user_activity():
        # Skip for static files, favicon, etc.
        if (request.endpoint and 
            not request.endpoint.startswith('static') and
            not request.path.startswith('/static/') and
            '/favicon.ico' not in request.path):
            # Update activity timestamp for authenticated users
            if current_user.is_authenticated:
                try:
                    # Only update periodically (every 5 minutes) to avoid excessive writes
                    now = datetime.now()
                    last_update = getattr(current_user, 'last_active', None)

                    # --- FIX: Convert last_update from string if necessary ---
                    if isinstance(last_update, str):
                        try:
                            last_update = datetime.fromisoformat(last_update)
                        except (ValueError, TypeError):
                            app.logger.warning(f"Could not parse last_active string '{last_update}' as datetime for user {current_user.id}")
                            last_update = None # Treat as if never updated if parse fails
                    # --- END FIX ---
                    
                    if not last_update or not isinstance(last_update, datetime) or (now - last_update).total_seconds() > 300:  # 5 minutes
                        # Update the user's last_active timestamp
                        current_user.update_activity() # Assumes this sets it to a datetime object
                        
                        # Save the user if we have access to the user repository
                        if hasattr(app, 'auth_service') and app.auth_service:
                            # Ensure the user object being saved has datetime objects
                            # This might require checking the User.to_dict() or repo.save() logic
                            app.auth_service.user_repo.save(current_user) 
                except Exception as e:
                    # Log the specific error type and message
                    app.logger.error(f"Error updating user activity: {type(e).__name__}: {e}") # More specific logging
    
    
    
    # Return the configured app
    return app

def configure_logging(app):
    """Quiet logging: errors only, no duplicate handlers, console only."""
    # Remove any existing handlers to avoid duplicates
    for handler in list(app.logger.handlers):
        app.logger.removeHandler(handler)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Errors only
    app.logger.setLevel(logging.ERROR)
    root_logger.setLevel(logging.ERROR)

    # Console handler (errors only)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    console_handler.setLevel(logging.ERROR)
    app.logger.addHandler(console_handler)

    # Do not propagate to root to prevent duplicate logs
    app.logger.propagate = False

    # Silence noisy third-party or internal loggers
    for name in (
        'werkzeug',
        'tensorflow',
        'urllib3',
        'backend',
        'backend.app',
        'backend.app.storage.file_manager',
        'backend.app.core.repositories',
    ):
        logging.getLogger(name).setLevel(logging.ERROR)

    return app
