# API Documentation - SoundClassifiers v10
Updated August 9, 2025

## Overview

The SoundClassifiers v10 API provides comprehensive endpoints for audio classification, model training, and speech recognition. The API supports both REST endpoints for web clients and specialized endpoints for C# client integration.

## Base URL
- **Production**: `https://www.soundsgood.health/api`
- **Local Development**: `http://localhost:5001/api`

## Authentication

### Methods
1. **Session-Based**: Login through web interface or API
2. **API Token**: Use `X-API-Token` header for programmatic access
3. **Model ID**: For custom speech API (C# clients)

### Getting an API Token
```http
POST /api/auth/token
Authorization: Session cookie or existing token
```

## API Endpoints

### 1. Custom Speech API (C# Integration)

#### Recognize Sound
```http
POST /api/speech/recognize
```

**Parameters:**
- **Option 1 - File Upload:**
  - `audio`: WAV file (multipart/form-data)
  - `model_id`: Model identifier (form field)
  
- **Option 2 - Base64 Stream:**
  - `audio_data`: Base64 encoded audio (JSON)
  - `model_id`: Model identifier (JSON)

**Response:**
```json
{
  "success": true,
  "phoneme": "ah",
  "alternatives": [
    {"phoneme": "oh", "confidence": 0.85}
  ],
  "confidence": 0.92,
  "model_id": "model_123"
}
```

#### List Available Models
```http
GET /api/speech/models
```

**Query Parameters:**
- `user_id` (optional): Filter models by user

**Response:**
```json
{
  "success": true,
  "models": [
    {
      "id": "model_123",
      "name": "Vowel Classifier",
      "description": "Trained on vowel sounds",
      "created_at": "2025-08-01T10:00:00Z",
      "dictionary_name": "Vowels",
      "accuracy": 0.95
    }
  ]
}
```

### 2. Authentication Endpoints

#### Register New User
```http
POST /api/auth/register
Content-Type: application/json
```

**Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json
```

**Body:**
```json
{
  "username_or_email": "john_doe",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "success": true,
  "user": {...},
  "api_token": "token_abc123..."
}
```

### 3. Recording Management

#### Upload Recording
```http
POST /api/recordings/<user_id>/<class_name>
```

**Parameters:**
- `audio`: WAV file (multipart/form-data)

#### Stream Recording
```http
POST /api/recordings/stream/<user_id>/<class_name>
Content-Type: application/json
```

**Body:**
```json
{
  "audio_data": "base64_encoded_audio_data..."
}
```

#### Get Recordings by Class
```http
GET /api/recordings/by-class/<user_id>/<class_name>
```

#### Verify Recording Segment
```http
POST /api/segments/verify/<segment_id>
Content-Type: application/json
```

**Body:**
```json
{
  "approved": true
}
```

### 4. Model Training

#### Train New Model
```http
POST /api/models/train
Content-Type: application/json
Authorization: Session or API Token
```

**Body:**
```json
{
  "user_id": "user_123",
  "dictionary_id": "dict_456",
  "model_type": "RF",
  "model_name": "My Classifier",
  "use_augmented": true,
  "params": {
    "n_estimators": 100,
    "max_depth": 10
  }
}
```

**Model Types:**
- `RF`: Random Forest
- `CNN`: Convolutional Neural Network
- `SVM`: Support Vector Machine
- `ENSEMBLE`: Combined models

#### Get Trained Models
```http
GET /api/models/<user_id>/<dictionary_id>
```

#### Delete Model
```http
DELETE /api/models/<user_id>/<dictionary_id>/<model_id>
Authorization: Session or API Token
```

### 5. Inference/Prediction

#### Predict from File
```http
POST /api/inference
```

**Parameters:**
- `audio`: WAV file (multipart/form-data)
- `user_id`: User identifier
- `dictionary_id`: Dictionary identifier
- `model_id`: Model identifier
- `save_result` (optional): Save prediction for analysis
- `actual_class` (optional): For feedback/evaluation

**Response:**
```json
{
  "success": true,
  "prediction": {
    "predicted_class": "ah",
    "confidence": 0.89,
    "alternatives": [
      {"class": "oh", "confidence": 0.75}
    ],
    "processing_time": 0.125
  }
}
```

#### Predict from Stream
```http
POST /api/inference/stream
Content-Type: application/json
```

**Body:**
```json
{
  "user_id": "user_123",
  "dictionary_id": "dict_456",
  "model_id": "model_789",
  "audio_data": "base64_encoded_audio..."
}
```

### 6. Dictionary Management

#### Create Dictionary
```http
POST /api/dictionary/create
Content-Type: application/json
Authorization: Required
```

**Body:**
```json
{
  "name": "Vowel Sounds",
  "description": "Collection of vowel phonemes",
  "classes": ["ah", "ee", "oh", "oo"]
}
```

#### List Dictionaries with Models
```http
GET /api/dictionary/list-with-models
Authorization: Required
```

#### Add Class to Dictionary
```http
POST /api/dictionary/<dictionary_id>/add_class
Content-Type: application/json
Authorization: Required
```

**Body:**
```json
{
  "class_name": "uh",
  "description": "Short u sound"
}
```

### 7. Data Augmentation

#### Start Augmentation
```http
POST /api/augmentation/start
Content-Type: application/json
Authorization: Required
```

**Body:**
```json
{
  "target_type": "dictionary",
  "target_id": "dict_123",
  "strategy": "fixed",
  "fixed_number": 10,
  "config": {
    "pitch_shift_range": [-2, 2],
    "time_stretch_range": [0.9, 1.1],
    "noise_level_range": [0.001, 0.005]
  }
}
```

#### Get Augmentation Status
```http
GET /api/augmentation/status/<dictionary_id>/<class_name>
Authorization: Required
```

### 8. Feature Extraction

#### Extract Features
```http
POST /api/features/extract
Content-Type: application/json
Authorization: Required
```

**Body:**
```json
{
  "recording_ids": ["rec_1", "rec_2", "rec_3"]
}
```

### 9. System Statistics

#### Dashboard Stats
```http
GET /api/dashboard/stats
Authorization: Required
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "models": 5,
    "classes": 12,
    "dictionaries": 3,
    "original_recordings": 150,
    "augmented_recordings": 750,
    "pending_recordings": 25,
    "total_recordings": 925
  }
}
```

## Error Handling

All endpoints follow a consistent error response format:

```json
{
  "success": false,
  "error": "Error message description",
  "details": {} 
}
```

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request - Invalid parameters
- `401`: Unauthorized - Authentication required
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `500`: Internal Server Error

## Rate Limiting

- API calls are limited to 100 requests per minute per IP
- Batch operations count as single requests
- Contact support for higher limits

## Best Practices

### Audio Format
- **Preferred**: 16kHz, 16-bit, mono WAV
- **Supported**: Most WAV formats (automatically converted)
- **Max File Size**: 10MB per audio file

### Model Training
1. Ensure sufficient Gold recordings (10+ per class)
2. Use augmentation for better performance
3. Start with Random Forest for baseline
4. Monitor training progress via status endpoint

### C# Client Integration
1. Always include model_id in requests
2. Handle base64 encoding properly
3. Implement retry logic for network failures
4. Cache model list to reduce API calls

### Security
1. Never expose API tokens in client-side code
2. Use HTTPS in production
3. Rotate tokens periodically
4. Validate audio data before processing

## Code Examples

### Python
```python
import requests
import base64

# Recognize sound
with open('audio.wav', 'rb') as f:
    audio_data = base64.b64encode(f.read()).decode()

response = requests.post(
    'https://www.soundsgood.health/api/speech/recognize',
    json={
        'audio_data': audio_data,
        'model_id': 'model_123'
    }
)

result = response.json()
print(f"Predicted: {result['phoneme']}")
```

### C# 
```csharp
using var client = new HttpClient();
var content = new MultipartFormDataContent();
content.Add(new ByteArrayContent(audioBytes), "audio", "audio.wav");
content.Add(new StringContent(modelId), "model_id");

var response = await client.PostAsync(
    "https://www.soundsgood.health/api/speech/recognize",
    content
);

var result = await response.Content.ReadAsStringAsync();
```

### JavaScript
```javascript
const formData = new FormData();
formData.append('audio', audioBlob, 'audio.wav');
formData.append('model_id', 'model_123');

const response = await fetch('/api/speech/recognize', {
    method: 'POST',
    body: formData
});

const result = await response.json();
console.log(`Predicted: ${result.phoneme}`);
```

## Support

For API support, feature requests, or bug reports:
- Email: support@soundsgood.health
- Documentation: https://www.soundsgood.health/developer
- Status Page: https://status.soundsgood.health

---

*Last Updated: August 2025*
*API Version: 1.0*