## Prediction Events Integration (C# WinForms and WebView2)

This guide shows two ways to receive real-time prediction events from the Soundsgood web app and use them in a C# application built in Visual Studio (WinForms).

- Option A: Subscribe to a server-sent events (SSE) stream at `/api/predictions/stream` from any C# process.
- Option B: Host the website inside a WebView2 control and receive prediction events from the page via a browser CustomEvent named `sg:prediction`.

Both options are passive (no behavior change to the site) and can be used independently.

---

## 1) Prerequisites

- Windows 10/11
- Visual Studio (not VS Code), with .NET Desktop Development workload
- .NET 6/7/8
- Soundsgood backend running locally on `http://localhost:5001`
  - Start:
    ```cmd
    .\venv\Scripts\python.exe run.py --no-browser --port 5001
    ```
- A user account for the site (for login)

If your backend runs elsewhere, adjust the URLs below.

---

## 2) What events look like

Two mechanisms produce identical information in slightly different shapes:

- Backend SSE stream (external C# apps)
  - `GET /api/predictions/stream` → `text/event-stream`
  - Example event:
    ```json
    {
      "event": "prediction",
      "timestamp": 1758423500.123,
      "dictionary_id": "dict_mohmoo",
      "model_id": "cnn1d_dict_mohmoo_...",
      "result": {
        "predictions": [
          { "label": "moo", "prob": 0.91 },
          { "label": "moh", "prob": 0.09 }
        ]
      }
    }
    ```

- Frontend CustomEvent (WebView2)
  - Event name: `sg:prediction` (fired on `window`)
  - Payload (`event.detail`):
    ```json
    {
      "dictionary_id": "dict_mohmoo",
      "model_id": "cnn1d_dict_mohmoo_...",
      "audio_id": "audio_...",
      "result": { "predictions": [ {"label": "moo", "prob": 0.91} ] },
      "top": { "label": "moo", "prob": 0.91 },
      "timestamp": 1695240000000
    }
    ```

---

## 3) Option A – C# WinForms app consuming SSE

This works for any C# process (WinForms/WPF/Console/Service). The app connects to the SSE endpoint and continuously reads events.

### 3.1 Create a WinForms project

1. Visual Studio → Create a new project → "Windows Forms App" (.NET 6/7/8)
2. Name it `PredictionEventsDemo`
3. Add a `ListBox` named `listEvents` and a `Button` named `btnStart` (Text: "Start Listening")

### 3.2 Add an SSE client class

Create `SseClient.cs`:

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace PredictionEventsDemo
{
    public sealed class SseClient : IAsyncDisposable
    {
        private readonly HttpClient _http;
        private readonly Uri _uri;
        private CancellationTokenSource? _cts;

        public event EventHandler<JsonDocument>? EventReceived;
        public event EventHandler<Exception>? Error;

        public SseClient(string url)
        {
            _uri = new Uri(url);
            _http = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
        }

        public async Task StartAsync(CancellationToken externalToken = default)
        {
            _cts = CancellationTokenSource.CreateLinkedTokenSource(externalToken);
            try
            {
                using var response = await _http.GetAsync(_uri, HttpCompletionOption.ResponseHeadersRead, _cts.Token);
                response.EnsureSuccessStatusCode();

                await using var stream = await response.Content.ReadAsStreamAsync(_cts.Token);
                using var reader = new StreamReader(stream);

                while (!_cts.IsCancellationRequested && !reader.EndOfStream)
                {
                    var line = await reader.ReadLineAsync();
                    if (string.IsNullOrWhiteSpace(line)) continue;
                    if (!line.StartsWith("data:")) continue; // SSE payload line

                    var json = line.Substring("data:".Length).TrimStart();
                    try
                    {
                        using var doc = JsonDocument.Parse(json);
                        EventReceived?.Invoke(this, doc);
                    }
                    catch (Exception ex)
                    {
                        Error?.Invoke(this, ex);
                    }
                }
            }
            catch (Exception ex)
            {
                Error?.Invoke(this, ex);
            }
        }

        public void Stop() => _cts?.Cancel();

        public async ValueTask DisposeAsync()
        {
            Stop();
            _http.Dispose();
            _cts?.Dispose();
            await Task.CompletedTask;
        }
    }
}
```

### 3.3 Wire it in the Form

`Form1.cs`:

```csharp
using System;
using System.Text.Json;
using System.Threading;
using System.Windows.Forms;

namespace PredictionEventsDemo
{
    public partial class Form1 : Form
    {
        private SseClient? _client;
        private readonly SynchronizationContext _ui;

        public Form1()
        {
            InitializeComponent();
            _ui = SynchronizationContext.Current!; // capture UI context
        }

        private async void btnStart_Click(object sender, EventArgs e)
        {
            btnStart.Enabled = false;

            _client = new SseClient("http://localhost:5001/api/predictions/stream");

            _client.EventReceived += (s, doc) =>
            {
                try
                {
                    var root = doc.RootElement;
                    var dictId = root.GetProperty("dictionary_id").GetString();
                    var modelId = root.GetProperty("model_id").GetString();
                    var top = root.GetProperty("result").GetProperty("predictions")[0];
                    var label = top.GetProperty("label").GetString();
                    var prob = top.GetProperty("prob").GetDouble();

                    _ui.Post(_ => listEvents.Items.Insert(0, $"{DateTime.Now:T} | {dictId} | {modelId} | {label} {prob:P1}"), null);
                }
                catch (Exception ex)
                {
                    _ui.Post(_ => listEvents.Items.Insert(0, $"Parse error: {ex.Message}"), null);
                }
            };

            _client.Error += (s, ex) => _ui.Post(_ => listEvents.Items.Insert(0, $"SSE error: {ex.Message}"), null);

            await _client.StartAsync();
        }
    }
}
```

Run the app, click "Start Listening", then perform predictions in the website. New lines will appear in the list.

> Tip: add a reconnection loop if you want to auto-reconnect after server restarts.

---

## 4) Option B – WebView2: embed the site and receive browser events

This is ideal when you want the site inside a native window and direct event forwarding from the page.

### 4.1 Add WebView2 to a WinForms project

1. Create a WinForms project
2. Add the NuGet package `Microsoft.Web.WebView2`
3. Drop a `WebView2` control on the form and name it `webView`

### 4.2 Initialize and handle prediction messages

`Form1.cs`:

```csharp
using Microsoft.Web.WebView2.Core;
using System;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace WebViewPredictionDemo
{
    public partial class Form1 : Form
    {
        public Form1()
        {
            InitializeComponent();
            _ = InitAsync();
        }

        private async Task InitAsync()
        {
            await webView.EnsureCoreWebView2Async();

            // Bridge sg:prediction events to C# via postMessage
            await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(@"
                window.addEventListener('sg:prediction', e => {
                  try { chrome.webview.postMessage(JSON.stringify(e.detail)); } catch (err) {}
                });
            ");

            webView.CoreWebView2.WebMessageReceived += (s, e) =>
            {
                try
                {
                    using var doc = JsonDocument.Parse(e.TryGetWebMessageAsString());
                    var root = doc.RootElement;
                    var dictId = root.GetProperty("dictionary_id").GetString();
                    var modelId = root.GetProperty("model_id").GetString();
                    var top = root.GetProperty("top");
                    var label = top.GetProperty("label").GetString();
                    var prob = top.GetProperty("prob").GetDouble();

                    BeginInvoke(new Action(() =>
                    {
                        Text = $"{dictId} | {modelId} | {label} {prob:P1}"; // example UI update
                    }));
                }
                catch (Exception ex)
                {
                    BeginInvoke(new Action(() => Text = $"Parse error: {ex.Message}"));
                }
            };

            // Navigate to login page first
            webView.CoreWebView2.Navigate("http://localhost:5001/login");
        }
    }
}
```

### 4.3 Login & navigate to predictor

1. When the WebView opens, log in (session cookies are stored automatically).
2. After login, either:
   - Navigate manually to `/predict` and select a dictionary + model, or
   - Navigate programmatically:
     ```csharp
     webView.CoreWebView2.NavigationCompleted += (s, e) =>
     {
         if (webView.Source.AbsoluteUri.EndsWith("/login") && e.IsSuccess)
         {
             Task.Delay(500).ContinueWith(_ =>
                 webView.CoreWebView2.Navigate("http://localhost:5001/predict"));
         }
     };
     ```
3. The page emits `sg:prediction` for every result; the injected script forwards them to C#.

### 4.4 Verify in a normal browser (optional)

Open DevTools Console and paste:
```js
window.addEventListener('sg:prediction', e => console.log('prediction event:', e.detail));
```
Make a prediction to see the payload.

---

## 5) Troubleshooting

- Confirm the SSE stream is reachable:
  ```cmd
  curl -N http://localhost:5001/api/predictions/stream
  ```
  You should see an initial `data: {"event":"hello", ...}` line. Make a prediction; new JSON lines should appear.

- Predictions work but SSE shows nothing:
  - Restart the backend after adding the feature
  - Ensure predictions go through `/api/inference/classify` or `/api/inference` (both publish now)
  - Keep `curl` open while predicting

- WebView2 bridge isn’t firing:
  - Ensure the injection script is added before navigating to `/predict`
  - Confirm you are logged in and receiving predictions in the UI

---

## 6) Security & performance

- SSE is read-only; in local dev it’s unauthenticated. If exposed publicly, protect it (cookies/tokens/proxy rules).
- Each client has a bounded queue; slow clients may drop events without affecting the site.
- All publish/dispatch code is wrapped in try/catch to avoid breaking normal flows.

---

## 7) Files involved

- `backend/app/api/prediction_events.py` – SSE endpoint `/api/predictions/stream` and `publish_prediction_event()`.
- `backend/app/api/inference.py` – publishes SSE events after API predictions.
- `backend/app/routes/inference_routes.py` – publishes SSE events after web `/api/inference/classify` predictions.
- `backend/app/__init__.py` – registers the SSE blueprint.
- `frontend/static/js/predict_api.js` – dispatches `sg:prediction` CustomEvent on `window`.

Safe to deploy; behavior is unchanged unless a listener connects.
