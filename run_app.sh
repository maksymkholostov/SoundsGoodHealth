#!/bin/bash
# Wrapper script to run the app with the correct Python environment

# Use the correct Python interpreter
PYTHON_PATH="/opt/anaconda3/envs/sounds_easy_py310/bin/python"

# Check if the Python interpreter exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Python interpreter not found at $PYTHON_PATH"
    echo "Please ensure the sounds_easy_py310 conda environment is installed."
    exit 1
fi

# Export the path so subprocesses use it too
export PATH="/opt/anaconda3/envs/sounds_easy_py310/bin:$PATH"

# Set Python environment variables to ensure correct interpreter
export PYTHONHOME="/opt/anaconda3/envs/sounds_easy_py310"

# Run the application
echo "Starting SoundClassifiers with correct Python environment..."
echo "Using Python: $PYTHON_PATH"
"$PYTHON_PATH" run.py "$@"