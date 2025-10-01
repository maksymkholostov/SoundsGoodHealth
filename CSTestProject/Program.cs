// CSTestProject/Program.cs
// This is a test project for the SoundClassifiers API.
// It is used to test the API and ensure that it is working correctly.  

using System;
using System.IO;
using System.Net.Http; // Need this for HttpRequestException
using System.Threading.Tasks;
using SoundClassifiersClient; // Your client namespace

class Program
{
    // --- Configuration ---
    // URLs for both environments
    private const string ProductionApiUrl = "https://www.soundsgood.health";
    private const string LocalApiUrl = "http://localhost:5001"; // Default local Flask port

    // Model and File Path (Update these)
    private const string ModelId    = "56b79c08-c58f-41cd-a7b6-f515ba04b5b6"; // PASTE A VALID MODEL ID
    private const string TestWavFilePath = "Eh.wav"; // PASTE FULL PATH or relative if in same folder
    // Windows example path:   private const string TestWavFilePath = @"C:\path\to\your\test_audio.wav"; 
    // macOS/Linux example path: private const string TestWavFilePath = @"/Users/your_user/path/to/your/test_audio.wav"; 
    // --- End Configuration ---

    static async Task Main(string[] args)
    {
        Console.WriteLine("--- SoundClassifiers C# Client Test ---");

        // --- 1. Check Test File Existence ---
        Console.WriteLine($"Checking for test audio file at: {TestWavFilePath}");
        if (!File.Exists(TestWavFilePath))
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Error: Test WAV file not found.");
            Console.ResetColor(); ExitPrompt(); return;
        }
        Console.WriteLine("Test file found.");

        // --- 2. Read Audio File ---
        byte[] audioBytes = null;
        try
        {
            Console.WriteLine("Attempting to read file bytes directly...");
            audioBytes = File.ReadAllBytes(TestWavFilePath);
            Console.WriteLine($"Successfully read {audioBytes.Length} bytes from file.");
        }
        catch (Exception readEx)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"ERROR reading file: {readEx.GetType().Name} - {readEx.Message}");
            Console.ResetColor(); ExitPrompt(); return;
        }

        // --- 3. Attempt Recognition (Production First, then Local Fallback) ---
        RecognitionResult result = null;
        bool triedProduction = false;
        bool triedLocal = false;

        // --- Attempt 1: Production URL ---
        Console.WriteLine($"\nAttempting API call to PRODUCTION: {ProductionApiUrl}");
        triedProduction = true;
        result = await TryApiCall(ProductionApiUrl, ModelId, audioBytes);

        // --- Attempt 2: Local URL (if Production failed) ---
        if (result == null) // Check if TryApiCall returned null (indicating failure)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"Production API call failed. Falling back to LOCAL: {LocalApiUrl}");
            Console.ResetColor();
            triedLocal = true;
            result = await TryApiCall(LocalApiUrl, ModelId, audioBytes);
        }

        // --- 4. Process Final Result ---
        Console.WriteLine("\n--- Final Result ---");
        if (result != null)
        {
             ProcessAndDisplayResult(result, triedProduction ? ProductionApiUrl : LocalApiUrl);
        }
        else
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("ERROR: Both Production and Local API calls failed.");
            if (!triedLocal) Console.WriteLine("(Did not attempt local fallback because production call seemed successful but returned null result object).");
             Console.WriteLine("Check Flask server logs (local or Railway) and network connection.");
            Console.ResetColor();
        }

        ExitPrompt();
    }

    // --- Helper Function to Isolate API Call and Error Handling ---
    static async Task<RecognitionResult?> TryApiCall(string baseUrl, string modelId, byte[] audioBytes)
    {
        SoundClassifiersClient.SoundClassifiersClient? scClient = null;
        try
        {
            // Initialize client for this attempt
            scClient = new SoundClassifiersClient.SoundClassifiersClient(
                baseUrl: baseUrl,
                modelId: modelId
            );
            Console.WriteLine($"  Client initialized for {baseUrl}.");

            // Perform the recognition
            Console.WriteLine($"  Calling RecognizeFromDataAsync for Model ID: {modelId}...");
            RecognitionResult apiResult = await scClient.RecognizeFromDataAsync(audioBytes);
            Console.WriteLine($"  API call to {baseUrl} completed.");

            // Basic check: Return the result object even if it indicates "No Match" or API-level error
            if (apiResult == null)
            {
                 Console.ForegroundColor = ConsoleColor.DarkYellow;
                 Console.WriteLine($"  Warning: API call to {baseUrl} returned a null result object.");
                 Console.ResetColor();
            }
            // We return the result object itself; the caller will decide if it's a "success"
            return apiResult;

        }
        catch (HttpRequestException httpEx)
        {
             Console.ForegroundColor = ConsoleColor.DarkYellow; // Use yellow for non-fatal attempt failure
             Console.WriteLine($"  Network Error connecting to {baseUrl}: {httpEx.Message}");
             if (httpEx.InnerException != null) Console.WriteLine($"  Inner Exception: {httpEx.InnerException.Message}");
             Console.ResetColor();
             return null; // Indicate failure
        }
        catch (Exception ex) // Catch other unexpected errors during this specific attempt
        {
             Console.ForegroundColor = ConsoleColor.DarkYellow;
             Console.WriteLine($"  Unexpected Error during call to {baseUrl}: {ex.GetType().Name} - {ex.Message}");
             // Console.WriteLine($"  Stack Trace:\n{ex.StackTrace}"); // Uncomment for more detail if needed
             Console.ResetColor();
             return null; // Indicate failure
        }
    }

    // --- Helper Function to Display Results ---
    static void ProcessAndDisplayResult(RecognitionResult result, string sourceUrl)
    {
         Console.WriteLine($"Response received from: {sourceUrl}");
         // Check for null result object (should have been caught by caller, but good practice)
         if (result == null) {
              Console.ForegroundColor = ConsoleColor.Red;
              Console.WriteLine("ERROR: Result object is null.");
              Console.ResetColor();
              return;
         }

         // Check if a phoneme was recognized
         if (!string.IsNullOrEmpty(result.Phoneme))
         {
             Console.ForegroundColor = ConsoleColor.Green;
             Console.WriteLine($"Status:     Success");
             Console.WriteLine($"Phoneme:    {result.Phoneme}");
             Console.ResetColor();

             if (result.Alternatives != null && result.Alternatives.Count > 0)
             {
                 Console.WriteLine("Alternatives:");
                 foreach (var alt in result.Alternatives)
                 {
                     Console.WriteLine($"  - {alt.Phoneme}");
                 }
             }
         }
         else
         {
             // API call was likely okay, but model didn't recognize anything confidently
             Console.ForegroundColor = ConsoleColor.Yellow;
             Console.WriteLine($"Status:     No Match / Unrecognized");
             Console.WriteLine($"Details:    API call to {sourceUrl} succeeded, but no phoneme was recognized confidently.");
             Console.ResetColor();
         }
         Console.WriteLine("------------------");
    }

    static void ExitPrompt()
    {
         Console.WriteLine("\nTest finished. Press Enter to exit.");
         Console.ReadLine();
    }
}
