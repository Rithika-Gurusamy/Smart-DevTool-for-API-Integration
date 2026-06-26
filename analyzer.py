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

def analyze_frontend_integration(url: str, scraped_text: str, framework: str) -> dict:
    """
    Sends documentation context and framework preferences to Gemini.
    Generates a structured Frontend Integration Blueprint.
    If Gemini API isn't configured, falls back to high-quality mock models.
    """
    if not api_key or not HAS_GEMINI:
        return get_mock_frontend_analysis(url, framework)

    prompt = f"""
You are a Lead Frontend Architect. Analyze the following API documentation text and planned target frontend framework.
URL: {url}
Target Frontend Framework: {framework}
Scraped Text/Parsed Spec (may be truncated or empty if URL fetch failed/blocked):
---
{scraped_text[:30000]}
---

Step 1: Resource Grouping. Organize all endpoints into logical resource-based groups (e.g. Authentication, Users, Products, Orders).
Step 2: CRUD Pattern Detection. For each endpoint, determine the CRUD pattern it represents (Create, Read, Update, Delete, Search/List).
Step 3: Authentication Flow Analysis. Plan how the frontend will authenticate (strategy e.g. JWT, Bearer Token, API Key, Session-based), identify the login/logout/refresh endpoints, and suggest frontend storage (e.g. localStorage, HttpOnly Cookie).
Step 4: Endpoint Dependency Analysis. Map dependent sequences (e.g., login must succeed before profile call, customer must be created before checkout session).
Step 5: Service Planning. Organize client integrations into services (e.g. authService, productService). Assign endpoints to planned services. For each service domain, infer logical domains intelligently, calculate a grouping confidence score (0-100) and rationale, map its CRUD patterns, identify shared models, and outline cross-resource dependencies.
Step 6: Model Planning. Design reusable data schemas/entities (e.g. User, Product, Order) that correspond to API requests and responses. Include fields and their primitive types.
Step 7: Configuration Planning. Outline config defaults (base URL, content-type headers, timeout, etc.).
Step 8: Recommended Folder Structure. Plan an organized frontend directory layout relative to "src/" tailored for API integration (e.g. api, services, models, config, hooks, utils).

CRITICAL: If the Scraped Text is empty or limited, please use your pre-trained knowledge about the API at the URL: {url}.

You MUST return your response as a valid JSON object matching the following structure:
{{
    "api_name": "Name of the API (e.g., Stripe, Twilio, OpenAI)",
    "framework": "{framework}",
    "resource_groups": [
        {{
            "name": "Resource Group Name (e.g. Authentication)",
            "description": "Short description of this resource group's purpose",
            "endpoints": [
                {{
                    "method": "POST",
                    "path": "/login",
                    "description": "User Login"
                }}
            ]
        }}
    ],
    "crud_metadata": [
        {{
            "method": "POST",
            "path": "/login",
            "pattern": "Create (Session)"
        }}
    ],
    "authentication_plan": {{
        "strategy": "JWT | Bearer Token | API Key | Session-based | None",
        "login_endpoint": "POST /login (or empty if none)",
        "logout_endpoint": "POST /logout (or empty if none)",
        "refresh_token_endpoint": "POST /refresh_token (or empty if none)",
        "token_storage_suggestion": "localStorage | HttpOnly Cookie | Memory",
        "description": "Explain how the token or auth keys should be stored, passed, and refreshed."
    }},
    "endpoint_dependencies": [
        {{
            "pre_requisite": "POST /v1/customers",
            "dependent": "POST /v1/payment_intents",
            "reason": "Must create a customer profile to associate payment intents with billing records."
        }}
    ],
    "service_plan": [
        {{
            "service_name": "authService",
            "description": "Responsible for login, logout, and token refresh endpoints",
            "endpoints": ["POST /login", "POST /logout"],
            "confidence_score": 98,
            "explanation": "Authentication endpoints share tags, authentication requirements, and related schemas.",
            "crud_relationships": ["POST /login", "POST /logout"],
            "shared_resources": ["User"],
            "dependency_graph": []
        }}
    ],
    "model_plan": [
        {{
            "model_name": "User",
            "description": "Representation of the user account data.",
            "fields": {{
                "id": "string",
                "email": "string",
                "name": "string"
            }}
        }}
    ],
    "configuration_plan": {{
        "api_base_url": "Base URL of the API",
        "default_headers": {{
            "Content-Type": "application/json"
        }},
        "timeout_ms": 10000,
        "cors_required": true
    }},
    "folder_structure": {{
        "src": {{
            "api": {{
                "config": ["apiConfig.js"],
                "services": ["authService.js", "productService.js"],
                "models": ["types.ts"],
                "hooks": ["useAuth.js"]
            }}
        }}
    }}
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
        print(f"Gemini API frontend blueprint analysis failed ({str(e)}). Falling back to mock data.")
        return get_mock_frontend_analysis(url, framework)

def get_mock_frontend_analysis(url: str, framework: str) -> dict:
    """
    Mock data fallback for popular APIs for frontend blueprint.
    """
    clean_url = url.lower()
    
    if "stripe" in clean_url:
        return {
            "api_name": "Stripe Payments",
            "framework": framework,
            "resource_groups": [
                {
                    "name": "Customers",
                    "description": "Manage user billing profiles, address info, and payment records",
                    "endpoints": [
                        {"method": "POST", "path": "/v1/customers", "description": "Create a new customer profile"},
                        {"method": "GET", "path": "/v1/customers/{id}", "description": "Retrieve customer profile details"}
                    ]
                },
                {
                    "name": "Payments",
                    "description": "Initiate, capture, and track billing charge flows",
                    "endpoints": [
                        {"method": "POST", "path": "/v1/payment_intents", "description": "Create payment transaction session"},
                        {"method": "POST", "path": "/v1/refunds", "description": "Initiate refund for transaction"}
                    ]
                }
            ],
            "crud_metadata": [
                {"method": "POST", "path": "/v1/customers", "pattern": "Create"},
                {"method": "GET", "path": "/v1/customers/{id}", "pattern": "Read"},
                {"method": "POST", "path": "/v1/payment_intents", "pattern": "Create"},
                {"method": "POST", "path": "/v1/refunds", "pattern": "Create"}
            ],
            "authentication_plan": {
                "strategy": "Bearer Token",
                "login_endpoint": "",
                "logout_endpoint": "",
                "refresh_token_endpoint": "",
                "token_storage_suggestion": "Secure HTTP-Only Cookies / Backend Server Session",
                "description": "Frontend should not store Stripe secret keys directly. Requests should pass through a secure backend proxy, or use Stripe Elements tokenization in the client, passing tokenized cards to a backend server."
            },
            "endpoint_dependencies": [
                {
                    "pre_requisite": "POST /v1/customers",
                    "dependent": "POST /v1/payment_intents",
                    "reason": "Must construct a customer account record before associating payment intents for billing records."
                }
            ],
            "service_plan": [
                {
                    "service_name": "customerService",
                    "description": "Manages Stripe customers CRUD operations",
                    "endpoints": ["POST /v1/customers", "GET /v1/customers/{id}"],
                    "confidence_score": 95,
                    "explanation": "Customer service groups billing profile endpoints sharing Stripe tags and Customer models.",
                    "crud_relationships": ["POST /v1/customers", "GET /v1/customers/{id}"],
                    "shared_resources": ["Customer"],
                    "dependency_graph": ["POST /v1/customers -> POST /v1/payment_intents"]
                },
                {
                    "service_name": "paymentService",
                    "description": "Manages Stripe transaction sessions and intents",
                    "endpoints": ["POST /v1/payment_intents", "POST /v1/refunds"],
                    "confidence_score": 90,
                    "explanation": "Payments service collects checkout endpoints, transaction intents, and charge refunds.",
                    "crud_relationships": ["POST /v1/payment_intents", "POST /v1/refunds"],
                    "shared_resources": ["PaymentIntent"],
                    "dependency_graph": []
                }
            ],
            "model_plan": [
                {
                    "model_name": "Customer",
                    "description": "Represents a Stripe customer resource",
                    "fields": {
                        "id": "string",
                        "email": "string",
                        "name": "string",
                        "balance": "number"
                    }
                },
                {
                    "model_name": "PaymentIntent",
                    "description": "Tracks charge state lifecycle",
                    "fields": {
                        "id": "string",
                        "amount": "number",
                        "currency": "string",
                        "status": "string",
                        "customer_id": "string"
                    }
                }
            ],
            "configuration_plan": {
                "api_base_url": "https://api.stripe.com",
                "default_headers": {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                "timeout_ms": 15000,
                "cors_required": True
            },
            "folder_structure": {
                "src": {
                    "api": {
                        "config": ["apiConfig.js"],
                        "services": ["customerService.js", "paymentService.js"],
                        "models": ["types.ts"],
                        "hooks": ["usePayments.js"]
                    }
                }
            }
        }
    elif "twilio" in clean_url:
        return {
            "api_name": "Twilio Messages",
            "framework": framework,
            "resource_groups": [
                {
                    "name": "SMS Dispatch",
                    "description": "Outbound message deliveries and tracking logs",
                    "endpoints": [
                        {"method": "POST", "path": "/2010-04-01/Accounts/{AccountSid}/Messages.json", "description": "Dispatch outbound text message"},
                        {"method": "GET", "path": "/2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json", "description": "Query specific message dispatch logs"}
                    ]
                }
            ],
            "crud_metadata": [
                {"method": "POST", "path": "/2010-04-01/Accounts/{AccountSid}/Messages.json", "pattern": "Create"},
                {"method": "GET", "path": "/2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json", "pattern": "Read"}
            ],
            "authentication_plan": {
                "strategy": "Basic Auth",
                "login_endpoint": "",
                "logout_endpoint": "",
                "refresh_token_endpoint": "",
                "token_storage_suggestion": "Secure Server Environment Variables",
                "description": "Auth credentials (Account SID & Auth Token) are basic-auth encoded. Do not include in frontend code to prevent credentials hijacking."
            },
            "endpoint_dependencies": [
                {
                    "pre_requisite": "POST /2010-04-01/Accounts/{AccountSid}/Messages.json",
                    "dependent": "GET /2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json",
                    "reason": "Must dispatch a message first before retrieving its delivery logs."
                }
            ],
            "service_plan": [
                {
                    "service_name": "messageService",
                    "description": "Manages twilio SMS dispatches",
                    "endpoints": [
                        "POST /2010-04-01/Accounts/{AccountSid}/Messages.json",
                        "GET /2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json"
                    ],
                    "confidence_score": 98,
                    "explanation": "Twilio messaging endpoints share SMS dispatch path patterns and Message schema.",
                    "crud_relationships": ["POST /2010-04-01/Accounts/{AccountSid}/Messages.json", "GET /2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json"],
                    "shared_resources": ["Message"],
                    "dependency_graph": ["POST /2010-04-01/Accounts/{AccountSid}/Messages.json -> GET /2010-04-01/Accounts/{AccountSid}/Messages/{Sid}.json"]
                }
            ],
            "model_plan": [
                {
                    "model_name": "Message",
                    "description": "Represents an outbound twilio message",
                    "fields": {
                        "sid": "string",
                        "to": "string",
                        "from": "string",
                        "body": "string",
                        "status": "string"
                    }
                }
            ],
            "configuration_plan": {
                "api_base_url": "https://api.twilio.com",
                "default_headers": {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                "timeout_ms": 10000,
                "cors_required": True
            },
            "folder_structure": {
                "src": {
                    "api": {
                        "config": ["apiConfig.js"],
                        "services": ["messageService.js"],
                        "models": ["types.ts"]
                    }
                }
            }
        }
    else:
        # Default Blueprint Mock
        return {
            "api_name": "Generic REST API",
            "framework": framework,
            "resource_groups": [
                {
                    "name": "Resources",
                    "description": "CRUD management endpoints",
                    "endpoints": [
                        {"method": "GET", "path": "/api/v1/resources", "description": "Query matching database list"},
                        {"method": "POST", "path": "/api/v1/resources", "description": "Insert a new item record"}
                    ]
                }
            ],
            "crud_metadata": [
                {"method": "GET", "path": "/api/v1/resources", "pattern": "Search/List"},
                {"method": "POST", "path": "/api/v1/resources", "pattern": "Create"}
            ],
            "authentication_plan": {
                "strategy": "API Key",
                "login_endpoint": "",
                "logout_endpoint": "",
                "refresh_token_endpoint": "",
                "token_storage_suggestion": "localStorage / Context State",
                "description": "Supplied inside custom headers: 'X-API-Key: <TOKEN>'."
            },
            "endpoint_dependencies": [],
            "service_plan": [
                {
                    "service_name": "resourceService",
                    "description": "Handles resource model CRUD requests",
                    "endpoints": ["GET /api/v1/resources", "POST /api/v1/resources"],
                    "confidence_score": 85,
                    "explanation": "Resource service manages basic CRUD patterns on the core Resource entity.",
                    "crud_relationships": ["GET /api/v1/resources", "POST /api/v1/resources"],
                    "shared_resources": ["Resource"],
                    "dependency_graph": []
                }
            ],
            "model_plan": [
                {
                    "model_name": "Resource",
                    "description": "Generic api data schema",
                    "fields": {
                        "id": "string",
                        "name": "string",
                        "createdAt": "string"
                    }
                }
            ],
            "configuration_plan": {
                "api_base_url": "https://api.example.com",
                "default_headers": {
                    "Content-Type": "application/json"
                },
                "timeout_ms": 10000,
                "cors_required": True
            },
            "folder_structure": {
                "src": {
                    "api": {
                        "config": ["apiConfig.js"],
                        "services": ["resourceService.js"],
                        "models": ["types.ts"]
                    }
                }
            }
        }
