import os
import json
import re
import importlib
from dotenv import load_dotenv
try:
    genai = importlib.import_module("google.generativeai")
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

# Load env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Configure Gemini if key exists
if api_key and HAS_GEMINI:
    genai.configure(api_key=api_key)

def analyze_api_docs(url: str, scraped_text: str, use_case: str, language: str) -> dict:
    """
    Sends documentation context and use case requirements to Gemini.
    If Gemini API isn't configured, falls back to high-quality mock models for key APIs.
    """
    if not api_key or not HAS_GEMINI:
        # Fallback to high-quality mock data for demo purposes if API key is missing or library is unavailable
        return get_mock_analysis(url, use_case, language)
        
    prompt = f"""
You are an expert API Architect. Analyze the following API documentation text and user use case.
URL: {url}
Use Case: {use_case}
Target Language: {language}
Scraped Text (may be truncated or empty if URL fetch failed/blocked):
---
{scraped_text[:30000]}
---

Analyze the API details and match it to the use case.
CRITICAL: If the Scraped Text is empty or limited, please use your pre-trained knowledge about the API at the URL: {url}.
For example, if the URL is about Stripe (stripe.com), you know its authentication method (Bearer Token), its SDK recommendation (stripe), and the core endpoints like POST /v1/payments, GET /v1/customers, etc. Use this internal knowledge to complete the analysis.

You MUST return your response as a valid JSON object matching the following structure:
{{
    "api_name": "Name of the API (e.g., Stripe, Twilio, OpenAI)",
    "auth_method": {{
        "type": "Bearer Token | API Key | OAuth 2.0 | Basic Auth | None",
        "description": "Short explanation of how to pass the authentication header or token."
    }},
    "sdk_recommendation": {{
        "name": "Package name to install (e.g., 'stripe', 'twilio', 'openai')",
        "install_command": "Command to install (e.g., 'pip install stripe' or 'npm install stripe')"
    }},
    "endpoints": [
        {{
            "method": "GET | POST | PUT | DELETE | PATCH",
            "path": "/path/to/endpoint",
            "description": "Short description of what it does",
            "relevance": "Why this endpoint is relevant to the user's use case"
        }}
    ]
}}
Return ONLY the raw JSON object. Do not add any conversational text, markdown formatting, or HTML tags. Just raw JSON.
"""

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean any accidental markdown wrap
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        analysis = json.loads(text)
        return analysis
    except Exception as e:
        # If parsing or network fails, fallback gracefully to mock
        print(f"Gemini API analysis failed ({str(e)}). Falling back to mock data.")
        return get_mock_analysis(url, use_case, language)

def get_mock_analysis(url: str, use_case: str, language: str) -> dict:
    """
    Mock data fallback for popular APIs.
    """
    clean_url = url.lower()
    clean_lang = language.lower()
    
    if "stripe" in clean_url:
        return {
            "api_name": "Stripe Payments API",
            "auth_method": {
                "type": "Bearer Token",
                "description": "Passed as an 'Authorization: Bearer <API_KEY>' HTTP header using your Secret Key."
            },
            "sdk_recommendation": {
                "name": "stripe",
                "install_command": "pip install stripe" if clean_lang == "python" else "npm install stripe"
            },
            "endpoints": [
                {"method": "POST", "path": "/v1/payment_intents", "description": "Create a PaymentIntent to start a checkout session", "relevance": "Core endpoint required to initiate a secure transaction session."},
                {"method": "POST", "path": "/v1/charges", "description": "Create a direct credit card charge", "relevance": "Alternative endpoint for simple card billing workflows."},
                {"method": "POST", "path": "/v1/customers", "description": "Create a customer record", "relevance": "Saves customer billing information for subsequent charges."},
                {"method": "POST", "path": "/v1/refunds", "description": "Refund an existing transaction", "relevance": "Essential endpoint to return money back to customers."}
            ]
        }
    elif "twilio" in clean_url:
        return {
            "api_name": "Twilio Communication API",
            "auth_method": {
                "type": "Basic Auth",
                "description": "Uses your Account SID as the username and your Auth Token as the password."
            },
            "sdk_recommendation": {
                "name": "twilio",
                "install_command": "pip install twilio" if clean_lang == "python" else "npm install twilio"
            },
            "endpoints": [
                {"method": "POST", "path": "/2010-04-01/Accounts/{AccountSid}/Messages.json", "description": "Send an SMS message resource", "relevance": "Primary endpoint for sending outbound texts and messages."},
                {"method": "GET", "path": "/2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json", "description": "Retrieve SMS log status", "relevance": "Used to track if the SMS delivery was successful or failed."}
            ]
        }
    elif "openai" in clean_url:
        return {
            "api_name": "OpenAI Inference API",
            "auth_method": {
                "type": "Bearer Token",
                "description": "Passed as an 'Authorization: Bearer <API_KEY>' HTTP header."
            },
            "sdk_recommendation": {
                "name": "openai",
                "install_command": "pip install openai" if clean_lang == "python" else "npm install openai"
            },
            "endpoints": [
                {"method": "POST", "path": "/v1/chat/completions", "description": "Generate text completions based on prompt messages", "relevance": "Core endpoint to run standard LLM inference and query responses."},
                {"method": "POST", "path": "/v1/embeddings", "description": "Generate vector representations of text inputs", "relevance": "Required to perform semantic search or build a RAG database application."}
            ]
        }
    else:
        # Generic API Mock
        return {
            "api_name": "Custom REST API Engine",
            "auth_method": {
                "type": "API Key",
                "description": "Typically provided inside custom headers: 'X-API-Key: <TOKEN>'."
            },
            "sdk_recommendation": {
                "name": "requests" if clean_lang == "python" else "axios",
                "install_command": "pip install requests" if clean_lang == "python" else "npm install axios"
            },
            "endpoints": [
                {"method": "GET", "path": "/api/v1/resources", "description": "Query matching resources database list", "relevance": "Checks database items matching the use-case query request."},
                {"method": "POST", "path": "/api/v1/resources", "description": "Insert a new item record", "relevance": "Stores data entries requested by your custom application logic."}
            ]
        }
