# User Manual - SoundClassifiers v10
Updated August 9, 2025

## Welcome to SoundsGood.Health

SoundsGood.Health is a phoneme recognition application designed to help users practice and improve their pronunciation of specific sounds. This platform uses machine learning to provide personalized feedback on speech sounds.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [User Registration & Login](#user-registration--login)
4. [Sound Classes](#sound-classes)
5. [Dictionaries](#dictionaries)
6. [Recording Audio](#recording-audio)
7. [Verifying Recordings](#verifying-recordings)
8. [Data Augmentation](#data-augmentation)
9. [Training Models](#training-models)
10. [Making Predictions](#making-predictions)
11. [Tips for Success](#tips-for-success)

## Getting Started

### Access the Application
- **Online**: Visit https://www.soundsgood.health
- **Local Development**: Run `python run.py` and navigate to http://localhost:5001

### System Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Microphone access for recording
- Stable internet connection (for online version)

## Core Concepts

Before diving in, understand these key terms:

- **Sound Class**: A specific sound or phoneme you want to practice (e.g., "ah", "sh", "th")
- **Dictionary**: A collection of related sound classes for focused training
- **Recording**: An audio sample of a sound class
- **Gold Recording**: A verified, high-quality recording used for training
- **Model**: A trained machine learning algorithm that recognizes sounds
- **Inference**: The process of predicting which sound class matches new audio

## User Registration & Login

### Creating an Account

1. Click "Sign Up" or "Register" on the homepage
2. Provide the following information:
   - **Username**: 3-30 characters (letters, numbers, underscores only)
   - **Email**: Valid email address for account recovery
   - **Password**: Minimum 8 characters, choose something secure
   - **First/Last Name**: Optional, for personalization

3. Click "Register" to create your account

### Logging In

1. Click "Log In" on the homepage
2. Enter your username or email
3. Enter your password
4. Click "Log In"

### Password Recovery

1. Click "Forgot Password?" on the login page
2. Enter your registered email address
3. Check your email for reset instructions

## Sound Classes

Sound classes are the foundation of your personalized training.

### Creating a Sound Class

1. Navigate to **Sound Classes** from the main menu
2. Click **"Create New Class"**
3. Enter a unique name (e.g., "th", "ah", "sh")
4. Add an optional description (e.g., "Voiceless th sound")
5. Click **"Create"**

### Best Practices for Sound Classes
- Use consistent naming (phonetic symbols or common spellings)
- Keep names short and descriptive
- Each class name must be unique across the system

## Dictionaries

Dictionaries organize related sound classes for targeted practice.

### Creating a Dictionary

1. Navigate to **Dictionaries** from the main menu
2. Click **"Create New Dictionary"**
3. Provide:
   - **Name**: Descriptive name (e.g., "Vowel Practice", "S and SH Sounds")
   - **Description**: Optional notes about purpose
   - **Sound Classes**: Select checkboxes for classes to include
4. Click **"Create"**

### Why Use Dictionaries?
- **Organization**: Keep related sounds together
- **Focused Training**: Models train on specific dictionaries
- **Targeted Practice**: Work on specific sound contrasts

## Recording Audio

Provide audio samples for each sound class in your dictionary.

### Method 1: Direct Recording

1. Navigate to **"Record"** or **"Record Sounds"**
2. Select the target Sound Class from the dropdown
3. Ensure you're in a quiet environment
4. Click the **Microphone Button** to start recording
5. Clearly pronounce the target sound
6. Click the Microphone Button again to stop
7. Repeat for multiple samples (aim for 10-20+ per class)

### Method 2: File Upload

1. Navigate to **"Upload"** or **"Upload Sounds"**
2. Select the target Sound Class
3. Click **"Choose File"** and select a .wav file
   - Format: 16kHz, 16-bit, mono WAV recommended
   - Multiple sounds should be separated by ~1 second of silence
4. Click **"Upload"**

### Recording Tips
- Speak clearly and naturally
- Leave brief silence before and after sounds
- Aim for variety in tone and volume
- More high-quality samples = better model performance

## Verifying Recordings

Quality control is crucial for effective model training.

### The Verification Process

1. Navigate to **"Verify"** from the menu
2. Review pending recordings by Sound Class
3. For each recording:
   - Click play to listen
   - Assess quality and accuracy
   - **Approve** (✔️): Mark as "Gold" for training
   - **Discard** (❌): Reject poor quality recordings

### Verification Guidelines
- Be selective - quality over quantity
- Ensure consistency within each class
- Check for background noise and clarity
- Only approve clear, accurate examples

## Data Augmentation

Enhance your dataset without additional recording.

### How Augmentation Works

1. Navigate to **"Augmentation"** section
2. Select your dictionary
3. View Gold recordings available for augmentation
4. For each Gold recording:
   - Set number of variations to generate (e.g., 5-50)
   - Click **"Augment"**
5. System creates variations with:
   - Slight pitch changes
   - Volume adjustments
   - Speed variations
   - Minor background noise

### Benefits
- Rapidly expand training data
- Improve model robustness
- Handle real-world variations better

## Training Models

Train custom recognition models on your prepared data.

### Available Model Types

1. **Random Forest (RF)**
   - Fast training
   - Reliable baseline performance
   - Good default choice

2. **CNN (Convolutional Neural Network)**
   - Deep learning approach
   - Complex pattern recognition
   - Currently being optimized

3. **Ensemble**
   - Combines multiple models
   - Potentially best accuracy
   - Under refinement

### Training Process

1. Navigate to **"Training"**
2. Select your dictionary
3. Choose model type (start with RF)
4. Configure parameters (use defaults if unsure):
   - **RF**: Number of estimators, max depth
   - **CNN**: Epochs, batch size, learning rate
5. Click **"Start Training"**
6. Monitor progress:
   - Progress bar
   - Status messages
   - Training logs
7. Review results:
   - Accuracy metrics
   - Confusion matrix
   - Performance summary

### Training Tips
- Start with Random Forest for quick results
- Ensure adequate Gold recordings (10+ per class)
- Use augmentation for better performance
- Train multiple models to compare

## Making Predictions

Test your trained models and practice pronunciation.

### Real-Time Microphone Prediction

1. Navigate to **"Inference"** or **"Predict"**
2. Select a trained model from the dropdown
3. View the list of sounds the model recognizes
4. Click **"Start Recording"**
5. Speak one of the trained sounds clearly
6. View predictions:
   - Predicted sound class
   - Confidence score
   - Recent prediction history
7. Provide feedback:
   - Click 👍 if correct
   - Click 👎 if incorrect, then select actual sound
8. Monitor statistics for accuracy tracking
9. Click **"Stop Recording"** when finished

### Understanding Results
- **Confidence Score**: Higher = more certain (aim for 70%+)
- **Confusion Matrix**: Shows which sounds are confused
- **Feedback**: Helps identify model weaknesses

## Tips for Success

### Recording Quality
- Use a good microphone in a quiet room
- Maintain consistent distance from microphone
- Record multiple sessions for variety
- Include different speakers if possible

### Training Strategy
1. Start small: 2-3 similar sounds
2. Record 20+ examples per sound
3. Verify carefully
4. Use augmentation (5-10x multiplier)
5. Train with Random Forest first
6. Test thoroughly before expanding

### Common Issues & Solutions

**Low Accuracy**
- Add more Gold recordings
- Check for mislabeled recordings
- Increase augmentation
- Try different model parameters

**Sounds Confused**
- These sounds may be too similar
- Add more distinctive examples
- Focus practice on confused pairs

**Model Won't Train**
- Ensure all classes have Gold recordings
- Check dictionary has multiple classes
- Verify feature extraction completed

## Getting Help

- **In-App Help**: Look for ? icons for contextual help
- **Developer Guide**: For API integration and advanced features
- **Support**: Contact through the platform's support channels

---

*Last Updated: August 2025*
*Version: SoundClassifiers v10*