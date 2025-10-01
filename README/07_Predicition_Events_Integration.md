Hi Theo — event handling is now available using the LIVE website.

Below is one single copy‑paste block that includes the cover note, instructions, and the exact C# code you can drop into a WinForms app using WebView2. This runs the live site inside your app and forwards prediction events directly into your C# code.

— Copy everything from the next line down —

Hi Theo,

Event handling is now available from the live Soundsgood website in a way your C# app can consume in real time.

Summary:
- You will embed the live website inside a WebView2 control (Microsoft Edge engine) inside your WinForms app.
- The website already emits a browser event named sg:prediction each time it produces a prediction.
- We inject a tiny script that forwards that event payload to your C# code via chrome.webview.postMessage.
- In C#, you receive the label and probability and can respond immediately (e.g., show text, play a sound, call your existing code).

Steps (one time setup):
1) Create a new Windows Forms App in Visual Studio (.NET 6/7/8).
2) Add the NuGet package: Microsoft.Web.WebView2
3) Drop a WebView2 control onto your main form and name it: webView
4) Replace your Form1.cs with the code below (edit the BaseUrl to the live site URL):

Form1.cs (replace content):

using Microsoft.Web.WebView2.Core;
using System;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Media;

public partial class Form1 : Form
{
    // Set this to your live website base URL, for example:
    // private const string BaseUrl = "https://dazzling-respect.up.railway.app";
    private const string BaseUrl = "https://<your-live-site-domain>";

    public Form1()
    {
        InitializeComponent();
        _ = InitAsync();
    }

    private async Task InitAsync()
    {
        // Ensure WebView2 core is ready
        await webView.EnsureCoreWebView2Async();

        // Inject a script that forwards the website's sg:prediction events to C# as messages
        await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(@"
            window.addEventListener('sg:prediction', e => {
              try { chrome.webview.postMessage(JSON.stringify(e.detail)); } catch (err) {}
            });
        ");

        // Receive forwarded prediction events in C#
        webView.CoreWebView2.WebMessageReceived += (s, e) =>
        {
            try
            {
                using var doc = JsonDocument.Parse(e.TryGetWebMessageAsString());
                var root = doc.RootElement;

                // Try to use the pre-extracted 'top' result if present
                string label;
                double prob;
                if (root.TryGetProperty("top", out var top))
                {
                    label = top.GetProperty("label").GetString();
                    prob  = top.GetProperty("prob").GetDouble();
                }
                else
                {
                    // Fallback to first prediction entry
                    var first = root.GetProperty("result").GetProperty("predictions")[0];
                    label = first.GetProperty("label").GetString();
                    prob  = first.TryGetProperty("prob", out var p) ? p.GetDouble()
                          : first.GetProperty("confidence").GetDouble();
                }

                // Example: Beep and put the result in the form title
                SystemSounds.Beep.Play();
                BeginInvoke(new Action(() =>
                {
                    Text = $"Prediction: {label}  ({prob:P0})";
                }));

                // TODO: Call your existing handler here
                // MyHandler.OnPrediction(label, prob);
            }
            catch
            {
                // Ignore any parse errors to avoid breaking the UI
            }
        };

        // Navigate to the live login page; after login, go to /predict and use the site normally
        webView.CoreWebView2.Navigate($"{BaseUrl}/login");
    }
}

How to use it during a session:
- Start the app; you’ll see the live website login page inside the window.
- Log in with your account.
- Navigate to /predict (either manually or by clicking in the site’s UI).
- Choose your dictionary and model as usual.
- Speak a word; each time the site makes a prediction, your C# handler (above) receives the event with label and probability immediately.
- Replace the TODO call with your own code that announces/records/displays the label.

Notes:
- No local backend required—this uses the live website.
- If you need a direct feed without embedding the website UI, you can also subscribe to the live event stream at: https://<your-live-site-domain>/api/predictions/stream (SSE). I can send that short snippet separately if you want it.

Thanks,
Ron

