# IRAS Callback API Server

A comprehensive Flask-based callback API server for handling IRAS (Inland Revenue Authority of Singapore) service callbacks. This server provides endpoints for GST returns, Corporate Secretary forms, commission records, donation records, and e-stamping submissions.

## 🚀 Live Demo

- **API Base URL**: `https://test-callback-api.onrender.com`
- **Health Check**: `https://test-callback-api.onrender.com/health`
- **Documentation**: `https://test-callback-api.onrender.com/docs`

## 📋 Table of Contents

- [Features](#features)
- [IRAS Callback Endpoints](#iras-callback-endpoints)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Configuration](#configuration)
- [Error Handling](#error-handling)

## ✨ Features

- **5 IRAS Callback Endpoints** for different submission types
- **Comprehensive Input Validation** with Singapore UEN format validation
- **Detailed Logging & Monitoring** with request tracking
- **Mock Testing Endpoints** for development and testing
- **Health Check & Statistics** for monitoring
- **Production-Ready** with proper error handling
- **CORS Support** for cross-origin requests
- **Memory Management** with automatic log rotation

## 🎯 IRAS Callback Endpoints

| Endpoint                            | Description                   | Form Types               |
| ----------------------------------- | ----------------------------- | ------------------------ |
| `/iras/gst-return/callback`         | GST Return submissions        | F5, F8                   |
| `/iras/form-cs/callback`            | Corporate Secretary forms     | Annual returns, changes  |
| `/iras/commission-records/callback` | Commission record submissions | Various commission types |
| `/iras/donation-records/callback`   | Donation record submissions   | Tax-deductible donations |
| `/iras/e-stamping/callback`         | E-stamping submissions        | Document stamping        |

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip package manager

### Local Development

1. **Clone the repository**

   ```bash
   git clone https://github.com/hoangtiot/test-callback-api.git
   cd test-callback-api
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**

   ```bash
   python main.py
   ```

4. **Test the API**
   ```bash
   curl http://localhost:5000/health
   ```

The server will start on `http://localhost:5000`

## 📖 API Documentation

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "platform": " API Hosting + Flask",
  "logs_count": 0,
  "memory_usage": "normal"
}
```

### GST Return Callback

```http
POST /iras/gst-return/callback
Content-Type: application/json
```

**Request Body:**

```json
{
  "submissionId": "GST202501001234",
  "submissionStatus": "SUCCESS",
  "formType": "F5",
  "submissionDateTime": "2025-01-15T14:30:00+08:00",
  "companyUEN": "201234567D",
  "taxPeriod": "202412",
  "acknowledgementNumber": "ACK123456789",
  "totalTaxAmount": 15000.5,
  "errors": []
}
```

**Response:**

```json
{
  "status": "received",
  "message": "GST F5 submission for period 202412 processed successfully",
  "submissionId": "GST202501001234",
  "timestamp": "2025-01-15T14:30:01.000Z",
  "requestId": "abc12345"
}
```

### Required Fields by Endpoint

#### GST Return Callback

- `submissionId` (string): Unique submission identifier
- `submissionStatus` (string): SUCCESS, FAILED, PROCESSING, PENDING, REJECTED, CANCELLED
- `formType` (string): F5 or F8
- `submissionDateTime` (string): ISO datetime
- `companyUEN` (string): Singapore UEN format (12345678A)
- `taxPeriod` (string): YYYYMM format

#### Form CS Callback

- `submissionId`, `submissionStatus`, `submissionDateTime`, `companyUEN`
- `formVersion` (string): Form version
- `filingType` (string): Type of CS filing

#### Commission Records Callback

- `submissionId`, `submissionStatus`, `submissionDateTime`, `companyUEN`
- `recordType` (string): Type of commission record
- `recordPeriod` (string): Period for records

#### Donation Records Callback

- `submissionId`, `submissionStatus`, `submissionDateTime`, `companyUEN`
- `donationType` (string): Type of donation
- `donationPeriod` (string): Period for donations

#### E-Stamping Callback

- `submissionId`, `submissionStatus`, `submissionDateTime`, `companyUEN`
- `documentType` (string): Type of document stamped

## 🧪 Testing

### View API Documentation

```bash
curl https://test-callback-api.onrender.com/docs
```

### Generate Mock Callbacks

```bash
# Test GST callback
curl -X POST https://test-callback-api.onrender.com/test/mock-gst-callback

# Test Form CS callback
curl -X POST https://test-callback-api.onrender.com/test/mock-form-cs-callback
```

### Validate Callback Data

```bash
curl -X POST https://test-callback-api.onrender.com/test/validate-callback?type=gst-return \
  -H "Content-Type: application/json" \
  -d '{
    "submissionId": "GST123",
    "submissionStatus": "SUCCESS",
    "formType": "F5",
    "submissionDateTime": "2025-01-15T14:30:00+08:00",
    "companyUEN": "201234567D",
    "taxPeriod": "202412"
  }'
```

### View Logs and Statistics

```bash
# View recent logs
curl https://test-callback-api.onrender.com/logs?limit=5

# View statistics
curl https://test-callback-api.onrender.com/logs/stats

# Clear logs (testing only)
curl -X DELETE https://test-callback-api.onrender.com/logs
```

## ⚙️ Configuration

### Environment Variables

| Variable     | Description                          | Default        |
| ------------ | ------------------------------------ | -------------- |
| `PORT`       | Server port                          | 5000           |
| `FLASK_ENV`  | Environment (development/production) | production     |
| `SECRET_KEY` | Flask secret key                     | auto-generated |

### IRAS Requirements

Your callback URLs must meet IRAS requirements:

- ✅ **HTTPS only** (automatic with deployment)
- ✅ **Fully Qualified Domain Name** (no IP addresses)
- ✅ **No query parameters** in the URL
- ✅ **Case-sensitive** URLs
- ✅ **Different URLs** for sandbox and production
- ✅ **SSL certificate** (automatic with hosting providers)

### Recommended IRAS Registration URLs

**Sandbox Environment:**

```
https://test-callback-api-staging.onrender.com/iras/gst-return/callback
https://test-callback-api-staging.onrender.com/iras/form-cs/callback
https://test-callback-api-staging.onrender.com/iras/commission-records/callback
https://test-callback-api-staging.onrender.com/iras/donation-records/callback
https://test-callback-api-staging.onrender.com/iras/e-stamping/callback
```

**Production Environment:**

```
https://test-callback-api.onrender.com/iras/gst-return/callback
https://test-callback-api.onrender.com/iras/form-cs/callback
https://test-callback-api.onrender.com/iras/commission-records/callback
https://test-callback-api.onrender.com/iras/donation-records/callback
https://test-callback-api.onrender.com/iras/e-stamping/callback
```

## 🛡️ Error Handling

### Validation Errors (400)

```json
{
  "status": "error",
  "message": "Missing required fields: submissionId, formType",
  "error_id": "abc12345",
  "submissionId": null,
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

### Server Errors (500)

```json
{
  "status": "error",
  "message": "Error processing callback",
  "error_id": "xyz67890",
  "submissionId": "GST123",
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

### UEN Validation

- Format: 8 or 9 digits followed by a letter
- Examples: `201234567D`, `123456789A`
- Case-sensitive letter suffix

### Tax Period Validation

- Format: YYYYMM (6 digits)
- Examples: `202412`, `202501`
- Year range: 2000-2100
- Month range: 01-12

## 📊 Monitoring

### Log Structure

```json
{
  "requestId": "abc12345",
  "timestamp": "2025-01-15T14:30:00.000Z",
  "endpoint": "GST-RETURN",
  "callback_data": { ... },
  "headers": { ... },
  "client_ip": "203.0.113.1",
  "method": "POST",
  "status": "SUCCESS"
}
```

### Memory Management

- Automatic log rotation (max 200 entries)
- Memory usage monitoring
- Request ID tracking for debugging

## 🔧 Development

### Project Structure

```
test-callback-api/
├── main.py              # Flask application
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .gitignore          # Git ignore rules
└── render.yaml         # Render deployment config (optional)
```

### Adding New Endpoints

1. Create validation logic in `CallbackValidator`
2. Add route handler following existing patterns
3. Update documentation and tests
4. Deploy and test

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

- **Issues**: Create a GitHub issue
- **Documentation**: Check `/docs` endpoint
- **Health Check**: Monitor `/health` endpoint

## 🔄 Version History

- **v1.0.0**: Initial release with 5 IRAS callback endpoints
- Full input validation and error handling
- Production-ready deployment configuration

---
