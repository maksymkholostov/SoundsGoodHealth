"""
Flask application configuration for SoundClassifiers v10.

This module configures the Flask application with all necessary components
for serving both the backend API and frontend interface.
"""
import os
import sys
import logging
from flask import render_template, jsonify, send_from_directory, request
from backend.app import create_app
from backend.app.auth.models import User

logger = logging.getLogger(__name__)

def create_test_user(app):
    """Ensure the ronrubin user exists (already created with password123)."""
    try:
        # Check if auth service and user repository are available
        if not hasattr(app, 'auth_service') or not hasattr(app.auth_service, 'user_repo'):
            app.logger.warning("Auth service or user repository not available, skipping user check")
            return
        
        # Get the user repository from the auth service
        user_repo = app.auth_service.user_repo
        
        # Check if ronrubin user already exists
        if user_repo.username_exists('ronrubin'):
            app.logger.info("User 'ronrubin' already exists")
            return
        
        # The user should already exist from the file system
        # Just log that it's missing if it's not there
        app.logger.warning("User 'ronrubin' not found - please check data/users/ronrubin/user_profile.json")
            
    except Exception as e:
        app.logger.error(f"Error creating test user: {str(e)}")

def create_flask_app(config_name='development'):
    """
    Create and configure the Flask application.
    
    Args:
        config_name: Configuration name to use
        
    Returns:
        Configured Flask application
    """
    # Create the base app
    try:
        app = create_app(config_name)
    except Exception as e:
        import traceback
        print(f"Error creating Flask app: {str(e)}")
        print(traceback.format_exc())
        raise
    
    # Configure static files and templates - only if they're not already properly set
    static_path = os.path.join(os.path.dirname(__file__), 'frontend/static')
    template_path = os.path.join(os.path.dirname(__file__), 'frontend/templates')
    
    # Set static and template folders with fallbacks
    if not app.static_folder or app.static_folder == 'static':
        app.static_folder = static_path
    
    if not app.template_folder or app.template_folder == 'templates':
        app.template_folder = template_path
    
    # Ensure config has required keys with fallbacks
    if not app.config.get('STATIC_FOLDER'):
        app.config['STATIC_FOLDER'] = static_path
    
    if not app.config.get('TEMPLATE_FOLDER'):
        app.config['TEMPLATE_FOLDER'] = template_path
    
    # Create test user
    try:
        create_test_user(app)
    except Exception as e:
        logger.error(f"Error setting up test user: {str(e)}")
    
    # Serve favicon.ico from root url
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.ico')
    
    # Add CSS for visualization components
    @app.route('/static/css/visualizations.css')
    def serve_viz_css():
        """Serve the visualization CSS file."""
        # Check if the file exists in the static folder
        css_path = os.path.join(app.static_folder, 'css', 'visualizations.css')
        if os.path.exists(css_path):
            with open(css_path, 'r') as f:
                css = f.read()
            return css, 200, {'Content-Type': 'text/css'}
        
        # Fallback to inline CSS if file doesn't exist
        css = """
        .visualization-container {
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
        
        .visualization-item {
            margin-bottom: 20px;
        }
        
        .visualization-item h3 {
            margin-bottom: 10px;
            color: #333;
        }
        
        .visualization-item img {
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .quality-metrics {
            margin-top: 20px;
        }
        
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .metrics-table th, .metrics-table td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .metrics-table th {
            background-color: #f2f2f2;
        }
        
        /* New visualization styles */
        .sc-visualization-container {
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .sc-visualization-title {
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.2rem;
            color: #333;
        }
        
        .sc-visualization {
            width: 100%;
            min-height: 150px;
            position: relative;
        }
        
        /* Waveform visualization */
        .sc-waveform-container {
            height: 150px;
            background-color: #ffffff;
        }
        """
        return css, 200, {'Content-Type': 'text/css'}
    
    # Frontend routes (if not already defined elsewhere)
    # @app.route('/')
    # def index():
    #     return render_template('index.html')
    
    # Visualization data API endpoints
    @app.route('/api/visualizations/waveform/<recording_id>')
    def waveform_data(recording_id):
        """Return waveform data for visualization."""
        # This would normally fetch data from your backend services
        # For now, return sample data for testing
        return jsonify({
            'recording_id': recording_id,
            'sampling_rate': 16000,
            'samples': [0.0] * 16000  # Placeholder data
        })
    
    @app.route('/api/visualizations/spectrogram/<recording_id>')
    def spectrogram_data(recording_id):
        """Return spectrogram data for visualization."""
        # This would normally fetch data from your backend services
        return jsonify({
            'recording_id': recording_id,
            'data': []  # Placeholder data
        })
    
    # Visualization JS file
    @app.route('/static/js/visualizations.js')
    def serve_viz_js():
        """Serve the visualization JS file."""
        js_path = os.path.join(app.static_folder, 'js', 'visualizations.js')
        if os.path.exists(js_path):
            with open(js_path, 'r') as f:
                js = f.read()
            return js, 200, {'Content-Type': 'application/javascript'}
        
        # Fallback to inline basic JS if file doesn't exist
        js = """
        /**
         * SoundClassifiers v10 - Basic Visualization Components
         */
        
        // Will be expanded in the full implementation file
        const SCVisualizations = {
            init: function() {
                console.log('Initializing basic visualizations');
                // Find elements with data-visualization attribute
                const elements = document.querySelectorAll('[data-visualization]');
                elements.forEach(el => {
                    const type = el.dataset.visualization;
                    const id = el.dataset.audioId;
                    if (type === 'waveform' && id) {
                        this.createWaveform(el, id);
                    }
                });
            },
            
            createWaveform: function(container, audioId) {
                container.innerHTML += '<div class="sc-waveform-container"><p>Waveform visualization will appear here</p></div>';
                // In the full implementation, this would fetch data and render a canvas
            }
        };
        
        document.addEventListener('DOMContentLoaded', function() {
            SCVisualizations.init();
        });
        """
        return js, 200, {'Content-Type': 'application/javascript'}
    
    # Add a debug route to see all registered routes
    @app.route('/debug/routes')
    def list_routes():
        """List all registered routes for debugging."""
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'route': str(rule)
            })
        return jsonify(routes)
    
    # Error handlers for debugging
    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors with more information."""
        if request.path.startswith('/static/'):
            # More detailed error for static file issues
            file_path = request.path[8:]  # Remove '/static/' prefix
            static_path = os.path.join(app.static_folder, file_path)
            exists = os.path.exists(static_path)
            
            return jsonify({
                "error": "Static file not found",
                "path": request.path,
                "full_path": static_path,
                "exists": exists,
                "static_folder": app.static_folder
            }), 404
            
        return jsonify({
            "error": "Page not found",
            "path": request.path,
            "available_rules": [str(rule) for rule in app.url_map.iter_rules()]
        }), 404
    
    @app.errorhandler(500)
    def server_error(e):
        """Handle 500 errors with more information."""
        import traceback
        
        return jsonify({
            "error": "Internal server error",
            "details": str(e),
            "traceback": traceback.format_exc()
        }), 500
    
    return app

# Create the application
app = create_flask_app()

# Add debug routes for Railway deployment
@app.route('/api/healthz')
def healthz():
    """Simple health endpoint for Railway health checks."""
    return jsonify({"status": "ok"}), 200

@app.route('/debug/model_paths')
def debug_model_paths():
    """Debug endpoint to check model paths and files on Railway."""
    results = {
        'base_dir': str(os.path.dirname(os.path.abspath(__file__))),
        'cwd': os.getcwd(),
        'data_paths': {},
        'models': []
    }
    
    # Check data directories
    data_dirs = [
        'models',
        'backend/data/models',
        'data/models'
    ]
    
    for directory in data_dirs:
        dir_path = os.path.join(os.getcwd(), directory)
        results['data_paths'][directory] = {
            'exists': os.path.exists(dir_path),
            'is_dir': os.path.isdir(dir_path) if os.path.exists(dir_path) else False
        }
        
        # If directory exists, list model files
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith('.h5') or file.endswith('.pkl') or file.endswith('.joblib'):
                        results['models'].append({
                            'path': os.path.join(root, file),
                            'size': os.path.getsize(os.path.join(root, file))
                        })
    
    return jsonify(results)

# Make sure test user exists, but only if this file is being run directly
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
