using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using System.IO;

namespace Azure_SR_Winforms
{
    public partial class FrmMain : Form
    {

        static string YourSubscriptionKey = "b36d47fa66e04d9c9fb32409e4f04f31";
        static string YourServiceRegion = "westeurope";

        string RecoMode; // Continuous, OnceOnly

        public FrmMain()
        {
            InitializeComponent();

            lblHeading.Text = "Adapted from M.K.'s Keyword Recognition code";
            label1.Text = "Click on the button below to start Once-Only recognition";
            btnStartReco.Text = "Speak into microphone";
            RecoOutput.Text = "reco output here";
            opt_OnceOnly.Checked = true;
            RecoMode = "OnceOnly";

            //opt_Continuous.Checked = false;
            btnStopReco.Visible = opt_Continuous.Checked;

            SetPreListeningUI();
        }

        private void SetPreListeningUI()
        {
            //btnListenOnce.Enabled = false;
            //btnCancel.Enabled = true;
            btnStartReco.Enabled = true;
            btnStopReco.Enabled = false;
        }

        private void SetPostListeningUI()
        {
            //btnListenOnce.Enabled = true;
            //btnCancel.Enabled = false;
            btnStartReco.Enabled = false;
            btnStopReco.Enabled = true;
        }

        private async void btnStartReco_Click(object sender, EventArgs ev)
        {
            //SetPreListeningUI();
 
            var speechConfig = SpeechConfig.FromSubscription(YourSubscriptionKey, YourServiceRegion);
            speechConfig.SpeechRecognitionLanguage = "en-US";
            var stopRecognition = new TaskCompletionSource<int>();

            switch (RecoMode)
            {
                case "Continuous":
                    
                    using (var speechRecognizer = new SpeechRecognizer(speechConfig))
                    {
                        StringBuilder sb;//https://stackoverflow.com/questions/5221066/convert-console-writeline-into-textbox
                        sb = new StringBuilder();
                        // Subscribes to events.
                        speechRecognizer.Recognizing += (s, e) =>
                        {
                            sb.AppendLine($"RECOGNIZING: Text={e.Result.Text}");
                        };

                        speechRecognizer.Recognized += (s, e) =>
                        {
                            if (e.Result.Reason == ResultReason.RecognizedSpeech)
                            {

                                sb.AppendLine($"RECOGNIZED: Text={e.Result.Text}");
                            }
                            else if (e.Result.Reason == ResultReason.NoMatch)
                            {
                                sb.AppendLine($"NOMATCH: Speech could not be recognized.");
                            }
                        };

                        speechRecognizer.Canceled += (s, e) =>
                        {
                            sb.AppendLine($"CANCELED: Reason={e.Reason}");

                            if (e.Reason == CancellationReason.Error)
                            {
                                sb.AppendLine($"CANCELED: ErrorCode={e.ErrorCode}");
                                sb.AppendLine($"CANCELED: ErrorDetails={e.ErrorDetails}");
                                sb.AppendLine($"CANCELED: Did you update the subscription info?");
                            }

                            stopRecognition.TrySetResult(0);
                        };

                        speechRecognizer.SessionStarted += (s, e) =>
                        {
                            Console.WriteLine("\n    Session started event.");
                        };

                        speechRecognizer.SessionStopped += (s, e) =>
                        {
                            Console.WriteLine("\n    Session stopped event.");
                            Console.WriteLine("\nStop recognition.");
                            stopRecognition.TrySetResult(0);
                        };

                        // Starts continuous recognition. Uses StopContinuousRecognitionAsync() to stop recognition.
                        await speechRecognizer.StartContinuousRecognitionAsync().ConfigureAwait(false);

                        // Waits for completion.
                        // Use Task.WaitAny to keep the task rooted.
                        Task.WaitAny(new[] { stopRecognition.Task });

                        // Stops recognition.
                        await speechRecognizer.StopContinuousRecognitionAsync().ConfigureAwait(false);

                        RecoOutput.Text = sb.ToString();
                    }
                    break;

                case "OnceOnly":
                using (var audioConfig = AudioConfig.FromDefaultMicrophoneInput())
                using (var speechRecognizer = new SpeechRecognizer(speechConfig, audioConfig))
                {
                    //Console.WriteLine("Speak into your microphone.");
                    var speechRecognitionResult = await speechRecognizer.RecognizeOnceAsync();
                    OutputSpeechRecognitionResult(speechRecognitionResult);
                }
                    break;
            }
            //SetPostListeningUI();
        }

        private async void btnStopReco_Click(object sender, EventArgs e)
        {
            //await recognizer.StopRecognitionAsync();

            //ERROR BECAUSE RECOGNIZER ONLY LOCALLY DEFINED ABOVE
            //await speechRecognizer.StopRecognitionAsync();
        }
        //static void OutputSpeechRecognitionResult(SpeechRecognitionResult speechRecognitionResult)
        //copied from azure start-up reco example
        private void OutputSpeechRecognitionResult(SpeechRecognitionResult speechRecognitionResult)
        {
            StringBuilder sb;//https://stackoverflow.com/questions/5221066/convert-console-writeline-into-textbox
            sb = new StringBuilder();
            switch (speechRecognitionResult.Reason)
            {
                case ResultReason.RecognizedSpeech:
                    //Console.WriteLine($"RECOGNIZED: Text={speechRecognitionResult.Text}");
                    sb.AppendLine($"RECOGNIZED: Text={speechRecognitionResult.Text}");
                    break;
                case ResultReason.NoMatch:
                    sb.AppendLine($"NOMATCH: Speech could not be recognized.");
                    break;
                case ResultReason.Canceled:
                    var cancellation = CancellationDetails.FromResult(speechRecognitionResult);
                    sb.AppendLine($"CANCELED: Reason={cancellation.Reason}");

                    if (cancellation.Reason == CancellationReason.Error)
                    {
                        sb.AppendLine($"CANCELED: ErrorCode={cancellation.ErrorCode}");
                        sb.AppendLine($"CANCELED: ErrorDetails={cancellation.ErrorDetails}");
                        sb.AppendLine($"CANCELED: Did you set the speech resource key and region values?");
                    }
                    break;
            }
            RecoOutput.Text = sb.ToString();
        }
    }
}
