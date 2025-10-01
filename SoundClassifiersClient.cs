// SoundClassifiersClient.cs
//
// Client library for connecting to SoundClassifiers API for phoneme recognition
// This replaces Azure Speech SDK with a direct connection to the SoundClassifiers model API.

using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace SoundClassifiersClient
{
    /// <summary>
    /// Client for connecting to the SoundClassifiers API
    /// </summary>
    public class SoundClassifiersClient
    {
        private readonly HttpClient _httpClient;
        private readonly string _baseUrl;
        private readonly string _modelId;

        /// <summary>
        /// Initialize a new SoundClassifiers client
        /// </summary>
        /// <param name="baseUrl">Base URL of the SoundClassifiers API (e.g., "https://www.soundsgood.health")</param>
        /// <param name="modelId">ID of the model to use for inference</param>
        public SoundClassifiersClient(string baseUrl = "https://www.soundsgood.health", 
                                     string modelId = "your-model-id")
        {
            _httpClient = new HttpClient();
            _baseUrl = baseUrl.TrimEnd('/');
            _modelId = modelId;
        }

        /// <summary>
        /// Get a list of available models from the API
        /// </summary>
        /// <param name="userId">Optional user ID to filter models</param>
        /// <returns>List of available models</returns>
        public async Task<List<ModelInfo>> GetAvailableModelsAsync(string userId = null)
        {
            try
            {
                var url = $"{_baseUrl}/api/speech/models";
                
                // Add query parameters if provided
                var queryParams = new List<string>();
                if (!string.IsNullOrEmpty(userId))
                    queryParams.Add($"user_id={Uri.EscapeDataString(userId)}");

                if (queryParams.Count > 0)
                    url += "?" + string.Join("&", queryParams);

                // Make the request
                var response = await _httpClient.GetAsync(url);
                response.EnsureSuccessStatusCode();

                var content = await response.Content.ReadAsStringAsync();
                var result = JsonConvert.DeserializeObject<ModelsResponse>(content);

                if (result.Success)
                    return result.Models;
                else
                    throw new Exception($"API Error: {result.Error}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error retrieving models: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Recognize phonemes from an audio file
        /// </summary>
        /// <param name="audioFilePath">Path to the WAV audio file</param>
        /// <returns>Recognition result</returns>
        public async Task<RecognitionResult> RecognizeFromFileAsync(string audioFilePath)
        {
            try
            {
                var url = $"{_baseUrl}/api/speech/recognize";

                // Create multipart form content
                using (var formContent = new MultipartFormDataContent())
                {
                    // Add audio file
                    var fileContent = new ByteArrayContent(File.ReadAllBytes(audioFilePath));
                    fileContent.Headers.ContentType = MediaTypeHeaderValue.Parse("audio/wav");
                    formContent.Add(fileContent, "audio", Path.GetFileName(audioFilePath));

                    // Add model ID
                    formContent.Add(new StringContent(_modelId), "model_id");

                    // Make the request
                    var response = await _httpClient.PostAsync(url, formContent);
                    response.EnsureSuccessStatusCode();

                    var content = await response.Content.ReadAsStringAsync();
                    var result = JsonConvert.DeserializeObject<RecognitionResponse>(content);

                    if (result.Success)
                        return new RecognitionResult
                        {
                            Phoneme = result.Phoneme,
                            Confidence = result.Confidence,
                            Alternatives = result.Alternatives
                        };
                    else
                        throw new Exception($"API Error: {result.Error}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error recognizing audio: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Recognize phonemes from audio data in memory
        /// </summary>
        /// <param name="audioData">Raw audio data (WAV format)</param>
        /// <returns>Recognition result</returns>
        public async Task<RecognitionResult> RecognizeFromDataAsync(byte[] audioData)
        {
            try
            {
                var url = $"{_baseUrl}/api/speech/recognize";

                // Convert audio data to base64
                var base64Audio = Convert.ToBase64String(audioData);

                // Create JSON payload
                var payload = new
                {
                    model_id = _modelId,
                    audio_data = base64Audio
                };

                var jsonContent = new StringContent(
                    JsonConvert.SerializeObject(payload),
                    Encoding.UTF8,
                    "application/json"
                );

                // Make the request
                var response = await _httpClient.PostAsync(url, jsonContent);
                response.EnsureSuccessStatusCode();

                var content = await response.Content.ReadAsStringAsync();
                var result = JsonConvert.DeserializeObject<RecognitionResponse>(content);

                if (result.Success)
                    return new RecognitionResult
                    {
                        Phoneme = result.Phoneme,
                        Confidence = result.Confidence,
                        Alternatives = result.Alternatives
                    };
                else
                    throw new Exception($"API Error: {result.Error}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error recognizing audio: {ex.Message}");
                throw;
            }
        }
    }

    // Response models

    public class ModelsResponse
    {
        public bool Success { get; set; }
        public string Error { get; set; }
        public List<ModelInfo> Models { get; set; }
    }

    public class ModelInfo
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public string CreatedAt { get; set; }
        public string DictionaryName { get; set; }
        public string UserId { get; set; }
    }

    public class RecognitionResponse
    {
        public bool Success { get; set; }
        public string Error { get; set; }
        public string Phoneme { get; set; }
        public double Confidence { get; set; }
        public List<AlternativeResult> Alternatives { get; set; }
        public string ModelId { get; set; }
    }

    public class RecognitionResult
    {
        public string Phoneme { get; set; }
        public double Confidence { get; set; }
        public List<AlternativeResult> Alternatives { get; set; }
    }

    public class AlternativeResult
    {
        public string Phoneme { get; set; }
        public double Confidence { get; set; }
    }
} 