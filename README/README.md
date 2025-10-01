# SoundClassifiers v10
Updated August 9, 2025

A comprehensive web-based system for training and using sound classification models, designed for speech therapy and phoneme recognition.

**Production Site**: https://www.soundsgood.health

## Quick Start

```bash
# Run the application
python run.py

# The browser will open automatically at http://localhost:5001
# Login with test credentials or register a new account
```

## Features

- **Sound Classification**: Train custom ML models (Random Forest, CNN, SVM, Ensemble)
- **Real-time Inference**: Process audio input for immediate feedback
- **Data Augmentation**: Automatically generate training data variations
- **User Management**: Multi-user support with individual dictionaries
- **C# Client API**: Integration support for Windows applications
- **Interactive UI**: Modern web interface for all devices

## Documentation

All documentation is located in the `Documentation/` folder:

1. **[User Manual](Documentation/01_User_Manual.md)** - Complete guide for using the platform
2. **[API Documentation](Documentation/02_APIs.md)** - REST API endpoints and examples
3. **[For Theo - C# Integration](Documentation/03_For_Theo.md)** - C# client setup and usage
4. **[Connecting to Railway](Documentation/04_Connecting_to_Railway.md)** - Production server management
5. **[Code Notes](Documentation/05_Code_Notes.md)** - Architecture, naming conventions, development notes
6. **[Deployment Guide](Documentation/06_Deployment_to_Live_Server.md)** - Deploy to production on Railway

## Project Structure

```
SoundClassifiers_v10/
├── backend/           # Flask application and ML models
│   ├── app/          # Core application modules
│   └── data/         # User data and models
├── frontend/         # Web interface
│   ├── static/       # CSS, JavaScript, images
│   └── templates/    # HTML templates
├── CSTestProject/    # C# client test project
├── Documentation/    # All documentation (6 files)
├── scripts/          # Utility and development scripts
├── flask_app.py      # Flask application factory
├── run.py           # Application runner
└── wsgi.py          # Production WSGI entry point
```

## Requirements

- Python 3.8+
- See `requirements.txt` for Python dependencies
- For C# client: .NET SDK 6+ and NAudio

## Installation

1. **Clone the repository**
   ```bash
   git clone [repository-url]
   cd SoundClassifiers_v10
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python run.py
   ```

4. **Access the application**
   - Browser opens automatically
   - Or navigate to http://localhost:5001
   - Login with test account or register

## Model Types

The platform supports multiple machine learning models:

- **Random Forest (RF)**: Fast, reliable baseline model
- **CNN**: Deep learning for complex patterns
- **SVM**: Support Vector Machine for classification
- **Ensemble**: Combines multiple models for best accuracy

## C# Client Integration

For Windows application integration, see [Documentation/03_For_Theo.md](Documentation/03_For_Theo.md)

Quick test:
```bash
cd CSTestProject
dotnet run
```

## Development Scripts

Utility scripts are organized in the `scripts/` folder:
- `analysis/` - Model analysis tools
- `tests/` - API and model tests
- `migration/` - Data migration scripts
- `deployment/` - Production deployment tools

## Deployment

The application is deployed on Railway at https://www.soundsgood.health

For deployment instructions, see [Documentation/06_Deployment_to_Live_Server.md](Documentation/06_Deployment_to_Live_Server.md)

### Persistent data on Railway (Volumes)

In production, datasets (sounds, features, models, logs) must not be baked into the image. Persist them on a Railway Volume and point the app to it.

1. Attach a Volume to the service and set Mount Path to `/data`.
2. Set the following environment variables on the service:

```
USE_VOLUME=true
DATA_VOLUME_PATH=/data
```

3. Redeploy the service.

The app will automatically resolve `DATA_ROOT` to the volume path and write/read all runtime data there via `FileManager`.

Optional migration (one time inside `railway ssh`):

```
mkdir -p /data && cp -a /app/backend/data/. /data/
```

## Support

- Check the [User Manual](Documentation/01_User_Manual.md) for usage instructions
- Review [API Documentation](Documentation/02_APIs.md) for integration
- See [Code Notes](Documentation/05_Code_Notes.md) for development details

## License

All rights reserved. This is proprietary software.

## Authors

SoundsGood Team

---

*For detailed information on any topic, please refer to the appropriate document in the Documentation folder.*