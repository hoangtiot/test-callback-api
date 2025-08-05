"""
IRAS Callback API Server - Flask Implementation
===============================================
Flask server for handling various IRAS callback endpoints.
Optimized for  App Hosting source upload deployment.

Endpoints:
- /iras/gst-return/callback - GST Return submissions (F5, F8)
- /iras/form-cs/callback - Corporate Secretary forms
- /iras/commission-records/callback - Commission record submissions
- /iras/donation-records/callback - Donation record submissions
- /iras/e-stamping/callback - E-stamping submissions

Author: Generated for IRAS Integration Testing
"""

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
import json
import logging
from datetime import datetime
import os
import traceback
import uuid
from typing import Dict, List, Any, Optional
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for testing (configure domains for production)
CORS(app, origins=["*"])

# App configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=True
)

# In-memory storage for testing (resets on restart)
callback_logs: List[Dict[str, Any]] = []
MAX_LOGS = 200  # Prevent memory issues

# ================================
# Data Validation Classes
# ================================

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)

class CallbackValidator:
    """Validator class for IRAS callback data"""
    
    @staticmethod
    def validate_required_fields(data: dict, required_fields: list) -> None:
        """Validate that all required fields are present"""
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
    
    @staticmethod
    def validate_submission_status(status: str) -> str:
        """Validate and normalize submission status"""
        if not status:
            raise ValidationError("submissionStatus is required")
        
        allowed_statuses = ['SUCCESS', 'FAILED', 'PROCESSING', 'PENDING', 'REJECTED', 'CANCELLED']
        status_upper = status.upper()
        
        if status_upper not in allowed_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {', '.join(allowed_statuses)}")
        
        return status_upper
    
    @staticmethod
    def validate_uen(uen: str) -> str:
        """Validate Singapore UEN format"""
        if not uen:
            raise ValidationError("companyUEN is required")
        
        # UEN format: 8 digits + letter OR 9 digits + letter
        uen_pattern = r'^\d{8}[A-Z]$|^\d{9}[A-Z]$'
        if not re.match(uen_pattern, uen):
            raise ValidationError("Invalid UEN format. Expected format: 12345678A or 123456789A")
        
        return uen
    
    @staticmethod
    def validate_form_type(form_type: str) -> str:
        """Validate GST form type"""
        if not form_type:
            raise ValidationError("formType is required")
        
        form_type_upper = form_type.upper()
        if form_type_upper not in ['F5', 'F8']:
            raise ValidationError("Invalid formType. Must be F5 or F8")
        
        return form_type_upper
    
    @staticmethod
    def validate_tax_period(tax_period: str) -> str:
        """Validate tax period format (YYYYMM)"""
        if not tax_period:
            raise ValidationError("taxPeriod is required")
        
        if not re.match(r'^\d{6}$', tax_period):
            raise ValidationError("Invalid taxPeriod format. Expected format: YYYYMM (e.g., 202412)")
        
        # Basic date validation
        try:
            year = int(tax_period[:4])
            month = int(tax_period[4:])
            if year < 2000 or year > 2100:
                raise ValidationError("Invalid year in taxPeriod")
            if month < 1 or month > 12:
                raise ValidationError("Invalid month in taxPeriod")
        except ValueError:
            raise ValidationError("Invalid taxPeriod format")
        
        return tax_period

# ================================
# Utility Functions
# ================================

def get_client_ip() -> str:
    """Get client IP address with proxy support"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'

def log_callback(endpoint: str, callback_data: Dict[str, Any]) -> str:
    """
    Log callback data and return a unique request ID
    
    Args:
        endpoint: The callback endpoint called
        callback_data: The callback payload
        
    Returns:
        str: Unique request ID for tracking
    """
    request_id = str(uuid.uuid4())[:8]  # Short unique ID
    client_ip = get_client_ip()
    
    log_entry = {
        "requestId": request_id,
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "callback_data": callback_data,
        "headers": dict(request.headers),
        "client_ip": client_ip,
        "method": request.method,
        "status": callback_data.get('submissionStatus', 'UNKNOWN')
    }
    
    # Add to logs and maintain size limit
    callback_logs.append(log_entry)
    if len(callback_logs) > MAX_LOGS:
        callback_logs.pop(0)  # Remove oldest log
    
    # Log to console for monitoring
    logger.info(f"📨 {endpoint} callback received - Request ID: {request_id}")
    logger.info(f"   Submission ID: {callback_data.get('submissionId', 'N/A')}")
    logger.info(f"   Status: {callback_data.get('submissionStatus', 'N/A')}")
    logger.info(f"   Company UEN: {callback_data.get('companyUEN', 'N/A')}")
    logger.info(f"   Client IP: {client_ip}")
    
    return request_id

def create_success_response(message: str, submission_id: str, request_id: str) -> dict:
    """Create a successful callback response"""
    return {
        "status": "received",
        "message": message,
        "submissionId": submission_id,
        "timestamp": datetime.now().isoformat(),
        "requestId": request_id
    }

def create_error_response(error: Exception, submission_id: str = None, status_code: int = 500) -> tuple:
    """
    Create error response with proper logging
    
    Args:
        error: The exception that occurred
        submission_id: Optional submission ID for tracking
        status_code: HTTP status code
        
    Returns:
        tuple: (response_dict, status_code)
    """
    error_id = str(uuid.uuid4())[:8]
    error_detail = str(error)
    
    logger.error(f"❌ Callback processing error - Error ID: {error_id}")
    logger.error(f"   Error: {error_detail}")
    logger.error(f"   Submission ID: {submission_id or 'N/A'}")
    logger.error(f"   Endpoint: {request.endpoint}")
    logger.error(f"   Method: {request.method}")
    logger.error(f"   Client IP: {get_client_ip()}")
    if status_code >= 500:  # Only log traceback for server errors
        logger.error(f"   Traceback: {traceback.format_exc()}")
    
    response = {
        "status": "error",
        "message": "Error processing callback" if status_code >= 500 else error_detail,
        "error_id": error_id,
        "submissionId": submission_id,
        "timestamp": datetime.now().isoformat()
    }
    
    # Include error details for validation errors
    if isinstance(error, ValidationError):
        response["error_detail"] = error_detail
        if hasattr(error, 'field') and error.field:
            response["field"] = error.field
    
    return response, status_code

def validate_json_payload() -> dict:
    """Validate and return JSON payload from request"""
    if not request.is_json:
        raise ValidationError("Content-Type must be application/json")
    
    try:
        data = request.get_json()
        if data is None:
            raise ValidationError("Request body must contain valid JSON")
        return data
    except Exception as e:
        raise ValidationError(f"Invalid JSON payload: {str(e)}")

# ================================
# Health and Info Endpoints
# ================================

@app.route("/", methods=["GET"])
def root():
    """Root endpoint with API information"""
    return jsonify({
        "message": "IRAS Callback API Server",
        "status": "healthy",
        "platform": " App Hosting + Flask",
        "version": "1.0.0",
        "framework": "Flask",
        "endpoints": {
            "gst_return": "/iras/gst-return/callback",
            "form_cs": "/iras/form-cs/callback",
            "commission_records": "/iras/commission-records/callback",
            "donation_records": "/iras/donation-records/callback",
            "e_stamping": "/iras/e-stamping/callback",
            "health": "/health",
            "logs": "/logs"
        },
        "documentation": "Visit /docs for endpoint documentation"
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        current_time = datetime.now().isoformat()
        log_count = len(callback_logs)
        
        return jsonify({
            "status": "healthy",
            "timestamp": current_time,
            "platform": " App Hosting + Flask",
            "logs_count": log_count,
            "memory_usage": "normal" if log_count < MAX_LOGS * 0.8 else "high",
            "python_version": os.sys.version,
            "flask_version": "2.3.3"
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        response, status_code = create_error_response(e, status_code=503)
        return jsonify(response), status_code

@app.route("/docs", methods=["GET"])
def api_documentation():
    """API documentation endpoint"""
    docs = {
        "title": "IRAS Callback API Documentation",
        "version": "1.0.0",
        "description": "Comprehensive callback API for IRAS services",
        "endpoints": [
            {
                "path": "/iras/gst-return/callback",
                "method": "POST",
                "description": "GST Return submission callback (F5, F8)",
                "required_fields": [
                    "submissionId", "submissionStatus", "formType", 
                    "submissionDateTime", "companyUEN", "taxPeriod"
                ],
                "optional_fields": [
                    "acknowledgementNumber", "totalTaxAmount", "errors"
                ]
            },
            {
                "path": "/iras/form-cs/callback",
                "method": "POST",
                "description": "Corporate Secretary form submission callback",
                "required_fields": [
                    "submissionId", "submissionStatus", "submissionDateTime", 
                    "companyUEN", "formVersion", "filingType"
                ],
                "optional_fields": [
                    "effectiveDate", "acknowledgementNumber", "errors"
                ]
            },
            {
                "path": "/iras/commission-records/callback",
                "method": "POST",
                "description": "Commission records submission callback",
                "required_fields": [
                    "submissionId", "submissionStatus", "submissionDateTime", 
                    "companyUEN", "recordType", "recordPeriod"
                ],
                "optional_fields": [
                    "totalRecords", "totalCommissionAmount", "acknowledgementNumber", "errors"
                ]
            },
            {
                "path": "/iras/donation-records/callback",
                "method": "POST",
                "description": "Donation records submission callback",
                "required_fields": [
                    "submissionId", "submissionStatus", "submissionDateTime", 
                    "companyUEN", "donationType", "donationPeriod"
                ],
                "optional_fields": [
                    "totalDonations", "totalDonationAmount", "acknowledgementNumber", "errors"
                ]
            },
            {
                "path": "/iras/e-stamping/callback",
                "method": "POST",
                "description": "E-stamping submission callback",
                "required_fields": [
                    "submissionId", "submissionStatus", "submissionDateTime", 
                    "companyUEN", "documentType"
                ],
                "optional_fields": [
                    "stampDuty", "stampCertificateNumber", "acknowledgementNumber", "errors"
                ]
            }
        ],
        "example_payload": {
            "submissionId": "GST202501001234",
            "submissionStatus": "SUCCESS",
            "submissionDateTime": "2025-01-15T14:30:00+08:00",
            "companyUEN": "201234567D",
            "formType": "F5",
            "taxPeriod": "202412",
            "acknowledgementNumber": "ACK123456789",
            "totalTaxAmount": 15000.50
        }
    }
    
    return jsonify(docs)

# ================================
# IRAS Callback Endpoints
# ================================

@app.route("/iras/gst-return/callback", methods=["POST"])
def gst_return_callback():
    """
    GST Return submission callback endpoint (F5, F8)
    
    This endpoint receives callbacks from IRAS after GST return processing.
    Handles both successful and failed submissions with proper validation.
    """
    submission_id = None
    try:
        # Validate and extract JSON payload
        data = validate_json_payload()
        
        # Validate required fields
        required_fields = [
            'submissionId', 'submissionStatus', 'formType', 
            'submissionDateTime', 'companyUEN', 'taxPeriod'
        ]
        CallbackValidator.validate_required_fields(data, required_fields)
        
        # Extract and validate individual fields
        submission_id = data['submissionId']
        submission_status = CallbackValidator.validate_submission_status(data['submissionStatus'])
        form_type = CallbackValidator.validate_form_type(data['formType'])
        company_uen = CallbackValidator.validate_uen(data['companyUEN'])
        tax_period = CallbackValidator.validate_tax_period(data['taxPeriod'])
        
        # Optional fields with validation
        ack_number = data.get('acknowledgementNumber')
        total_tax = data.get('totalTaxAmount')
        errors = data.get('errors', [])
        
        if total_tax is not None:
            try:
                total_tax = float(total_tax)
                if total_tax < 0:
                    raise ValidationError("totalTaxAmount must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("totalTaxAmount must be a valid number")
        
        # Create normalized callback data
        callback_data = {
            'submissionId': submission_id,
            'submissionStatus': submission_status,
            'formType': form_type,
            'submissionDateTime': data['submissionDateTime'],
            'companyUEN': company_uen,
            'taxPeriod': tax_period,
            'acknowledgementNumber': ack_number,
            'totalTaxAmount': total_tax,
            'errors': errors
        }
        
        # Log the callback
        request_id = log_callback("GST-RETURN", callback_data)
        
        # Process based on status
        if submission_status == "SUCCESS":
            logger.info(f"✅ GST {form_type} submission successful!")
            if ack_number:
                logger.info(f"   ACK Number: {ack_number}")
            if total_tax:
                logger.info(f"   Total Tax: ${total_tax:,.2f}")
            message = f"GST {form_type} submission for period {tax_period} processed successfully"
            
        elif submission_status == "FAILED":
            logger.warning(f"❌ GST {form_type} submission failed")
            if errors:
                logger.warning(f"   Errors: {', '.join(errors)}")
            message = f"GST {form_type} submission for period {tax_period} failed"
            
        else:  # PROCESSING, PENDING, etc.
            logger.info(f"⏳ GST {form_type} submission status: {submission_status}")
            message = f"GST {form_type} submission for period {tax_period} is {submission_status.lower()}"
        
        response = create_success_response(message, submission_id, request_id)
        return jsonify(response), 200
        
    except ValidationError as e:
        response, status_code = create_error_response(e, submission_id, 400)
        return jsonify(response), status_code
    except Exception as e:
        response, status_code = create_error_response(e, submission_id, 500)
        return jsonify(response), status_code

@app.route("/iras/form-cs/callback", methods=["POST"])
def form_cs_callback():
    """
    Corporate Secretary form submission callback endpoint
    
    Handles callbacks for corporate secretary filings and changes.
    """
    submission_id = None
    try:
        data = validate_json_payload()
        
        required_fields = [
            'submissionId', 'submissionStatus', 'submissionDateTime', 
            'companyUEN', 'formVersion', 'filingType'
        ]
        CallbackValidator.validate_required_fields(data, required_fields)
        
        submission_id = data['submissionId']
        submission_status = CallbackValidator.validate_submission_status(data['submissionStatus'])
        company_uen = CallbackValidator.validate_uen(data['companyUEN'])
        
        callback_data = {
            'submissionId': submission_id,
            'submissionStatus': submission_status,
            'submissionDateTime': data['submissionDateTime'],
            'companyUEN': company_uen,
            'formVersion': data['formVersion'],
            'filingType': data['filingType'],
            'effectiveDate': data.get('effectiveDate'),
            'acknowledgementNumber': data.get('acknowledgementNumber'),
            'errors': data.get('errors', [])
        }
        
        request_id = log_callback("FORM-CS", callback_data)
        
        if submission_status == "SUCCESS":
            logger.info(f"✅ Form CS submission successful!")
            logger.info(f"   Filing Type: {data['filingType']}")
            if data.get('effectiveDate'):
                logger.info(f"   Effective Date: {data['effectiveDate']}")
            message = f"Form CS ({data['filingType']}) submission processed successfully"
            
        elif submission_status == "FAILED":
            logger.warning(f"❌ Form CS submission failed")
            if data.get('errors'):
                logger.warning(f"   Errors: {', '.join(data['errors'])}")
            message = f"Form CS ({data['filingType']}) submission failed"
            
        else:
            logger.info(f"⏳ Form CS submission status: {submission_status}")
            message = f"Form CS ({data['filingType']}) submission is {submission_status.lower()}"
        
        response = create_success_response(message, submission_id, request_id)
        return jsonify(response), 200
        
    except ValidationError as e:
        response, status_code = create_error_response(e, submission_id, 400)
        return jsonify(response), status_code
    except Exception as e:
        response, status_code = create_error_response(e, submission_id, 500)
        return jsonify(response), status_code

@app.route("/iras/commission-records/callback", methods=["POST"])
def commission_records_callback():
    """
    Commission records submission callback endpoint
    
    Handles callbacks for commission record submissions.
    """
    submission_id = None
    try:
        data = validate_json_payload()
        
        required_fields = [
            'submissionId', 'submissionStatus', 'submissionDateTime', 
            'companyUEN', 'recordType', 'recordPeriod'
        ]
        CallbackValidator.validate_required_fields(data, required_fields)
        
        submission_id = data['submissionId']
        submission_status = CallbackValidator.validate_submission_status(data['submissionStatus'])
        company_uen = CallbackValidator.validate_uen(data['companyUEN'])
        
        # Validate optional numeric fields
        total_records = data.get('totalRecords')
        total_commission = data.get('totalCommissionAmount')
        
        if total_records is not None:
            try:
                total_records = int(total_records)
                if total_records < 0:
                    raise ValidationError("totalRecords must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("totalRecords must be a valid integer")
        
        if total_commission is not None:
            try:
                total_commission = float(total_commission)
                if total_commission < 0:
                    raise ValidationError("totalCommissionAmount must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("totalCommissionAmount must be a valid number")
        
        callback_data = {
            'submissionId': submission_id,
            'submissionStatus': submission_status,
            'submissionDateTime': data['submissionDateTime'],
            'companyUEN': company_uen,
            'recordType': data['recordType'],
            'recordPeriod': data['recordPeriod'],
            'totalRecords': total_records,
            'totalCommissionAmount': total_commission,
            'acknowledgementNumber': data.get('acknowledgementNumber'),
            'errors': data.get('errors', [])
        }
        
        request_id = log_callback("COMMISSION-RECORDS", callback_data)
        
        if submission_status == "SUCCESS":
            logger.info(f"✅ Commission records submission successful!")
            logger.info(f"   Record Type: {data['recordType']}")
            logger.info(f"   Period: {data['recordPeriod']}")
            if total_records:
                logger.info(f"   Total Records: {total_records}")
            if total_commission:
                logger.info(f"   Total Commission: ${total_commission:,.2f}")
            message = f"Commission records ({data['recordType']}) for {data['recordPeriod']} processed successfully"
            
        elif submission_status == "FAILED":
            logger.warning(f"❌ Commission records submission failed")
            if data.get('errors'):
                logger.warning(f"   Errors: {', '.join(data['errors'])}")
            message = f"Commission records ({data['recordType']}) submission failed"
            
        else:
            logger.info(f"⏳ Commission records submission status: {submission_status}")
            message = f"Commission records ({data['recordType']}) submission is {submission_status.lower()}"
        
        response = create_success_response(message, submission_id, request_id)
        return jsonify(response), 200
        
    except ValidationError as e:
        response, status_code = create_error_response(e, submission_id, 400)
        return jsonify(response), status_code
    except Exception as e:
        response, status_code = create_error_response(e, submission_id, 500)
        return jsonify(response), status_code

@app.route("/iras/donation-records/callback", methods=["POST"])
def donation_records_callback():
    """
    Donation records submission callback endpoint
    
    Handles callbacks for donation record submissions.
    """
    submission_id = None
    try:
        data = validate_json_payload()
        
        required_fields = [
            'submissionId', 'submissionStatus', 'submissionDateTime', 
            'companyUEN', 'donationType', 'donationPeriod'
        ]
        CallbackValidator.validate_required_fields(data, required_fields)
        
        submission_id = data['submissionId']
        submission_status = CallbackValidator.validate_submission_status(data['submissionStatus'])
        company_uen = CallbackValidator.validate_uen(data['companyUEN'])
        
        # Validate optional numeric fields
        total_donations = data.get('totalDonations')
        total_amount = data.get('totalDonationAmount')
        
        if total_donations is not None:
            try:
                total_donations = int(total_donations)
                if total_donations < 0:
                    raise ValidationError("totalDonations must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("totalDonations must be a valid integer")
        
        if total_amount is not None:
            try:
                total_amount = float(total_amount)
                if total_amount < 0:
                    raise ValidationError("totalDonationAmount must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("totalDonationAmount must be a valid number")
        
        callback_data = {
            'submissionId': submission_id,
            'submissionStatus': submission_status,
            'submissionDateTime': data['submissionDateTime'],
            'companyUEN': company_uen,
            'donationType': data['donationType'],
            'donationPeriod': data['donationPeriod'],
            'totalDonations': total_donations,
            'totalDonationAmount': total_amount,
            'acknowledgementNumber': data.get('acknowledgementNumber'),
            'errors': data.get('errors', [])
        }
        
        request_id = log_callback("DONATION-RECORDS", callback_data)
        
        if submission_status == "SUCCESS":
            logger.info(f"✅ Donation records submission successful!")
            logger.info(f"   Donation Type: {data['donationType']}")
            logger.info(f"   Period: {data['donationPeriod']}")
            if total_donations:
                logger.info(f"   Total Donations: {total_donations}")
            if total_amount:
                logger.info(f"   Total Amount: ${total_amount:,.2f}")
            message = f"Donation records ({data['donationType']}) for {data['donationPeriod']} processed successfully"
            
        elif submission_status == "FAILED":
            logger.warning(f"❌ Donation records submission failed")
            if data.get('errors'):
                logger.warning(f"   Errors: {', '.join(data['errors'])}")
            message = f"Donation records ({data['donationType']}) submission failed"
            
        else:
            logger.info(f"⏳ Donation records submission status: {submission_status}")
            message = f"Donation records ({data['donationType']}) submission is {submission_status.lower()}"
        
        response = create_success_response(message, submission_id, request_id)
        return jsonify(response), 200
        
    except ValidationError as e:
        response, status_code = create_error_response(e, submission_id, 400)
        return jsonify(response), status_code
    except Exception as e:
        response, status_code = create_error_response(e, submission_id, 500)
        return jsonify(response), status_code

@app.route("/iras/e-stamping/callback", methods=["POST"])
def e_stamping_callback():
    """
    E-stamping submission callback endpoint
    
    Handles callbacks for e-stamping submissions.
    """
    submission_id = None
    try:
        data = validate_json_payload()
        
        required_fields = [
            'submissionId', 'submissionStatus', 'submissionDateTime', 
            'companyUEN', 'documentType'
        ]
        CallbackValidator.validate_required_fields(data, required_fields)
        
        submission_id = data['submissionId']
        submission_status = CallbackValidator.validate_submission_status(data['submissionStatus'])
        company_uen = CallbackValidator.validate_uen(data['companyUEN'])
        
        # Validate optional stamp duty field
        stamp_duty = data.get('stampDuty')
        if stamp_duty is not None:
            try:
                stamp_duty = float(stamp_duty)
                if stamp_duty < 0:
                    raise ValidationError("stampDuty must be non-negative")
            except (ValueError, TypeError):
                raise ValidationError("stampDuty must be a valid number")
        
        callback_data = {
            'submissionId': submission_id,
            'submissionStatus': submission_status,
            'submissionDateTime': data['submissionDateTime'],
            'companyUEN': company_uen,
            'documentType': data['documentType'],
            'stampDuty': stamp_duty,
            'stampCertificateNumber': data.get('stampCertificateNumber'),
            'acknowledgementNumber': data.get('acknowledgementNumber'),
            'errors': data.get('errors', [])
        }
        
        request_id = log_callback("E-STAMPING", callback_data)
        
        if submission_status == "SUCCESS":
            logger.info(f"✅ E-stamping submission successful!")
            logger.info(f"   Document Type: {data['documentType']}")
            if stamp_duty:
                logger.info(f"   Stamp Duty: ${stamp_duty:,.2f}")
            if data.get('stampCertificateNumber'):
                logger.info(f"   Certificate Number: {data['stampCertificateNumber']}")
            message = f"E-stamping for {data['documentType']} processed successfully"
            
        elif submission_status == "FAILED":
            logger.warning(f"❌ E-stamping submission failed")
            if data.get('errors'):
                logger.warning(f"   Errors: {', '.join(data['errors'])}")
            message = f"E-stamping for {data['documentType']} submission failed"
            
        else:
            logger.info(f"⏳ E-stamping submission status: {submission_status}")
            message = f"E-stamping for {data['documentType']} submission is {submission_status.lower()}"
        
        response = create_success_response(message, submission_id, request_id)
        return jsonify(response), 200
        
    except ValidationError as e:
        response, status_code = create_error_response(e, submission_id, 400)
        return jsonify(response), status_code
    except Exception as e:
        response, status_code = create_error_response(e, submission_id, 500)
        return jsonify(response), status_code

# ================================
# Testing and Monitoring Endpoints
# ================================

@app.route("/logs", methods=["GET"])
def get_callback_logs():
    """
    Get recent callback logs for testing and monitoring
    
    Query parameters:
        limit: Number of recent logs to return (max 50, default 10)
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)  # Prevent excessive data transfer
        recent_logs = callback_logs[-limit:] if callback_logs else []
        
        return jsonify({
            "total_callbacks": len(callback_logs),
            "returned_logs": len(recent_logs),
            "logs": recent_logs
        })
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

@app.route("/logs/stats", methods=["GET"])
def get_callback_stats():
    """Get callback statistics and summary"""
    try:
        if not callback_logs:
            return jsonify({"message": "No callbacks received yet"})
        
        # Calculate statistics
        status_counts = {}
        endpoint_counts = {}
        recent_activity = []
        
        for log in callback_logs:
            # Count by status
            status = log.get('status', 'UNKNOWN')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count by endpoint
            endpoint = log.get('endpoint', 'UNKNOWN')
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
        
        # Get recent activity (last 10 callbacks)
        for log in callback_logs[-10:]:
            recent_activity.append({
                "timestamp": log.get('timestamp'),
                "endpoint": log.get('endpoint'),
                "status": log.get('status'),
                "submissionId": log.get('callback_data', {}).get('submissionId', 'N/A')
            })
        
        return jsonify({
            "total_callbacks": len(callback_logs),
            "status_breakdown": status_counts,
            "endpoint_breakdown": endpoint_counts,
            "latest_callback": callback_logs[-1]['timestamp'] if callback_logs else None,
            "recent_activity": recent_activity
        })
    except Exception as e:
        logger.error(f"Error calculating stats: {str(e)}")
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

@app.route("/logs", methods=["DELETE"])
def clear_logs():
    """Clear all callback logs (for testing)"""
    try:
        global callback_logs
        logs_cleared = len(callback_logs)
        callback_logs.clear()
        
        logger.info(f"🧹 Cleared {logs_cleared} callback logs")
        
        return jsonify({
            "message": f"Cleared {logs_cleared} callback logs",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

# ================================
# Mock Testing Endpoints
# ================================

@app.route("/test/mock-gst-callback", methods=["POST"])
def test_mock_gst_callback():
    """Generate and process a mock GST callback for testing"""
    try:
        # Create mock GST callback data
        mock_data = {
            "submissionId": f"GST{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "submissionStatus": "SUCCESS",
            "formType": "F5",
            "submissionDateTime": datetime.now().isoformat(),
            "companyUEN": "201234567D",
            "taxPeriod": "202412",
            "acknowledgementNumber": f"ACK{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "totalTaxAmount": 15000.50,
            "errors": []
        }
        
        # Process the mock callback internally
        with app.test_request_context('/test/mock-gst-callback', 
                                    method='POST', 
                                    json=mock_data,
                                    headers={'Content-Type': 'application/json'}):
            request_id = log_callback("GST-RETURN-TEST", mock_data)
        
        response = create_success_response(
            "Mock GST F5 submission for period 202412 processed successfully",
            mock_data["submissionId"],
            request_id
        )
        
        return jsonify({
            "message": "Mock GST callback generated and processed successfully",
            "mock_data": mock_data,
            "callback_response": response
        })
    except Exception as e:
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

@app.route("/test/mock-form-cs-callback", methods=["POST"])
def test_mock_form_cs_callback():
    """Generate and process a mock Form CS callback for testing"""
    try:
        mock_data = {
            "submissionId": f"CS{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "submissionStatus": "SUCCESS",
            "submissionDateTime": datetime.now().isoformat(),
            "companyUEN": "201234567D",
            "formVersion": "2025.1",
            "filingType": "ANNUAL_RETURN",
            "effectiveDate": "2025-01-01",
            "acknowledgementNumber": f"ACK{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "errors": []
        }
        
        with app.test_request_context('/test/mock-form-cs-callback', 
                                    method='POST', 
                                    json=mock_data,
                                    headers={'Content-Type': 'application/json'}):
            request_id = log_callback("FORM-CS-TEST", mock_data)
        
        response = create_success_response(
            "Form CS (ANNUAL_RETURN) submission processed successfully",
            mock_data["submissionId"],
            request_id
        )
        
        return jsonify({
            "message": "Mock Form CS callback generated and processed successfully",
            "mock_data": mock_data,
            "callback_response": response
        })
    except Exception as e:
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

@app.route("/test/validate-callback", methods=["POST"])
def test_validate_callback():
    """Test callback validation with provided data"""
    try:
        data = validate_json_payload()
        
        # Get callback type from query parameter
        callback_type = request.args.get('type', 'gst-return')
        
        if callback_type == 'gst-return':
            required_fields = [
                'submissionId', 'submissionStatus', 'formType', 
                'submissionDateTime', 'companyUEN', 'taxPeriod'
            ]
            CallbackValidator.validate_required_fields(data, required_fields)
            CallbackValidator.validate_submission_status(data['submissionStatus'])
            CallbackValidator.validate_form_type(data['formType'])
            CallbackValidator.validate_uen(data['companyUEN'])
            CallbackValidator.validate_tax_period(data['taxPeriod'])
            
        elif callback_type in ['form-cs', 'commission-records', 'donation-records', 'e-stamping']:
            base_required = ['submissionId', 'submissionStatus', 'submissionDateTime', 'companyUEN']
            CallbackValidator.validate_required_fields(data, base_required)
            CallbackValidator.validate_submission_status(data['submissionStatus'])
            CallbackValidator.validate_uen(data['companyUEN'])
        
        return jsonify({
            "status": "valid",
            "message": f"Callback data validation passed for {callback_type}",
            "validated_data": data,
            "timestamp": datetime.now().isoformat()
        })
        
    except ValidationError as e:
        return jsonify({
            "status": "invalid",
            "message": "Validation failed",
            "error": str(e),
            "field": getattr(e, 'field', None),
            "timestamp": datetime.now().isoformat()
        }), 400
    except Exception as e:
        response, status_code = create_error_response(e, status_code=500)
        return jsonify(response), status_code

# ================================
# Error Handlers
# ================================

@app.errorhandler(404)
def not_found_handler(error):
    """Handle 404 errors with helpful message"""
    logger.warning(f"404 error: {request.url} not found")
    return jsonify({
        "status": "error",
        "message": "Endpoint not found",
        "requested_url": request.url,
        "available_endpoints": [
            "/iras/gst-return/callback",
            "/iras/form-cs/callback", 
            "/iras/commission-records/callback",
            "/iras/donation-records/callback",
            "/iras/e-stamping/callback",
            "/health",
            "/docs",
            "/logs"
        ],
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(405)
def method_not_allowed_handler(error):
    """Handle 405 errors (method not allowed)"""
    logger.warning(f"405 error: Method {request.method} not allowed for {request.url}")
    return jsonify({
        "status": "error",
        "message": f"Method {request.method} not allowed for this endpoint",
        "allowed_methods": ["GET", "POST"] if "callback" in request.url else ["GET"],
        "timestamp": datetime.now().isoformat()
    }), 405

@app.errorhandler(400)
def bad_request_handler(error):
    """Handle 400 errors (bad request)"""
    logger.warning(f"400 error: Bad request for {request.url}")
    return jsonify({
        "status": "error",
        "message": "Bad request - please check your request format",
        "timestamp": datetime.now().isoformat()
    }), 400

@app.errorhandler(500)
def internal_error_handler(error):
    """Handle 500 errors (internal server error)"""
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"500 error - Error ID: {error_id}")
    logger.error(f"   URL: {request.url}")
    logger.error(f"   Method: {request.method}")
    logger.error(f"   Error: {str(error)}")
    logger.error(f"   Traceback: {traceback.format_exc()}")
    
    return jsonify({
        "status": "error",
        "message": "Internal server error",
        "error_id": error_id,
        "timestamp": datetime.now().isoformat()
    }), 500

# ================================
# Application Startup/Shutdown
# ================================

@app.before_request
def startup_event():
    """Application startup event"""
    logger.info("🚀 IRAS Callback API Server starting up...")
    logger.info(f"   Platform:  App Hosting + Flask")
    logger.info(f"   Endpoints: 5 callback endpoints + monitoring")
    logger.info(f"   Documentation available at: /docs")
    logger.info(f"   Health check available at: /health")

def shutdown_event():
    """Application shutdown event (called manually if needed)"""
    logger.info("📴 IRAS Callback API Server shutting down...")
    logger.info(f"   Total callbacks processed: {len(callback_logs)}")

# ================================
# Production WSGI Entry Point
# ================================

# For production deployment with gunicorn
application = app

# ================================
# Development Server
# ================================

if __name__ == "__main__":
    # Development server (not used in production)
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    
    logger.info(f"🔥 Starting IRAS Callback API on port {port}")
    logger.info(f"   Debug mode: {debug_mode}")
    logger.info(f"   Environment: {os.environ.get('FLASK_ENV', 'production')}")
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode,
        use_reloader=debug_mode
    )