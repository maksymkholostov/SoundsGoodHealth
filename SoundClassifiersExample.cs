// SoundClassifiersExample.cs
//
// Example showing how to use SoundClassifiersClient to replace Azure Speech SDK
// for phoneme recognition in a Windows Forms application.

using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Text;
using SoundClassifiersClient;
using NAudio.Wave; // NAudio for audio recording - make sure to add this NuGet package

namespace SpeechRecognitionExample
{
    public partial class MainForm : Form
    {
        // Your SoundClassifiers API details
        private const string ApiBaseUrl = "https://your-railway-app.railway.app"; // Update this with your Railway app URL
        private const string ModelId = "56b79c08-c58f-41cd-a7b6-f515ba04b5b6"; // Get this from your SoundClassifiers app
        // API Key removed - no longer needed

        private SoundClassifiersClient.SoundClassifiersClient _client;
        private WaveInEvent _waveIn;
        private MemoryStream _audioStream;
        private bool _isRecording = false;
        
        public MainForm()
        {
            InitializeComponent();
            
            // Initialize the SoundClassifiers client
            _client = new SoundClassifiersClient.SoundClassifiersClient(
                baseUrl: ApiBaseUrl,
                modelId: ModelId
            );
            
            // Set up audio recording
            _waveIn = new WaveInEvent
            {
                WaveFormat = new WaveFormat(16000, 1) // 16kHz, mono
            };
            _waveIn.DataAvailable += WaveIn_DataAvailable;
            _waveIn.RecordingStopped += WaveIn_RecordingStopped;
        }
        
        private void btnStartReco_Click(object sender, EventArgs e)
        {
            if (!_isRecording)
            {
                // Start recording
                _audioStream = new MemoryStream();
                _waveIn.StartRecording();
                _isRecording = true;
                
                btnStartReco.Text = "Stop Recording";
                txtRecoOutput.AppendText("Listening...\r\n");
            }
            else
            {
                // Stop recording
                _waveIn.StopRecording();
                btnStartReco.Text = "Start Recording";
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
                // Convert to WAV format
                _audioStream.Position = 0;
                byte[] audioData = await ConvertToWavFormat(_audioStream);
                
                // Display status
                txtRecoOutput.AppendText("Processing audio...\r\n");
                
                // Send to SoundClassifiers API
                var result = await _client.RecognizeFromDataAsync(audioData);
                
                // Display results
                txtRecoOutput.AppendText($"Recognized: {result.Phoneme}\r\n");
                txtRecoOutput.AppendText($"Confidence: {result.Confidence:P}\r\n");
                
                if (result.Alternatives != null && result.Alternatives.Count > 0)
                {
                    txtRecoOutput.AppendText("Alternatives:\r\n");
                    foreach (var alt in result.Alternatives)
                    {
                        txtRecoOutput.AppendText($" - {alt.Phoneme} ({alt.Confidence:P})\r\n");
                    }
                }
                
                // Here you can add code to trigger animations or UI changes
                // based on the recognized phoneme (similar to your uncle's code)
            }
            catch (Exception ex)
            {
                txtRecoOutput.AppendText($"Error: {ex.Message}\r\n");
            }
            finally
            {
                _audioStream.Dispose();
                _audioStream = null;
            }
        }
        
        private async Task<byte[]> ConvertToWavFormat(MemoryStream audioStream)
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
                    writer.Write(32000); // Byte rate (SampleRate * Channels * BitsPerSample/8)
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
    }
}

// UI setup code (simplified for the example)
public partial class MainForm
{
    private System.ComponentModel.IContainer components = null;
    
    private Button btnStartReco;
    private TextBox txtRecoOutput;
    
    protected override void Dispose(bool disposing)
    {
        if (disposing && (components != null))
        {
            components.Dispose();
        }
        base.Dispose(disposing);
    }
    
    private void InitializeComponent()
    {
        this.btnStartReco = new Button();
        this.txtRecoOutput = new TextBox();
        
        // btnStartReco
        this.btnStartReco.Location = new System.Drawing.Point(50, 30);
        this.btnStartReco.Name = "btnStartReco";
        this.btnStartReco.Size = new System.Drawing.Size(200, 40);
        this.btnStartReco.Text = "Start Recording";
        this.btnStartReco.Click += new EventHandler(this.btnStartReco_Click);
        
        // txtRecoOutput
        this.txtRecoOutput.Location = new System.Drawing.Point(50, 90);
        this.txtRecoOutput.Multiline = true;
        this.txtRecoOutput.Name = "txtRecoOutput";
        this.txtRecoOutput.Size = new System.Drawing.Size(400, 200);
        this.txtRecoOutput.ScrollBars = ScrollBars.Vertical;
        
        // MainForm
        this.AutoScaleDimensions = new System.Drawing.SizeF(8F, 16F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new System.Drawing.Size(500, 320);
        this.Controls.Add(this.txtRecoOutput);
        this.Controls.Add(this.btnStartReco);
        this.Name = "MainForm";
        this.Text = "SoundClassifiers Example";
    }
} 