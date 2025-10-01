# SoundClassifiers Windows Forms Application Setup Guide

## Overview
This is a Windows Forms application that replaces Azure Speech SDK with the SoundClassifiers API for phoneme recognition. The application can record audio from your microphone or test with existing WAV files.

## Important Information

### API Endpoint
- Production URL: `https://www.soundsgood.health`
- Local URL (for testing): `http://localhost:5001`

### Model Information
- Model ID: `56b79c08-c58f-41cd-a7b6-f515ba04b5b6`
- This model recognizes two phonemes: "Eh" and "Oh"
- It's a Random Forest model with 100% accuracy on the training data

### Your Login Credentials
- Website: https://www.soundsgood.health
- Username: tdrubin
- Password: michalyocheved

## Setup Instructions

### 1. Create a New Windows Forms Project in Visual Studio
1. Open Visual Studio
2. Create New Project → Windows Forms App (.NET Framework)
3. Name it "SpeechRecognitionExample"
4. Choose .NET Framework 4.7.2 or higher

### 2. Install Required NuGet Packages
In Visual Studio, go to Tools → NuGet Package Manager → Package Manager Console and run:
```powershell
Install-Package Newtonsoft.Json
Install-Package NAudio
```

### 3. Add the Required Files
Copy these files to your project:
1. `SoundClassifiersClient.cs` - The API client library
2. `MainForm.cs` - The main form code
3. `MainForm.Designer.cs` - The form designer code

### 4. Replace Program.cs
Replace the default Program.cs content with:
```csharp
using System;
using System.Windows.Forms;

namespace SpeechRecognitionExample
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}
```

### 5. Test Audio Files
The model is trained to recognize "Eh" and "Oh" sounds. You can use the provided test files:
- `Eh.wav` - Should be recognized as "Eh"
- `Oh.wav` - Should be recognized as "Oh"

## How to Use the Application

### Recording from Microphone
1. Run the application
2. Make sure the API URL is set to `https://www.soundsgood.health`
3. Make sure the Model ID is set to `56b79c08-c58f-41cd-a7b6-f515ba04b5b6`
4. Click "Start Recording"
5. Say "Eh" or "Oh" clearly into the microphone
6. Click "Stop Recording"
7. The application will process the audio and show the result

### Testing with a File
1. Click "Test with File"
2. Select a WAV file (use Eh.wav or Oh.wav for testing)
3. The application will process the file and show the result

## Troubleshooting

### If you get connection errors:
1. Check that the API URL is correct: `https://www.soundsgood.health`
2. Make sure you have internet connection
3. Try the local URL `http://localhost:5001` if Ron is running the local server

### If recognition doesn't work:
1. Make sure you're using sounds similar to "Eh" or "Oh"
2. Check that the audio is clear and not too quiet
3. The WAV file should be 16kHz sample rate (the app handles this automatically for recordings)

### Build Errors:
1. Make sure you installed both NuGet packages (Newtonsoft.Json and NAudio)
2. Check that you're using .NET Framework 4.7.2 or higher
3. Ensure all files are properly added to the project

## Console Test Application
If you prefer to test with the console application first:
1. Use `Program.cs` (the original one, not Program_WinForms.cs)
2. Create a Console Application instead of Windows Forms
3. The console app will test both production and local endpoints automatically

## Notes
- The application records in 16kHz mono format, which is what the model expects
- The model is specifically trained for "Eh" and "Oh" sounds
- Results will show the recognized phoneme and any alternatives

Let me know if you encounter any issues!