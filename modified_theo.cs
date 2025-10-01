// modified_theo.cs
//
// PURPOSE:
// This file demonstrates how to adapt existing C# code (originally using Azure Speech SDK)
// to use the custom SoundClassifiers API via the SoundClassifiersClient library.
// It shows the key changes needed for initialization, audio handling, and result processing.
//
// NOTE: This is an EXAMPLE integration. You will need to adapt this code
//       to fit the specific structure and UI elements of your application.
//

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using NAudio.Wave;
using System.IO;
using SoundClassifiersClient;  // Import the client library

namespace Speech_Recognition_App
{
    public partial class FrmMain : Form
    {
        // --- Configuration for SoundClassifiers API ---
        // !! IMPORTANT: Replace placeholders below !!
        // Base URL of the deployed SoundClassifiers application
        static string ApiBaseUrl = "https://www.soundsgood.health"; // *** USE THIS URL ***

        // Model ID of the specific trained model you want to use.
        // Find this ID on the 'Developer Resources' or 'Quick Start' page
        // within the SoundsGood web application after logging in.
        static string ModelId = "56b79c08-c58f-41cd-a7b6-f515ba04b5b6"; // *** GET THIS FROM THE WEBSITE ***

        // API Key is not currently used by the SoundClassifiers API
        static string ApiKey = null;
        // --- End Configuration ---

        // *** NEW: Instance of the SoundClassifiers Client ***
        private SoundClassifiersClient.SoundClassifiersClient _scClient;

        // --- Audio Recording Components (using NAudio example) ---
        // You might have a different way of getting audio data (e.g., from file)
        private WaveInEvent _waveIn;
        private MemoryStream _audioStream;
        private bool _isRecording = false;
        // --- End Audio Recording ---

        // Task completion for managing async operations if needed
        private TaskCompletionSource<int> stopRecognition;

        // --- Variables migrated from the original Azure-based code ---
        // These variables control the application's state and logic based on recognition results.
        // They should be kept and used similarly, but populated from the RecognitionResult object.
        bool StoppedReco = false;
        StringBuilder sb; // For logging or displaying output
        int nStartReco = 0;
        string lastRecoWord = ""; // Will be populated by result.Phoneme
        int NlastReco = 0;
        // Example choices the original app was looking for:
        string choice1 = "ee";
        string choice2 = "or";
        int ichoiceRec = 0;
        int iDecoyRec = -1;
        int BugDirection = 0;
        bool CanTriggerAnimation = false;
        bool ManualActive = false;
        int SylNeeded = 0;
        int NumAdditionalSelectedChoices = 0;
        string[] SylDecoyText = new string[10]; // Populate as needed
        bool Teacher_Demo = false;
        int[] NRecoAttemptsCurrent = new int[10]; // Populate as needed
        bool NewReco = false;
        bool ObeyRecognizedSyl = true; // Flag from original code
        // --- End Migrated Variables ---

        public FrmMain()
        {
            InitializeComponent();
            
            // *** NEW: Initialize the SoundClassifiers Client ***
            _scClient = new SoundClassifiersClient.SoundClassifiersClient(
                baseUrl: ApiBaseUrl,
                modelId: ModelId,
                apiKey: ApiKey // Pass the null ApiKey variable
            );
            Console.WriteLine($"SoundClassifiers Client Initialized. Using Model ID: {ModelId}");
            
            // Set up audio recording with NAudio
            _waveIn = new WaveInEvent
            {
                WaveFormat = new WaveFormat(16000, 1) // 16kHz, mono (adjust as needed)
            };
            _waveIn.DataAvailable += WaveIn_DataAvailable;
            _waveIn.RecordingStopped += WaveIn_RecordingStopped;
            
            // Set default UI state
            SetPreListeningUI();
        }

        private void SetPreListeningUI()
        {
            // Pre-listening UI setup (same as original code)
            btn_StartReco.Enabled = true;
            btn_StopReco.Enabled = false;
        }

        private void SetPostListeningUI()
        {
            // Post-listening UI setup (same as original code)
            btn_StartReco.Enabled = false;
            btn_StopReco.Enabled = true;
        }

        private void WaveIn_DataAvailable(object sender, WaveInEventArgs e)
        {
            // Write audio data to memory stream
            if (_audioStream != null && !StoppedReco)
            {
                _audioStream.Write(e.Buffer, 0, e.BytesRecorded);
            }
        }

        private async void WaveIn_RecordingStopped(object sender, StoppedEventArgs e)
        {
            if (_audioStream == null || StoppedReco) return;
            
            try
            {
                // Convert to WAV format
                _audioStream.Position = 0;
                byte[] audioData = ConvertToWavFormat(_audioStream);
                
                // Send to SoundClassifiers API
                var result = await _scClient.RecognizeFromDataAsync(audioData);
                
                // Process the recognition result
                ProcessRecognitionResult(result);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing audio: {ex.Message}");
            }
            finally
            {
                _audioStream.Dispose();
                _audioStream = null;
                
                // Signal completion if continuous mode is stopped
                stopRecognition?.TrySetResult(0);
            }
        }

        private void ProcessRecognitionResult(RecognitionResult result)
        {
            // This replaces the Azure Recognizing/Recognized event handlers
            if (!ObeyRecognizedSyl) return;
            
            Console.WriteLine($"\n RECOGNIZED: Phoneme={result.Phoneme}");
            sb.AppendLine($"RECOGNIZED: Phoneme={result.Phoneme}");
            
            // Use the recognized phoneme directly instead of extracting from text
            lastRecoWord = result.Phoneme;
            string lastrecolower = lastRecoWord.ToLower();
            string lastrecoword = lastrecolower;
            
            // Apply the same transformations as in the original code
            switch (lastRecoWord)
            {
                case "E":
                    lastrecoword = "ee";
                    lastRecoWord = "E to ee";
                    break;
                case "EE":
                    lastrecoword = "ee";
                    lastRecoWord = "EE to ee";
                    break;
                case "he":
                    lastrecoword = "ee";
                    lastRecoWord = "he to ee";
                    break;
                case "ohh":
                    lastrecoword = "or";
                    lastRecoWord = "ohh to or";
                    break;
                default:
                    lastrecoword = lastrecolower;
                    break;
            }
            
            NlastReco++;
            if (!Teacher_Demo)
            {
                NRecoAttemptsCurrent[SylNeeded]++;
            }
            
            NewReco = true;
            if (lastrecoword == choice1)
            {
                if (!ManualActive)
                {
                    ichoiceRec = 1;
                    BugDirection = -1;
                    CanTriggerAnimation = true;
                }
            }
            else if (lastrecoword == choice2)
            {
                if (!ManualActive)
                {
                    ichoiceRec = 2;
                    BugDirection = 1;
                    CanTriggerAnimation = true;
                }
            }
            else if (NumAdditionalSelectedChoices > 0)
            {
                for (int i = 0; i < NumAdditionalSelectedChoices; i++)
                {
                    if (lastrecoword == SylDecoyText[i])
                    {
                        iDecoyRec = i;
                    }
                }
            }
        }

        private byte[] ConvertToWavFormat(MemoryStream audioStream)
        {
            // Convert raw PCM to WAV format
            using (var memoryStream = new MemoryStream())
            {
                using (var writer = new BinaryWriter(memoryStream))
                {
                    // Write WAV header
                    writer.Write(Encoding.ASCII.GetBytes("RIFF"));
                    writer.Write((int)(audioStream.Length + 36)); // File size
                    writer.Write(Encoding.ASCII.GetBytes("WAVE"));
                    writer.Write(Encoding.ASCII.GetBytes("fmt "));
                    writer.Write(16); // Chunk size
                    writer.Write((short)1); // Audio format (PCM)
                    writer.Write((short)1); // Channels (mono)
                    writer.Write(16000); // Sample rate
                    writer.Write(32000); // Byte rate
                    writer.Write((short)2); // Block align
                    writer.Write((short)16); // Bits per sample
                    writer.Write(Encoding.ASCII.GetBytes("data"));
                    writer.Write((int)audioStream.Length); // Data chunk size
                    
                    // Write audio data
                    audioStream.Position = 0;
                    audioStream.CopyTo(memoryStream);
                }
                
                return memoryStream.ToArray();
            }
        }

        private async void btn_StartReco_Click(object sender, EventArgs ev)
        {
            SetPreListeningUI();
            
            stopRecognition = new TaskCompletionSource<int>();
            StoppedReco = false;
            
            nStartReco++;
            sb = new StringBuilder();
            
            try
            {
                // Start recording
                _audioStream = new MemoryStream();
                _waveIn.StartRecording();
                _isRecording = true;
                
                Console.WriteLine($"\n    Session {nStartReco} started event. {DateTime.Now.ToString("hh:mm:ss.ffffff")}");
                sb.AppendLine($"    Session started event.");
                
                // Wait for completion (if using continuous mode)
                await Task.WhenAny(stopRecognition.Task);
                
                // Stop recording
                if (_isRecording)
                {
                    _waveIn.StopRecording();
                    _isRecording = false;
                }
                
                Console.WriteLine($"\n    Session {nStartReco} stopped event. {DateTime.Now.ToString("hh:mm:ss.ffffff")}");
                Console.WriteLine("\nStop recognition.");
                sb.AppendLine($"    Session stopped event.");
                sb.AppendLine($"Stop recognition.");
                StoppedReco = true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error during recognition: {ex.Message}");
                sb.AppendLine($"CANCELED: ErrorDetails={ex.Message}");
                stopRecognition.TrySetResult(0);
            }
        }

        private void btn_StopReco_Click(object sender, EventArgs e)
        {
            // Stop continuous recognition
            if (_isRecording)
            {
                _waveIn.StopRecording();
                _isRecording = false;
            }
            
            StoppedReco = true;
            stopRecognition.TrySetResult(0);
        }
        
        // Add UI components and other required methods
        // This would be a simplified version compared to the original code
        
        // Example of UI properties that would need to be defined
        private Button btn_StartReco;
        private Button btn_StopReco;
        private PictureBox pic_Bug;
        
        private void InitializeComponent()
        {
            // Component initialization code would go here
            // Similar to the original code
        }
    }
} 