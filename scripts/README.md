# Scripts Directory

Updated August 9, 2025

This directory contains utility, testing, and administrative scripts for the SoundClassifiers v10 application.

## Directory Structure

### `/analysis/`
Development tools for analyzing models and performance:
- `check_rf_params.py` - Analyze Random Forest model parameters and memory usage

### `/tests/`
Testing scripts for API and model validation:
- `test_api_backward_compat.py` - Test API backward compatibility
- `test_rf_prediction.py` - Test Random Forest model predictions
- `test_train_cnn1d.py` - CNN training integration tests

### `/migration/`
One-time migration scripts (can be archived after use):
- `migrate_class_ids.py` - Convert UUID class IDs to readable format
- `migrate_recording_ids.py` - Update recording ID formats

### `/deployment/`
Production deployment utilities:
- `upload_sounds_to_production.py` - Upload sound files to Railway

### `/utils/`
General utility scripts:
- `lookup_class_id.py` - Lookup class ID mappings
- `train_cnn1d_simple.py` - Simple CNN training test

## Usage

All scripts are designed to be run from the project root directory:

```bash
# From project root
python scripts/analysis/check_rf_params.py
python scripts/tests/test_api_backward_compat.py
python scripts/deployment/upload_sounds_to_production.py --dry-run
```

## Note on Git

Most subdirectories (except `/deployment/`) are excluded from version control via `.gitignore` as they contain development and testing tools not needed for runtime.