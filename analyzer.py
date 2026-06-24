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
You are an expert API Architect and Relevance Scoring Engine. Analyze the following API documentation text and user use case.
URL: {url}
Use Case: {use_case}
Target Language: {language}
Scraped Text/Parsed Spec (may be truncated or empty if URL fetch failed/blocked):
---
{scraped_text[:30000]}
---

Step 1: Extract key concepts and intents from the use case. Understand what the user's workflow needs to accomplish.
Step 2: Analyze each endpoint in the specification against the use case intent.
Step 3: Generate a relevance score (0-100) for every endpoint based on keyword overlap, semantic similarity, tag relevance, operation purpose, and dependency relationships.
Step 4: Categorize endpoints into: "Primary" (directly required), "Supporting" (frequently needed alongside), "Optional" (useful but not required), or "Irrelevant" (unrelated).
Step 5: Provide a short "reasoning" for the classification.
Step 6: Identify any workflow dependency relationships (e.g., you need to create a Customer before a Checkout Session).

CRITICAL: If the Scraped Text is empty or limited, please use your pre-trained knowledge about the API at the URL: {url}.

You MUST return your response as a valid JSON object matching the following structure:
{{
    "api_name": "Name of the API (e.g., Stripe, Twilio, OpenAI)",
    "auth_method": {{
        "type": "Bearer Token | API Key | OAuth 2.0 | Basic Auth | None",
        "description": "Short explanation of how to pass the authentication header or token."
    }},
    "sdk_recommendation": {{
        "name": "Package name to install (e.g., 'stripe', 'twilio', 'openai')",
        "install_command": "Command to install"
    }},
    "endpoints": [
        {{
            "method": "GET | POST | PUT | DELETE | PATCH",
            "path": "/path/to/endpoint",
            "description": "Short description of what it does",
            "relevance_score": 95,
            "category": "Primary | Supporting | Optional | Irrelevant",
            "reasoning": "This endpoint directly creates payment checkout sessions and is essential...",
            "dependencies": ["POST /customers", "GET /products"]
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
                {
                    "method": "POST", "path": "/v1/payment_intents", "description": "Create a PaymentIntent to start a checkout session", 
                    "relevance_score": 98, "category": "Primary", "reasoning": "Core endpoint required to initiate a secure transaction session.", "dependencies": ["POST /v1/customers"]
                },
                {
                    "method": "POST", "path": "/v1/customers", "description": "Create a customer record", 
                    "relevance_score": 85, "category": "Supporting", "reasoning": "Saves customer billing information for subsequent charges.", "dependencies": []
                },
                {
                    "method": "POST", "path": "/v1/refunds", "description": "Refund an existing transaction", 
                    "relevance_score": 40, "category": "Optional", "reasoning": "Useful for reversing charges but not strictly required for the happy path checkout.", "dependencies": ["POST /v1/payment_intents"]
                },
                {
                    "method": "POST", "path": "/v1/charges", "description": "Create a direct credit card charge", 
                    "relevance_score": 20, "category": "Irrelevant", "reasoning": "Legacy endpoint superseded by Payment Intents for checkout flows.", "dependencies": []
                }
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
                {
                    "method": "POST", "path": "/2010-04-01/Accounts/{AccountSid}/Messages.json", "description": "Send an SMS message resource", 
                    "relevance_score": 100, "category": "Primary", "reasoning": "Primary endpoint for sending outbound texts and messages.", "dependencies": []
                },
                {
                    "method": "GET", "path": "/2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json", "description": "Retrieve SMS log status", 
                    "relevance_score": 75, "category": "Supporting", "reasoning": "Used to track if the SMS delivery was successful or failed.", "dependencies": ["POST /2010-04-01/Accounts/{AccountSid}/Messages.json"]
                }
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
                {
                    "method": "POST", "path": "/v1/chat/completions", "description": "Generate text completions based on prompt messages", 
                    "relevance_score": 100, "category": "Primary", "reasoning": "Core endpoint to run standard LLM inference and query responses.", "dependencies": []
                },
                {
                    "method": "POST", "path": "/v1/embeddings", "description": "Generate vector representations of text inputs", 
                    "relevance_score": 40, "category": "Optional", "reasoning": "Required to perform semantic search or build a RAG database application, but maybe optional depending on context.", "dependencies": []
                }
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
                {
                    "method": "GET", "path": "/api/v1/resources", "description": "Query matching resources database list", 
                    "relevance_score": 80, "category": "Primary", "reasoning": "Checks database items matching the use-case query request.", "dependencies": []
                },
                {
                    "method": "POST", "path": "/api/v1/resources", "description": "Insert a new item record", 
                    "relevance_score": 90, "category": "Primary", "reasoning": "Stores data entries requested by your custom application logic.", "dependencies": []
                }
            ]
        }
