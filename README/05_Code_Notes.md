# Code Notes - SoundClassifiers v10
Updated August 11, 2025

## Project Structure

```
SoundClassifiers_v10/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints for external clients
│   │   ├── auth/          # Authentication models and services
│   │   ├── core/          # Core models and repositories
│   │   ├── ml/            # Machine learning models
│   │   ├── routes/        # Web routes and blueprints
│   │   ├── services/      # Business logic services
│   │   └── storage/       # File management
│   └── data/              # Data storage root
├── frontend/
│   ├── static/            # CSS, JS, images
│   └── templates/         # HTML templates
├── CSTestProject/         # C# client library and examples
├── Documentation/         # Consolidated documentation
├── flask_app.py          # Main Flask application
├── wsgi.py              # WSGI entry point
├── run.py               # Development runner
└── requirements.txt     # Python dependencies
```

## File Naming Conventions

### Sound File IDs and Paths

#### Classes
- **Storage**: `data/classes/global_registry.json`
- **ID Format**: `cls_<lowercase_name>`
- **Examples**: `cls_eh`, `cls_oo`, `cls_ah`

#### Users
- **Storage**: `data/users/<username>.json`
- **ID Format**: Username string (NOT UUID)
- **Email Index**: `data/users/email_index.json`
- **Noise Profile**: `data/users/<username>/noise_profile.wav`

#### Sound Recordings

**Base Path**: `data/sounds/<class_name>/<username>/<recording_type>/`

**IMPORTANT**: Username is currently hardcoded as "ronrubin" in FileManager.py Line 124

##### Recording Types and Patterns

1. **Gold Recordings**
   - Path: `data/sounds/<class_name>/ronrubin/gold/`
   - Pattern: `<ClassName>_<UUID1>_<UUID2>_gold_seg_<SegNum>.[wav|json]`
   - ID in JSON: `seg_<UUID2>_<SegNum>`

2. **Augmented Recordings**
   - Path: `data/sounds/<class_name>/ronrubin/augmented/`
   - Pattern: `aug_<UUID>.[wav|json]`
   - ID in JSON: `aug_<UUID>`

3. **Pending Recordings**
   - Path: `data/sounds/<class_name>/ronrubin/pending/`
   - Pattern: `<ClassName>_<UUID1>_<UUID2>_pending_seg_<SegNum>.[wav|json]`

4. **Raw Recordings**
   - Recorded: `data/sounds/<class_name>/ronrubin/raw_recorded/`
   - Uploaded: `data/sounds/<class_name>/ronrubin/raw_uploaded/`
   - Pattern: `rec_<UUID>_raw.[wav|json]`

### Features
- **Path**: `data/features/<version>/<dictionary_id>/<type>/<class_name>/`
- **Pattern**: `<recording_id>_features.npz`
- **Types**: `gold`, `augmented`, `unknown`
- **Version**: Currently `v0.1`

### Models
- **Path**: `data/models/<dictionary_id>/<model_type>_<timestamp>/`
- **Files**: `model.pkl`, `metadata.json`, `scaler.pkl`, `encoder.pkl`
- **Model Types**: `RF`, `CNN`, `SVM`, `ENSEMBLE`

### Dictionaries
- **Storage**: `data/dictionaries/system_dictionaries.json`
- **ID Format**: `<dictionary_id>` (UUID format)

## Database Schema

### Key Models

#### User
```python
class User:
    id: str           # Username
    username: str     # Unique username
    email: str        # Email address
    password_hash: str
    is_admin: bool
    created_at: datetime
```

#### SoundClass
```python
class SoundClass:
    id: str           # cls_<name>
    name: str         # Display name
    description: str
    created_at: datetime
    creator_uid: str  # Username
```

#### Dictionary
```python
class Dictionary:
    id: str           # UUID
    name: str
    description: str
    class_ids: List[str]
    created_at: datetime
    creator_uid: str
```

#### Recording
```python
class Recording:
    id: str           # seg_<uuid>_<num>
    class_id: str     # cls_<name>
    user_id: str      # Username
    file_path: str
    status: str       # 'pending', 'gold', 'discarded'
    metadata: dict
```

## Critical Code Patterns

### Service Initialization Order (backend/app/__init__.py)
1. FileManager must be attached to app immediately
2. Repositories created before services
3. Services require specific dependencies:
   - DictionaryService(dictionary_repository)
   - RecordingService(recording_repository, dictionary_repository, file_service)
   - AuthService(user_repository)

### File Path Resolution
All file operations go through FileManager:
```python
file_manager = app.file_manager
path = file_manager.get_gold_sound_path(class_name, user_id)
```

### Model Training Flow
1. Feature extraction (automatic if missing)
2. Data loading and validation
3. Model training with specified parameters
4. Model saving with metadata
5. Cleanup of temporary files

### API Authentication
- Session-based for web interface
- API token via X-API-Token header
- Model ID for custom speech API

## Known Issues and TODOs

### Current Limitations
1. **Hardcoded Username**: FileManager uses "ronrubin" (Line 124)
2. **CNN Performance**: Currently underperforming, needs optimization
3. **Ensemble Models**: Dependent on CNN improvements
4. **Feature Version**: Locked to v0.1, no migration path yet

### Technical Debt
1. **Database**: Currently using file-based storage, should migrate to proper DB
2. ~~**Async Operations**: Long-running tasks block the main thread~~ **RESOLVED** - Implemented SSE and batch processing (Aug 11, 2025)
3. **File Cleanup**: Temporary files not always cleaned properly
4. **Error Handling**: Inconsistent error responses across endpoints

### Future Improvements
1. Multi-user file storage support
2. Background job queue for training (partially addressed with SSE)
3. ~~Real-time training progress via WebSockets~~ **IMPLEMENTED** - Using SSE for real-time updates (Aug 11, 2025)
4. Automated model performance tracking
5. Feature version migration system

## Environment Variables

### Required
```bash
FLASK_APP=flask_app.py
FLASK_ENV=production
SECRET_KEY=<secure_random_key>
DATABASE_URL=<database_connection_string>
DATA_ROOT=/app/backend/data
```

### Optional
```bash
DEFAULT_MODEL_TYPE=RF
ENABLE_DEBUG_ROUTES=false
MAX_UPLOAD_SIZE=10485760  # 10MB
FEATURE_VERSION=v0.1
```

## Common Operations

### Adding a New Model Type
1. Create trainer in `backend/app/ml/training/`
2. Create predictor in `backend/app/ml/inference/`
3. Register in `TrainingService.SUPPORTED_MODEL_TYPES`
4. Update frontend model selection UI

### Modifying File Storage
1. Update paths in `FileManager`
2. Create migration script for existing files
3. Update all service references
4. Test with existing data

### Adding New API Endpoint
1. Create route in appropriate blueprint
2. Add service method if needed
3. Update API documentation
4. Add tests
5. Update C# client if applicable

## Debugging Tips

### Check File Paths
```python
# In Python shell
from flask_app import app
fm = app.file_manager
print(fm.data_root)
print(fm.get_gold_sound_path("Eh", "ronrubin"))
```

### Verify Model Files
```bash
ls -la backend/data/models/*/
find backend/data/models -name "*.pkl"
```

### Track Feature Extraction
```python
# Check feature files
find backend/data/features -name "*.npz" | wc -l
```

### Monitor Training
- Check logs for "Training started" messages
- Look for model save confirmations
- Verify metadata.json creation

## Security Considerations

1. **File Upload**: Validate file types and sizes
2. **Path Traversal**: Use os.path.join, never concatenate
3. **User Isolation**: Ensure users can't access others' data
4. **API Keys**: Never log or expose in responses
5. **Audio Processing**: Sanitize filenames, validate formats

## Performance Notes

### Bottlenecks (UPDATED Aug 11, 2025)
1. ~~Feature extraction for large datasets~~ **RESOLVED** - Batch processing with SSE progress
2. Model training without GPU support
3. File I/O for augmentation operations
4. ~~Sequential processing of recordings~~ **RESOLVED** - Parallel processing with ThreadPoolExecutor

### Implemented Optimizations (Aug 11, 2025)

#### Feature Extraction Performance
- **Problem**: Taking 10+ minutes for 1200 sounds with no feedback
- **Solution**: Implemented in `backend/app/routes/feature_routes_improved.py`
  - Batch processing (5-10 files at a time)
  - Server-Sent Events for real-time progress
  - 5-second response caching
  - Parallel processing with ThreadPoolExecutor
  - AJAX-based status checks (no page reloads)

#### Training Data Loading
- **Problem**: Training hanging forever in "Data Preparation" phase
- **Solution**: Implemented in `backend/app/services/training_service_optimized.py`
  - Memory-mapped numpy arrays (mmap mode)
  - Batch loading (50 features at a time)
  - 4 parallel workers for loading
  - Automatic garbage collection after batches
  - Progress tracking during data preparation

#### UI Responsiveness
- **Problem**: Page freezing, 20+ minute reloads, browser crashes
- **Solution**: Implemented in `frontend/static/js/training_improved.js`
  - No page reloads for dictionary selection
  - Real-time progress updates via SSE
  - Visual progress bars and status messages
  - Better error handling and recovery

### Performance Results
- Feature extraction: 10+ min → 5-10 min with progress
- Status checks: 20+ min freezes → Instant (cached)
- Training prep: Hanging → Smooth with progress
- Memory usage: Crashes → Stable batch processing

### Original Optimizations (Still Active)
1. Cache extracted features
2. Batch process recordings
3. Use multiprocessing for CPU-intensive tasks
4. Implement pagination for large result sets

## Recent Changes Log

### August 11, 2025 - Performance Optimization Update
- Added `feature_routes_improved.py` for optimized feature extraction
- Added `training_service_optimized.py` for optimized training data loading
- Added `training_improved.js` and `training_api_optimized.js` for UI updates
- Integrated optimizations into `backend/app/__init__.py`
- Resolved major performance bottlenecks (see Performance Notes above)

---

*Last Updated: August 11, 2025*
*Code Version: v10.1 (with performance optimizations)*