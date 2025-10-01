None selected 


Skip to content
Using Gmail with screen readers
trubin@smile.net.il 
Conversations
event handlers from azure server
Inbox
Personal


trubin@smile.net.il via inter.net.il 
Attachments
Fri, Apr 18, 11:45 PM (9 days ago)
to me

Hi
This is the c# code in my app to get reco data from azure.
1. as currently in my code
2. from Eli‭‮
 2 Attachments
  •  Scanned by Gmail
Thanks, I'll check it out.Thanks, I'll look into it.Thanks a lot.
POP3
Inserted trubin@zahav.net.il.
        private async void btn_StartReco_Click(object sender, EventArgs ev)
        //private async void btn_StartReco_Click(object sender, EventArgs ev)
        {

            SetPreListeningUI();
            //var speechConfig = SpeechConfig.FromSubscription(YourSubscriptionKey, YourServiceRegion); //old code, now need key in Speech Studio
            var speechConfig = SpeechConfig.FromSubscription(YourSpeechKey, YourServiceRegion);
            //speechConfig.SpeechRecognitionLanguage = "en-US";
            //speechConfig.SpeechRecognitionLanguage = "en-GB"; //2303/03/24
            speechConfig.SpeechRecognitionLanguage = "en-US";  //2303/03/30
            //if (UseCustomModel)
            speechConfig.EndpointId = YourCustomModelEndpointId;

            stopRecognition = new TaskCompletionSource<int>();

            //switch (RecoMode)
            //{
            //      case "Continuous":

            StoppedReco = false;
            using (var speechRecognizer = new SpeechRecognizer(speechConfig))
            {
                nStartReco++;
                sb = new StringBuilder();
                string lastrecolower, lastrecoword;
                // Subscribes to events.
                //https://learn.microsoft.com/en-us/dotnet/api/microsoft.cognitiveservices.speech.speechrecognitioneventargs?view=azure-dotnet

                //var phraseList = PhraseListGrammar.FromRecognizer(speechRecognizer);
                //phraseList.AddPhrase("Meh");
                //phraseList.AddPhrase("Beh");
                //phraseList.AddPhrase("Bee");
                ////phraseList.AddPhrase("Itzik");
                ////phraseList.AddPhrase("Miri");


                speechRecognizer.Recognizing += (s, e) =>
                {
                    Console.WriteLine("\n    Recognizing event." + DateTime.Now.ToString("hh:mm:ss.ffffff"));
                    if (!ObeyRecognizedSyl) return; //20230227 
                    //to avoid recognizing when bug already opposite twinkle
                    sb.AppendLine($"RECOGNIZING: Text={e.Result.Text}");
                    Console.WriteLine($"\n RECOGNIZING: Text={e.Result.Text}");
                    //Re $: https://stackoverflow.com/questions/31014869/what-does-mean-before-a-string
                    string[] words = e.Result.Text.Split();
                    int len = words.Length;
                    if (len == 0) lastRecoWord = "";
                    else
                    {
                        lastRecoWord = words[len - 1];
                        lastrecolower = lastRecoWord.ToLower(); //20230226 EE to ee
                        //20230226 tentative
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
                        if(!Teacher_Demo) //20240729
                        //20230518
                        NRecoAttemptsCurrent[SylNeeded]++;
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
                        Console.WriteLine("\n    Canceled event. " + DateTime.Now.ToString("hh:mm:ss.ffffff"));
                        Console.WriteLine($"\n CANCELED: ErrorCode={e.ErrorCode}");
                        Console.WriteLine($"\n CANCELED: ErrorDetails={e.ErrorDetails}");
                    }
                    //btn_StartReco.Text = "Canceled...Speak"; //2023/03/31
                    btn_StartReco.Left = pic_Bug.Left;
                    btn_StartReco.Top = pic_Bug.Top;
                    //pic_Bug.Visible = false;
                    //btn_StartReco.Enabled = true; //2023/03/31
                    //btn_StartReco.Visible = true; //2023/04/01
                    StopRecognitionFromCancelled = true;
                    stopRecognition.TrySetResult(0);
                };

                speechRecognizer.SessionStarted += (s, e) =>
                {
                    //Console.WriteLine("\n    Session started event.");
                    Console.WriteLine("\n    Session" + $" {nStartReco}" + " started event. " + DateTime.Now.ToString("hh:mm:ss.ffffff"));
                    sb.AppendLine($"    Session started event.");
                };

                speechRecognizer.SessionStopped += (s, e) =>
                {
                    //Console.WriteLine("\n    Session stopped event.");
                    Console.WriteLine("\n    Session" + $" {nStartReco}" + " stopped event. " + DateTime.Now.ToString("hh:mm:ss.ffffff"));
                    Console.WriteLine("\nStop recognition.");
                    sb.AppendLine($"    Session stopped event.");
                    sb.AppendLine($"Stop recognition.");
                    StoppedReco = true;
                    stopRecognition.TrySetResult(0);
                };

                // Starts continuous recognition. Uses StopContinuousRecognitionAsync() to stop recognition.
                await speechRecognizer.StartContinuousRecognitionAsync().ConfigureAwait(false);

                // Waits for completion.
                // Use Task.WaitAny to keep the task rooted.
                Task.WaitAny(new[] { stopRecognition.Task });

                // Stops recognition.
                await speechRecognizer.StopContinuousRecognitionAsync().ConfigureAwait(false);

                //txt_RecoOutput.Text = sb.ToString();

            }
        }
btn_StartReco_Click.txt
Displaying btn_StartReco_Click.txt.