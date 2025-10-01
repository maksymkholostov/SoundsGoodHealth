using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;
using SoundClassifiersClient;
using NAudio.Wave;

namespace SpeechRecognitionExample
{
    public partial class MainForm : Form
    {
        private SoundClassifiersClient.SoundClassifiersClient _client;
        private WaveInEvent _waveIn;
        private MemoryStream _audioStream;
        private bool _isRecording = false;
        
        public MainForm()
        {
            InitializeComponent();
            InitializeClient();
            InitializeAudioRecording();
        }
        
        private void InitializeClient()
        {
            try
            {
                _client = new SoundClassifiersClient.SoundClassifiersClient(
                    baseUrl: txtApiUrl.Text,
                    modelId: txtModelId.Text
                );
                AppendOutput($"Client initialized with API: {txtApiUrl.Text}");
            }
            catch (Exception ex)
            {
                AppendOutput($"Error initializing client: {ex.Message}");
            }
        }
        
        private void InitializeAudioRecording()
        {
            try
            {
                _waveIn = new WaveInEvent
                {
                    WaveFormat = new WaveFormat(16000, 1) // 16kHz, mono
                };
                _waveIn.DataAvailable += WaveIn_DataAvailable;
                _waveIn.RecordingStopped += WaveIn_RecordingStopped;
                AppendOutput("Audio recording initialized (16kHz, mono)");
            }
            catch (Exception ex)
            {
                AppendOutput($"Error initializing audio: {ex.Message}");
            }
        }
        
        private void btnStartReco_Click(object sender, EventArgs e)
        {
            try
            {
                if (!_isRecording)
                {
                    // Re-initialize client with current settings
                    InitializeClient();
                    
                    // Start recording
                    _audioStream = new MemoryStream();
                    _waveIn.StartRecording();
                    _isRecording = true;
                    
                    btnStartReco.Text = "Stop Recording";
                    lblStatus.Text = "Recording...";
                    AppendOutput("\n--- Started Recording ---");
                }
                else
                {
                    // Stop recording
                    _waveIn.StopRecording();
                    btnStartReco.Text = "Start Recording";
                    lblStatus.Text = "Processing...";
                }
            }
            catch (Exception ex)
            {
                AppendOutput($"Error: {ex.Message}");
                lblStatus.Text = "Error";
            }
        }
        
        private void WaveIn_DataAvailable(object sender, WaveInEventArgs e)
        {
            // Write audio data to memory stream
            _audioStream.Write(e.Buffer, 0, e.BytesRecorded);
        }
        
        private async void WaveIn_RecordingStopped(object sender, StoppedEventArgs e)
        {
            _isRecording = false;
            
            try
            {
                AppendOutput("Recording stopped. Processing audio...");
                
                // Convert to WAV format
                _audioStream.Position = 0;
                byte[] audioData = await ConvertToWavFormat(_audioStream);
                
                AppendOutput($"Audio size: {audioData.Length:N0} bytes");
                
                // Send to SoundClassifiers API
                var result = await _client.RecognizeFromDataAsync(audioData);
                
                // Display results
                if (result != null && !string.IsNullOrEmpty(result.Phoneme))
                {
                    AppendOutput($"\n=== RESULT ===");
                    AppendOutput($"Recognized: {result.Phoneme}");
                    
                    if (result.Alternatives != null && result.Alternatives.Count > 0)
                    {
                        AppendOutput("\nAlternatives:");
                        foreach (var alt in result.Alternatives)
                        {
                            AppendOutput($"  - {alt.Phoneme}");
                        }
                    }
                }
                else
                {
                    AppendOutput("\nNo phoneme recognized or result was null");
                }
                
                lblStatus.Text = "Ready";
            }
            catch (Exception ex)
            {
                AppendOutput($"\nError processing audio: {ex.Message}");
                if (ex.InnerException != null)
                {
                    AppendOutput($"Inner error: {ex.InnerException.Message}");
                }
                lblStatus.Text = "Error";
            }
        }
        
        private async void btnTestFile_Click(object sender, EventArgs e)
        {
            using (OpenFileDialog ofd = new OpenFileDialog())
            {
                ofd.Filter = "WAV files (*.wav)|*.wav|All files (*.*)|*.*";
                ofd.Title = "Select a WAV file to test";
                
                if (ofd.ShowDialog() == DialogResult.OK)
                {
                    try
                    {
                        lblStatus.Text = "Processing file...";
                        AppendOutput($"\n--- Testing file: {Path.GetFileName(ofd.FileName)} ---");
                        
                        // Re-initialize client with current settings
                        InitializeClient();
                        
                        // Read file
                        byte[] audioData = File.ReadAllBytes(ofd.FileName);
                        AppendOutput($"File size: {audioData.Length:N0} bytes");
                        
                        // Send to API
                        var result = await _client.RecognizeFromDataAsync(audioData);
                        
                        // Display results
                        if (result != null && !string.IsNullOrEmpty(result.Phoneme))
                        {
                            AppendOutput($"\n=== RESULT ===");
                            AppendOutput($"Recognized: {result.Phoneme}");
                            
                            if (result.Alternatives != null && result.Alternatives.Count > 0)
                            {
                                AppendOutput("\nAlternatives:");
                                foreach (var alt in result.Alternatives)
                                {
                                    AppendOutput($"  - {alt.Phoneme}");
                                }
                            }
                        }
                        else
                        {
                            AppendOutput("\nNo phoneme recognized or result was null");
                        }
                        
                        lblStatus.Text = "Ready";
                    }
                    catch (Exception ex)
                    {
                        AppendOutput($"\nError: {ex.Message}");
                        if (ex.InnerException != null)
                        {
                            AppendOutput($"Inner error: {ex.InnerException.Message}");
                        }
                        lblStatus.Text = "Error";
                    }
                }
            }
        }
        
        private async Task<byte[]> ConvertToWavFormat(MemoryStream audioStream)
        {
            using (var outputStream = new MemoryStream())
            using (var writer = new WaveFileWriter(outputStream, _waveIn.WaveFormat))
            {
                audioStream.Position = 0;
                await audioStream.CopyToAsync(writer);
                writer.Flush();
                return outputStream.ToArray();
            }
        }
        
        private void AppendOutput(string text)
        {
            if (InvokeRequired)
            {
                Invoke(new Action<string>(AppendOutput), text);
                return;
            }
            
            txtRecoOutput.AppendText(text + Environment.NewLine);
            txtRecoOutput.SelectionStart = txtRecoOutput.Text.Length;
            txtRecoOutput.ScrollToCaret();
        }
    }
}