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

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if api_key and HAS_GEMINI:
    genai.configure(api_key=api_key)

def generate_wrapper(api_metadata: dict, language: str, use_case: str, stack_name: str = None) -> str:
    """
    Generates a complete client wrapper class for the target language and stack.
    """
    from generators import get_stack_generator
    
    if not stack_name:
        lang_lower = language.lower()
        if "python" in lang_lower:
            stack_name = "Generic Python"
        elif "javascript" in lang_lower or "typescript" in lang_lower:
            stack_name = "Vanilla JavaScript"
        elif "java" in lang_lower:
            stack_name = "Generic Java"
        elif "c#" in lang_lower or "csharp" in lang_lower:
            stack_name = "Generic .NET"
        else:
            stack_name = "Generic Python"
            
    stack_gen = get_stack_generator(stack_name, api_key=api_key)
    return stack_gen.generate_sdk(api_metadata, use_case)

def generate_rest_integration(api_metadata: dict, language: str, use_case: str, stack_name: str = None) -> str:
    """
    Generates standalone REST integration code for the target language and stack.
    """
    from generators import get_stack_generator
    
    if not stack_name:
        lang_lower = language.lower()
        if "python" in lang_lower:
            stack_name = "Generic Python"
        elif "javascript" in lang_lower or "typescript" in lang_lower:
            stack_name = "Vanilla JavaScript"
        elif "java" in lang_lower:
            stack_name = "Generic Java"
        elif "c#" in lang_lower or "csharp" in lang_lower:
            stack_name = "Generic .NET"
        else:
            stack_name = "Generic Python"
            
    stack_gen = get_stack_generator(stack_name, api_key=api_key)
    return stack_gen.generate_rest(api_metadata, use_case)


def generate_postman_collection(api_metadata: dict) -> str:
    """
    Generates a standard Postman Collection (v2.1.0 JSON format).
    """
    api_name = api_metadata.get("api_name", "API")
    endpoints = api_metadata.get("endpoints", [])
    auth_info = api_metadata.get("auth_method", {})
    
    items = []
    for ep in endpoints:
        path = ep["path"]
        method = ep["method"]
        desc = ep["description"]
        
        # Parse path variables / split paths
        clean_path = path.strip("/")
        path_segments = clean_path.split("/")
        
        # Base url mock
        host = ["api", "example", "com"]
        protocol = "https"
        
        headers = []
        if auth_info.get("type") == "Bearer Token":
            headers.append({
                "key": "Authorization",
                "value": "Bearer {{api_key}}",
                "type": "text"
            })
        elif auth_info.get("type") == "Basic Auth":
            headers.append({
                "key": "Authorization",
                "value": "Basic {{base64_encoded_credentials}}",
                "type": "text"
            })
        elif auth_info.get("type") == "API Key":
            headers.append({
                "key": "X-API-Key",
                "value": "{{api_key}}",
                "type": "text"
            })
            
        headers.append({
            "key": "Content-Type",
            "value": "application/json",
            "type": "text"
        })
        
        item = {
            "name": desc or f"{method} {path}",
            "request": {
                "method": method,
                "header": headers,
                "url": {
                    "raw": f"https://api.example.com{path}",
                    "protocol": protocol,
                    "host": host,
                    "path": path_segments
                },
                "description": desc
            },
            "response": []
        }
        items.append(item)
        
    collection = {
        "info": {
            "name": f"{api_name} Integration Collection",
            "description": f"Postman collection generated dynamically for {api_name} integration.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": items
    }
    
    return json.dumps(collection, indent=2)

def generate_sequence_diagram(api_metadata: dict, language: str) -> str:
    """
    Generates Mermaid sequence diagram markup.
    """
    api_name = api_metadata.get("api_name", "API")
    endpoints = api_metadata.get("endpoints", [])
    
    lines = [
        "sequenceDiagram",
        "    autonumber",
        "    actor Developer",
        "    participant App as App Logic",
        f"    participant Client as {api_name}Client ({language})",
        f"    participant Gateway as {api_name} Gateway",
        ""
    ]
    
    for idx, ep in enumerate(endpoints, 1):
        method = ep["method"]
        path = ep["path"]
        desc = ep["description"]
        
        # Clean description for Mermaid safety
        desc_clean = re.sub(r'[^a-zA-Z0-9\s_\-\/]', '', desc)
        if len(desc_clean) > 40:
            desc_clean = desc_clean[:37] + "..."
            
        lines.append(f"    Note over App, Client: Step {idx}: {desc_clean}")
        lines.append(f"    Developer->>App: Initiates flow")
        lines.append(f"    App->>Client: Request Wrapper Method")
        lines.append(f"    Note over Client: Append auth header")
        lines.append(f"    Client->>Gateway: {method} {path}")
        lines.append(f"    Gateway-->>Client: 200 OK (JSON Payload)")
        lines.append(f"    Client-->>App: Parse and return model")
        lines.append(f"    App-->>Developer: Success state UI / callback")
        lines.append("")
        
    return "\n".join(lines)

def get_mock_wrapper(api_name: str, auth_info: dict, endpoints: list, language: str) -> str:
    """
    Local mock wrapper template substitution for offline/fallback usage.
    """
    lang = language.lower()
    auth_type = auth_info.get("type", "Bearer Token")
    
    if lang == "python":
        code_lines = [
            f"# Python API Client Wrapper for {api_name}",
            "import requests",
            "import os",
            "",
            f"class {api_name}Client:",
            f"    def __init__(self, api_key: str = None, base_url: str = 'https://api.example.com'):",
            "        self.api_key = api_key or os.getenv('API_KEY')",
            "        self.base_url = base_url",
            "        if not self.api_key:",
            "            raise ValueError('An API key must be provided.')",
            "        self.session = requests.Session()",
        ]
        
        # Configure headers
        if auth_type == "Bearer Token":
            code_lines.append("        self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})")
        elif auth_type == "API Key":
            code_lines.append("        self.session.headers.update({'X-API-Key': self.api_key})")
        elif auth_type == "Basic Auth":
            code_lines.append("        # Basic Auth is handled per request or by session.auth")
            code_lines.append("        # self.session.auth = (self.api_key, '')")
            
        code_lines.append("        self.session.headers.update({'Content-Type': 'application/json'})")
        code_lines.append("")
        
        for ep in endpoints:
            method = ep["method"].lower()
            path = ep["path"]
            desc = ep["description"]
            # Generate python method name
            method_name = path.strip("/").replace("/", "_").replace("-", "_").replace("{", "").replace("}", "")
            method_name = re.sub(r'v\d+_', '', method_name) # Strip api version
            if not method_name:
                method_name = "request"
            method_name = f"{method}_{method_name}"
            
            # Format method parameters
            params = "self, data: dict = None"
            if "{" in path:
                var_match = re.findall(r'\{(\w+)\}', path)
                if var_match:
                    params = "self, " + ", ".join([f"{v}: str" for v in var_match]) + ", data: dict = None"
                    
            code_lines.extend([
                f"    def {method_name}({params}):",
                f"        \"\"\"",
                f"        {desc}",
                f"        \"\"\"",
            ])
            
            # Request URL builder
            if "{" in path:
                url_build = f"url = f'{{self.base_url}}{path.replace('{', '{')}'"
            else:
                url_build = f"url = f'{{self.base_url}}{path}'"
                
            code_lines.extend([
                f"        {url_build}",
                f"        response = self.session.{method}(url, json=data)" if method in ['post', 'put', 'patch'] else f"        response = self.session.{method}(url, params=data)",
                "        response.raise_for_status()",
                "        return response.json()",
                ""
            ])
            
        return "\n".join(code_lines)
        
    elif lang in ["javascript", "typescript"]:
        code_lines = [
            f"// JavaScript API Client Wrapper for {api_name}",
            "// Requires 'axios' npm library",
            "const axios = require('axios');",
            "",
            f"class {api_name}Client {{",
            "    constructor(apiKey, baseUrl = 'https://api.example.com') {",
            "        this.apiKey = apiKey || process.env.API_KEY;",
            "        this.baseUrl = baseUrl;",
            "        if (!this.apiKey) {",
            "            throw new Error('An API key must be provided.');",
            "        }",
            "        this.client = axios.create({",
            "            baseURL: this.baseUrl,",
            "            headers: {",
            "                'Content-Type': 'application/json',",
        ]
        
        if auth_type == "Bearer Token":
            code_lines.append("                'Authorization': `Bearer ${this.apiKey}`")
        elif auth_type == "API Key":
            code_lines.append("                'X-API-Key': this.apiKey")
            
        code_lines.extend([
            "            }",
            "        });",
            "    }",
            ""
        ])
        
        for ep in endpoints:
            method = ep["method"].lower()
            path = ep["path"]
            desc = ep["description"]
            
            method_name = path.strip("/").replace("/", "_").replace("-", "_").replace("{", "").replace("}", "")
            method_name = re.sub(r'v\d+_\b', '', method_name)
            if not method_name:
                method_name = "request"
            method_name = f"{method}{method_name.title().replace('_', '')}"
            
            params = "data = {}"
            if "{" in path:
                var_match = re.findall(r'\{(\w+)\}', path)
                if var_match:
                    params = ", ".join(var_match) + ", data = {}"
                    
            code_lines.extend([
                f"    /**",
                f"     * {desc}",
                f"     */",
                f"    async {method_name}({params}) {{",
            ])
            
            if "{" in path:
                url_build = f"const url = `{path.replace('{', '${')}`;"
            else:
                url_build = f"const url = '{path}';"
                
            code_lines.extend([
                f"        {url_build}",
                f"        const response = await this.client.{method}(url, data);",
                "        return response.data;",
                "    }",
                ""
            ])
            
        code_lines.append("}")
        code_lines.append(f"module.exports = {api_name}Client;")
        return "\n".join(code_lines)
        
    else:
        # Default Go-like or simple language wrapper fallback
        return f"// {language} SDK Wrapper for {api_name} is under construction.\n// Auth: {auth_type}\n// Supported endpoints:\n" + "\n".join([f"// {ep['method']} {ep['path']}" for ep in endpoints])
