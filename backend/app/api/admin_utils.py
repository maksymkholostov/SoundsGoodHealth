"""
Temporary admin utilities for data migration and diagnostics.
IMPORTANT: Remove this file after migration is complete!
"""

from flask import Blueprint, jsonify, request, send_file
import os
import shutil
import zipfile
from datetime import datetime
import hashlib
from werkzeug.utils import secure_filename
from pathlib import Path

admin_utils_bp = Blueprint('admin_utils', __name__)

# Secret key for authentication (change this!)
ADMIN_SECRET = "CHANGE_THIS_SECRET_KEY_12345"

def verify_admin_secret(provided_secret):
    """Verify the provided secret matches our admin secret."""
    return provided_secret == ADMIN_SECRET

@admin_utils_bp.route('/api/admin/diagnostics', methods=['POST'])
def diagnostics():
    """Get diagnostic information about the server's data directories."""
    data = request.get_json()
    if not data or not verify_admin_secret(data.get('secret')):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        base_path = Path('backend/data')
        result = {
            'current_directory': os.getcwd(),
            'data_exists': base_path.exists(),
            'directories': {}
        }
        
        if base_path.exists():
            for dir_name in ['sounds', 'models', 'features', 'users']:
                dir_path = base_path / dir_name
                if dir_path.exists():
                    # Count files by extension
                    file_counts = {}
                    total_size = 0
                    
                    for root, dirs, files in os.walk(dir_path):
                        for file in files:
                            ext = os.path.splitext(file)[1].lower()
                            file_counts[ext] = file_counts.get(ext, 0) + 1
                            
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except:
                                pass
                    
                    result['directories'][dir_name] = {
                        'exists': True,
                        'file_counts': file_counts,
                        'total_size_mb': round(total_size / (1024 * 1024), 2),
                        'subdirectories': [d for d in os.listdir(dir_path) if os.path.isdir(dir_path / d)][:10]  # First 10
                    }
                else:
                    result['directories'][dir_name] = {'exists': False}
        
        # Check for volumes
        result['mounts'] = []
        if os.path.exists('/proc/mounts'):
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    if '/app' in line:
                        result['mounts'].append(line.strip())
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_utils_bp.route('/api/admin/upload_sounds', methods=['POST'])
def upload_sounds():
    """Upload a zip file containing sound files to restore data."""
    # Check secret in form data
    if not verify_admin_secret(request.form.get('secret')):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Only ZIP files are accepted'}), 400
    
    try:
        # Save uploaded file temporarily
        temp_dir = Path('temp_upload')
        temp_dir.mkdir(exist_ok=True)
        
        zip_path = temp_dir / secure_filename(file.filename)
        file.save(str(zip_path))
        
        # Create backup of existing sounds
        sounds_path = Path('backend/data/sounds')
        if sounds_path.exists():
            backup_path = Path(f'backend/data/sounds_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            shutil.copytree(sounds_path, backup_path)
            result_message = f"Backed up existing sounds to {backup_path}"
        else:
            sounds_path.mkdir(parents=True, exist_ok=True)
            result_message = "Created sounds directory"
        
        # Extract zip file
        extracted_files = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith('.wav') or member.endswith('.json'):
                    zip_ref.extract(member, sounds_path)
                    extracted_files.append(member)
        
        # Clean up
        os.remove(zip_path)
        temp_dir.rmdir()
        
        return jsonify({
            'success': True,
            'message': result_message,
            'extracted_files_count': len(extracted_files),
            'sample_files': extracted_files[:10]  # Show first 10 files
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_utils_bp.route('/api/admin/download_sounds', methods=['POST'])
def download_sounds():
    """Download all sounds as a zip file."""
    data = request.get_json()
    if not data or not verify_admin_secret(data.get('secret')):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        sounds_path = Path('backend/data/sounds')
        if not sounds_path.exists():
            return jsonify({'error': 'No sounds directory found'}), 404
        
        # Create zip file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f'sounds_backup_{timestamp}.zip'
        zip_path = Path('temp') / zip_filename
        zip_path.parent.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(sounds_path):
                for file in files:
                    if file.endswith(('.wav', '.json')):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, sounds_path)
                        zip_file.write(file_path, arcname)
        
        # Return file info instead of sending file directly
        return jsonify({
            'success': True,
            'filename': zip_filename,
            'size_mb': round(os.path.getsize(zip_path) / (1024 * 1024), 2)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_utils_bp.route('/api/admin/list_sound_classes', methods=['POST'])
def list_sound_classes():
    """List all sound classes and their file counts."""
    data = request.get_json()
    if not data or not verify_admin_secret(data.get('secret')):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        sounds_path = Path('backend/data/sounds')
        if not sounds_path.exists():
            return jsonify({'classes': [], 'message': 'No sounds directory found'})
        
        classes = []
        for class_dir in sounds_path.iterdir():
            if class_dir.is_dir():
                class_info = {
                    'name': class_dir.name,
                    'users': []
                }
                
                # Check for user directories
                for user_dir in class_dir.iterdir():
                    if user_dir.is_dir():
                        wav_count = len(list(user_dir.rglob('*.wav')))
                        json_count = len(list(user_dir.rglob('*.json')))
                        
                        user_info = {
                            'user_id': user_dir.name,
                            'wav_files': wav_count,
                            'json_files': json_count,
                            'subdirs': [d.name for d in user_dir.iterdir() if d.is_dir()]
                        }
                        class_info['users'].append(user_info)
                
                class_info['total_wav_files'] = sum(u['wav_files'] for u in class_info['users'])
                class_info['total_json_files'] = sum(u['json_files'] for u in class_info['users'])
                classes.append(class_info)
        
        return jsonify({
            'classes': classes,
            'total_classes': len(classes),
            'total_wav_files': sum(c['total_wav_files'] for c in classes),
            'total_json_files': sum(c['total_json_files'] for c in classes)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Register blueprint
def register_admin_utils(app):
    """Register the admin utilities blueprint with the Flask app."""
    app.register_blueprint(admin_utils_bp)