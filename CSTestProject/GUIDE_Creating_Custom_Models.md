# Guide: Creating Custom Dictionaries and Training Models on SoundClassifiers

## Overview
This guide explains how to create your own dictionaries, record training data, and train Random Forest models on the SoundClassifiers platform.

## Step-by-Step Process

### 1. Login to SoundClassifiers
- Go to: https://www.soundsgood.health
- Login with your credentials:
  - Username: tdrubin
  - Password: michalyocheved

### 2. Create Sound Classes
First, you need to define what sounds you want to recognize.

1. Navigate to **"Classes"** in the menu
2. Click **"Create New Class"**
3. Enter a name for your sound (e.g., "Ah", "Uh", "Mmm", "Sss", etc.)
4. Click **"Create"**
5. Repeat for each sound you want to recognize

**Example Classes You Could Create:**
- Vowel sounds: "Ah", "Ee", "Oo", "Uh"
- Consonant sounds: "Sss", "Mmm", "Nnn", "Fff"
- Custom sounds: "Whistle", "Click", "Pop"

### 3. Create a Dictionary
A dictionary groups related sound classes together.

1. Navigate to **"Dictionaries"** in the menu
2. Click **"Create New Dictionary"**
3. Enter a name (e.g., "MyVowels", "ConsonantSet", etc.)
4. Select the classes you want to include
5. Click **"Create"**

**Example Dictionaries:**
- "BasicVowels": containing "Ah", "Ee", "Oo"
- "SibilantSounds": containing "Sss", "Shh", "Zzz"

### 4. Record Training Data
You need to record examples of each sound in your dictionary.

1. Navigate to **"Recordings"** in the menu
2. Select your dictionary from the dropdown
3. For each class in your dictionary:
   - Click **"Record"** button
   - Say the sound clearly into your microphone (multiple times)
   - Click **"Stop"** when done
   - Label the recording with the correct class
   - Click **"Save"**

**Recording Tips:**
- Record at least 10-20 examples of each sound
- Vary your pitch and tone slightly
- Keep recordings short (1-2 seconds each)
- Record in a quiet environment
- Use consistent microphone distance

### 5. Process Your Recordings
After recording, you need to process the audio files.

1. Go to **"Processing"** in the menu
2. Select your dictionary
3. Click **"Process All Recordings"**
4. Wait for processing to complete

### 6. Extract Features
Feature extraction prepares your audio for training.

1. Navigate to **"Features"** in the menu
2. Select your dictionary
3. Click **"Extract Features"**
4. Choose feature version (usually "v0.1" is fine)
5. Wait for extraction to complete

### 7. Train Your Model
Now you can train a Random Forest model.

1. Navigate to **"Training"** in the menu
2. Select your dictionary
3. Choose settings:
   - Model Type: **Random Forest**
   - Feature Version: v0.1 (or whatever you used)
   - Training Split: 80/20 (default is fine)
4. Click **"Start Training"**
5. Wait for training to complete

### 8. Get Your Model ID
After training completes:

1. Go to **"Models"** in the menu
2. Find your newly trained model in the list
3. Click on the model to see details
4. **Copy the Model ID** (it will look like: "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6")

### 9. Update Your C# Application
In your Windows Forms application:

1. Replace the Model ID in the code:
```csharp
private const string ModelId = "YOUR-NEW-MODEL-ID-HERE";
```

2. Or update it in the UI:
   - Run the application
   - Paste your new Model ID in the "Model ID" textbox
   - Click "Start Recording" or "Test with File"

## Example Workflow

Let's say you want to create a model that recognizes "Yes", "No", and "Maybe":

1. **Create Classes:**
   - Class 1: "Yes"
   - Class 2: "No" 
   - Class 3: "Maybe"

2. **Create Dictionary:**
   - Name: "YesNoMaybe"
   - Classes: Select all three

3. **Record Samples:**
   - 15 recordings of you saying "Yes"
   - 15 recordings of you saying "No"
   - 15 recordings of you saying "Maybe"

4. **Process → Extract Features → Train**

5. **Get Model ID** and use it in your application

## Tips for Better Models

1. **More Data = Better Accuracy**
   - Aim for at least 20-30 samples per class
   - More is generally better

2. **Consistent Recording Environment**
   - Use the same microphone
   - Same room/background noise level
   - Similar distance from microphone

3. **Diverse Examples**
   - Record at different times
   - Slight variations in pronunciation
   - Different emotional tones (if relevant)

4. **Clear Class Distinctions**
   - Choose sounds that are distinctly different
   - Avoid very similar sounds in the same dictionary

5. **Test Your Model**
   - After training, test with new recordings
   - If accuracy is low, add more training data

## Viewing Model Performance

After training, you can see:
- Accuracy percentage
- Precision and Recall metrics
- Number of training samples used

These metrics help you understand how well your model performs.

## Multiple Models

You can create multiple models for different purposes:
- One model for vowel sounds
- Another for consonant sounds
- Another for specific words
- etc.

Just change the Model ID in your C# application to switch between models.

## Need Help?

If you encounter issues:
1. Make sure you have enough recordings (minimum 5-10 per class)
2. Check that recordings are properly labeled
3. Ensure all processing steps completed successfully
4. Try recording clearer/louder samples if recognition is poor

Happy training!