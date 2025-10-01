# backend/app/routes/__init__.py
"""
Initializes and registers all blueprints for the application routes package.
"""
import logging

# Import blueprint instances from their respective files within this package
from .auth_routes import auth_web_bp
from .core_web_routes import core_web_bp
from .dictionary_routes import dictionary_web_bp
from .class_routes import class_bp
from .recording_routes import recording_web_bp
from .training_routes import training_web_bp
from .inference_routes import inference_web_bp
from .analysis_routes import analysis_web_bp
from .augmentation_routes import augmentation_bp
from .admin_routes import admin_bp
from .stats_api_routes import stats_api_bp
from .user_routes import user_bp
from .file_routes import file_bp
from .feature_routes import feature_bp
# Optional: Define a list of all blueprints for easier management
all_blueprints = [
    auth_web_bp,
    core_web_bp,
    dictionary_web_bp,
    class_bp,
    recording_web_bp,
    training_web_bp,
    inference_web_bp,
    analysis_web_bp,
    augmentation_bp,
    admin_bp,
    stats_api_bp,
    user_bp,
    file_bp,
    feature_bp,
]

def register_all_blueprints(app):
    """
    Registers all the application blueprints with the Flask app instance.

    Args:
        app: The Flask application instance.
    """
    for bp in all_blueprints:
        app.register_blueprint(bp)
        logging.getLogger().info("Registered blueprint: %s", bp.name)

    app.logger.info(f"All {len(all_blueprints)} application blueprints registered.")

