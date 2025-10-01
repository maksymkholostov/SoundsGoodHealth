# Integration Guide for Theo - SoundClassifiers v10
Updated August 9, 2025

## Quick Start

Uncle Theo, this guide will help you integrate the SoundsGood API into your C# applications. The API replaces Azure Speech SDK with our custom phoneme recognition system.

## What You Need

1. **Model ID**: Get this from https://www.soundsgood.health/developer/downloads
2. **C# Client Library**: `SoundClassifiersClient.cs` (included in CSTestProject folder)
3. **NuGet Packages**:
   - Newtonsoft.Json (for JSON handling)
   - NAudio (for microphone recording)

## Step 1: Get Your Model ID

1. Go to https://www.soundsgood.health
2. Login with your credentials
3. Navigate to "Developer" → "Downloads"
4. Copy the Model ID for your trained model

## Step 2: Basic Setup

### Remove Azure SDK References
Delete these lines from your code:
```csharp
// Remove these:
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
```

### Add SoundsGood References
Add these at the top of your file:
```csharp
using SoundClassifiersClient;
using NAudio.Wave;  // For microphone recording
using System.IO;    // For file operations
using Newtonsoft.Json;
```

## Step 3: Initialize the Client

Replace Azure initialization with:
```csharp
// SoundsGood API Setup
string apiUrl = "https://www.soundsgood.health";
string modelId = "YOUR_MODEL_ID_HERE";  // Replace with your actual model ID

var client = new SoundClassifiersClient(apiUrl, modelId);
```

## Step 4: Simple Recognition Examples

### Example 1: Recognize from WAV File
```csharp
public async Task RecognizeFromFile(string wavFilePath)
{
    try
    {
        // Call the API
        var result = await client.RecognizeFromFileAsync(wavFilePath);
        
        // Check if successful
        if (result.Success)
        {
            Console.WriteLine($"Recognized: {result.Phoneme}");
            Console.WriteLine($"Confidence: {result.Confidence:P}");
            
            // Show alternatives if any
            if (result.Alternatives?.Count > 0)
            {
                Console.WriteLine("Alternatives:");
                foreach (var alt in result.Alternatives)
                {
                    Console.WriteLine($"  - {alt.Phoneme}: {alt.Confidence:P}");
                }
            }
        }
        else
        {
            Console.WriteLine($"Recognition failed: {result.Error}");
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"Error: {ex.Message}");
    }
}
```

### Example 2: Recognize from Microphone Recording
```csharp
public class MicrophoneRecognizer
{
    private WaveInEvent waveIn;
    private MemoryStream audioStream;
    private SoundClassifiersClient client;
    
    public MicrophoneRecognizer(string modelId)
    {
        client = new SoundClassifiersClient("https://www.soundsgood.health", modelId);
    }
    
    public void StartRecording()
    {
        // Setup microphone
        waveIn = new WaveInEvent();
        waveIn.DeviceNumber = 0;  // Default microphone
        waveIn.WaveFormat = new WaveFormat(16000, 16, 1);  // 16kHz, 16-bit, Mono
        
        audioStream = new MemoryStream();
        
        // Capture audio data
        waveIn.DataAvailable += (sender, e) =>
        {
            audioStream.Write(e.Buffer, 0, e.BytesRecorded);
        };
        
        waveIn.StartRecording();
        Console.WriteLine("Recording... Press any key to stop.");
    }
    
    public async Task StopAndRecognize()
    {
        // Stop recording
        waveIn.StopRecording();
        waveIn.Dispose();
        
        // Convert to WAV format
        byte[] wavBytes = CreateWavFile(audioStream.ToArray());
        
        // Send to API
        var result = await client.RecognizeFromDataAsync(wavBytes);
        
        if (result.Success)
        {
            Console.WriteLine($"You said: {result.Phoneme}");
            Console.WriteLine($"Confidence: {result.Confidence:P}");
        }
        else
        {
            Console.WriteLine("Could not recognize the sound.");
        }
        
        audioStream.Dispose();
    }
    
    private byte[] CreateWavFile(byte[] pcmData)
    {
        using (var wavStream = new MemoryStream())
        using (var writer = new WaveFileWriter(wavStream, new WaveFormat(16000, 16, 1)))
        {
            writer.Write(pcmData, 0, pcmData.Length);
            writer.Flush();
            return wavStream.ToArray();
        }
    }
}
```

## Step 5: Complete Windows Forms Example

Here's a complete example for a Windows Forms application:

```csharp
using System;
using System.Windows.Forms;
using System.Threading.Tasks;
using SoundClassifiersClient;
using NAudio.Wave;
using System.IO;

public partial class MainForm : Form
{
    private SoundClassifiersClient client;
    private WaveInEvent waveIn;
    private MemoryStream audioStream;
    private Button recordButton;
    private Label resultLabel;
    private bool isRecording = false;
    
    public MainForm()
    {
        InitializeComponent();
        InitializeClient();
    }
    
    private void InitializeClient()
    {
        // Initialize with your model ID
        string modelId = "YOUR_MODEL_ID_HERE";
        client = new SoundClassifiersClient("https://www.soundsgood.health", modelId);
    }
    
    private void recordButton_Click(object sender, EventArgs e)
    {
        if (!isRecording)
        {
            StartRecording();
        }
        else
        {
            StopRecording();
        }
    }
    
    private void StartRecording()
    {
        try
        {
            waveIn = new WaveInEvent
            {
                DeviceNumber = 0,
                WaveFormat = new WaveFormat(16000, 16, 1)
            };
            
            audioStream = new MemoryStream();
            
            waveIn.DataAvailable += (s, args) =>
            {
                audioStream.Write(args.Buffer, 0, args.BytesRecorded);
            };
            
            waveIn.StartRecording();
            
            isRecording = true;
            recordButton.Text = "Stop Recording";
            resultLabel.Text = "Recording...";
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Error starting recording: {ex.Message}");
        }
    }
    
    private async void StopRecording()
    {
        try
        {
            waveIn.StopRecording();
            waveIn.Dispose();
            
            isRecording = false;
            recordButton.Text = "Start Recording";
            resultLabel.Text = "Processing...";
            
            // Create WAV file from recorded data
            byte[] wavData = CreateWavFile(audioStream.ToArray());
            audioStream.Dispose();
            
            // Send to API for recognition
            var result = await client.RecognizeFromDataAsync(wavData);
            
            // Display results
            if (result.Success)
            {
                resultLabel.Text = $"Recognized: {result.Phoneme} ({result.Confidence:P} confident)";
                
                // Optional: Play success sound or update UI
                UpdateUIForSuccess(result);
            }
            else
            {
                resultLabel.Text = $"Recognition failed: {result.Error}";
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Error during recognition: {ex.Message}");
            resultLabel.Text = "Error occurred";
        }
    }
    
    private byte[] CreateWavFile(byte[] pcmData)
    {
        using (var wavStream = new MemoryStream())
        using (var writer = new WaveFileWriter(wavStream, new WaveFormat(16000, 16, 1)))
        {
            writer.Write(pcmData, 0, pcmData.Length);
            writer.Flush();
            return wavStream.ToArray();
        }
    }
    
    private void UpdateUIForSuccess(RecognitionResult result)
    {
        // Add your custom UI updates here
        // For example, show confidence bar, play sound, etc.
    }
}
```

## Step 6: Testing Your Integration

### Test Checklist
1. ✅ Model ID is correctly set
2. ✅ API URL is https://www.soundsgood.health
3. ✅ Audio format is 16kHz, 16-bit, mono WAV
4. ✅ Internet connection is available
5. ✅ Model is trained and active on the server

### Simple Console Test
```csharp
class Program
{
    static async Task Main(string[] args)
    {
        // Quick test
        var client = new SoundClassifiersClient(
            "https://www.soundsgood.health",
            "YOUR_MODEL_ID"
        );
        
        // Test with a sample WAV file
        Console.WriteLine("Testing SoundsGood API...");
        var result = await client.RecognizeFromFileAsync("test.wav");
        
        if (result.Success)
        {
            Console.WriteLine($"Success! Recognized: {result.Phoneme}");
        }
        else
        {
            Console.WriteLine($"Failed: {result.Error}");
        }
    }
}
```

## Common Issues and Solutions

### Issue 1: "Model not found"
**Solution**: Double-check your Model ID from the website

### Issue 2: "Invalid audio format"
**Solution**: Ensure WAV is 16kHz, 16-bit, mono format

### Issue 3: No response from API
**Solution**: Check internet connection and firewall settings

### Issue 4: Low confidence scores
**Solution**: 
- Ensure quiet recording environment
- Check microphone quality
- Speak clearly and at normal volume

## Helper Functions

### Convert Any WAV to Required Format
```csharp
public byte[] ConvertToRequiredFormat(string inputWavPath)
{
    using (var reader = new AudioFileReader(inputWavPath))
    {
        var outFormat = new WaveFormat(16000, 16, 1);
        using (var resampler = new MediaFoundationResampler(reader, outFormat))
        {
            resampler.ResamplerQuality = 60;
            using (var ms = new MemoryStream())
            using (var writer = new WaveFileWriter(ms, outFormat))
            {
                byte[] buffer = new byte[outFormat.AverageBytesPerSecond];
                int bytesRead;
                while ((bytesRead = resampler.Read(buffer, 0, buffer.Length)) > 0)
                {
                    writer.Write(buffer, 0, bytesRead);
                }
                return ms.ToArray();
            }
        }
    }
}
```

### Get List of Available Models
```csharp
public async Task ShowAvailableModels()
{
    var client = new SoundClassifiersClient("https://www.soundsgood.health");
    var models = await client.GetAvailableModelsAsync();
    
    Console.WriteLine("Available Models:");
    foreach (var model in models)
    {
        Console.WriteLine($"- ID: {model.Id}");
        Console.WriteLine($"  Name: {model.Name}");
        Console.WriteLine($"  Dictionary: {model.DictionaryName}");
        Console.WriteLine($"  Created: {model.CreatedAt}");
        Console.WriteLine();
    }
}
```

## Need Help?

1. **Check the Model**: Make sure it's trained and active on the website
2. **Test with Known Audio**: Use a clear recording of a sound you know the model recognizes
3. **Review the Logs**: Check console output for detailed error messages
4. **Contact Support**: Reach out if you're stuck

## Summary

The key changes from Azure to SoundsGood:
1. Replace Azure SDK with SoundClassifiersClient
2. Use your Model ID for authentication
3. Ensure audio is in WAV format (16kHz, 16-bit, mono)
4. Handle results using RecognitionResult object

That's it! Your application should now work with the SoundsGood API instead of Azure.

---

*Remember: Always test with a simple console app first before integrating into your main application.*