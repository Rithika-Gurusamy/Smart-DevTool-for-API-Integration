import os
import re
import json
import importlib
from generators.rest_base import BaseRESTGenerator

try:
    genai = importlib.import_module("google.generativeai")
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

class JavaScriptRESTGenerator(BaseRESTGenerator):
    """
    Generates standalone, copy-pasteable REST integration scripts in JavaScript using the native Fetch API.
    """
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        endpoints = self.filter_endpoints(api_metadata.get("endpoints", []))
        if not endpoints:
            endpoints = api_metadata.get("endpoints", [])
            
        api_name = api_metadata.get("api_name", "API")
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        auth_desc = auth_info.get("description", "")

        # Try to generate using LLM if available
        if self.api_key and HAS_GEMINI:
            endpoints_str = "\n".join([
                f"- {ep['method']} {ep['path']} : {ep['description']} (Category: {ep.get('category', 'Primary')})" 
                for ep in endpoints
            ])
            
            prompt = f"""
You are a Principal Software Engineer. Generate standalone, production-ready REST integration examples in JavaScript using the native Fetch API.

API Name: {api_name}
Use Case: {use_case}
Authentication Method: {auth_type} ({auth_desc})

Endpoints to implement (ONLY generate standalone Fetch API request examples for these Primary/Supporting endpoints):
{endpoints_str}

Follow these strict requirements:
1. Generate a single, self-contained JavaScript script.
2. Centralized HttpClient: Include the shared `HttpClient` base class using the native `fetch` API that manages request headers (auth, Content-Type, Accept), transient retries with backoff, rate limit throttling (Retry-After), and error mappings.
3. Separation: Separate each endpoint example clearly with header comments.
4. Variables: Define parameters (e.g. BASE_URL, credentials) at the top.
5. Execution: Instantiate the client (`const client = new HttpClient(...)`) and run requests through `client.request(method, path, ...)`.
6. Error Handling: Wrap examples in try-catch blocks using the normalized exceptions: `AuthenticationError`, `ValidationError`, `RateLimitError`, `ServerError`, `NetworkError`, `TimeoutError`.

Return ONLY the raw JavaScript code. Do not include markdown code blocks or conversational text.
"""
            try:
                model = genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                code = response.text.strip()
                
                # Clean any accidental markdown wrap
                if code.startswith("```"):
                    lines = code.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    code = "\n".join(lines).strip()
                return code
            except Exception as e:
                print(f"Gemini generation in JavaScriptRESTGenerator failed ({str(e)}). Using local template.")

        # Fallback to dynamic local templates
        return self._generate_fallback(api_name, auth_type, auth_desc, endpoints)

        lines = [
            f"// Standalone JavaScript REST Integration Examples for {api_name}",
            f"// Auth Method: {auth_type} ({auth_desc})",
            "",
            "class APIClientError extends Error { constructor(message) { super(message); this.name = 'APIClientError'; } }",
            "class AuthenticationError extends APIClientError {}",
            "class ValidationError extends APIClientError {}",
            "class RateLimitError extends APIClientError {}",
            "class ServerError extends APIClientError {}",
            "class NetworkError extends APIClientError {}",
            "class TimeoutError extends APIClientError {}",
            "",
            "class HttpClient {",
            "    constructor(baseUrl, authStrategy, credentials, maxRetries = 3, enableLogging = true) {",
            "        this.baseUrl = baseUrl.replace(/\\/$/, '');",
            "        this.authStrategy = authStrategy;",
            "        this.credentials = credentials;",
            "        this.maxRetries = maxRetries;",
            "        this.enableLogging = enableLogging;",
            "    }",
            "",
            "    _log(level, msg) {",
            "        if (this.enableLogging) console.log(`[${level}] ${msg}`);",
            "    }",
            "",
            "    async request(method, path, options = {}) {",
            "        const url = `${this.baseUrl}${path}`;",
            "        let retries = 0;",
            "        let delay = 1000;",
            "        const headers = {",
            "            'Content-Type': 'application/json',",
            "            'Accept': 'application/json',",
            "            ...options.headers",
            "        };",
            "        if (this.authStrategy === 'Bearer Token') {",
            "            headers['Authorization'] = `Bearer ${this.credentials.token}`;",
            "        } else if (this.authStrategy === 'API Key') {",
            "            headers['X-API-Key'] = this.credentials.apiKey;",
            "        }",
            "        while (true) {",
            "            this._log('DEBUG', `Request: ${method} ${url}`);",
            "            try {",
            "                headers['X-Request-ID'] = `req_${Date.now()}`;",
            "                const fetchOptions = { method, headers, ...options };",
            "                const response = await fetch(url, fetchOptions);",
            "                const status = response.status;",
            "                this._log('DEBUG', `Response Status: ${status}`);",
            "                if (response.ok) {",
            "                    const text = await response.text();",
            "                    return text ? JSON.parse(text) : {};",
            "                }",
            "                if (status === 401 && this.credentials.refreshToken) {",
            "                    this._log('INFO', '401 Unauthorized. Attempting token refresh...');",
            "                    continue;",
            "                }",
            "                if (status === 429) {",
            "                    const retryAfter = response.headers.get('Retry-After');",
            "                    let sleepMs = delay;",
            "                    if (retryAfter) {",
            "                        sleepMs = isNaN(retryAfter) ? Date.parse(retryAfter) - Date.now() : parseInt(retryAfter, 10) * 1000;",
            "                        if (sleepMs < 0) sleepMs = 1000;",
            "                    }",
            "                    this._log('WARNING', `429 Rate Limit. Retrying in ${sleepMs}ms...`);",
            "                    await new Promise(resolve => setTimeout(resolve, sleepMs));",
            "                    continue;",
            "                }",
            "                if ([502, 503, 504].includes(status) && retries < this.maxRetries) {",
            "                    this._log('WARNING', `Transient error ${status}. Retrying in ${delay}ms...`);",
            "                    await new Promise(resolve => setTimeout(resolve, delay));",
            "                    retries++; delay *= 2;",
            "                    continue;",
            "                }",
            "                const errorText = await response.text();",
            "                if (status === 401 || status === 403) {",
            "                    throw new AuthenticationError(`Auth failed: ${errorText}`);",
            "                } else if (status === 429) {",
            "                    throw new RateLimitError('Rate limit exceeded.');",
            "                } else if (status >= 400 && status < 500) {",
            "                    throw new ValidationError(`Validation failed: ${errorText}`);",
            "                } else {",
            "                    throw new ServerError(`Server error: ${errorText}`);",
            "                }",
            "            } catch (error) {",
            "                if (error instanceof APIClientError) throw error;",
            "                if (retries < this.maxRetries) {",
            "                    this._log('WARNING', `Network failure. Retrying in ${delay}ms...`);",
            "                    await new Promise(resolve => setTimeout(resolve, delay));",
            "                    retries++; delay *= 2;",
            "                    continue;",
            "                }",
            "                throw new NetworkError(`Network failed: ${error.message}`);",
            "            }",
            "        }",
            "    }",
            "}",
            "",
            "// General Configuration",
            "const BASE_URL = 'https://api.example.com';",
        ]

        if auth_type == "Bearer Token":
            lines.append("const API_TOKEN = process.env.API_TOKEN || 'YOUR_BEARER_TOKEN';")
            lines.append("const client = new HttpClient(BASE_URL, 'Bearer Token', { token: API_TOKEN });")
        else:
            lines.append("const API_KEY = process.env.API_KEY || 'YOUR_API_KEY';")
            lines.append("const client = new HttpClient(BASE_URL, 'API Key', { apiKey: API_KEY });")

        lines.append("")
        lines.append("async function runExamples() {")

        for i, ep in enumerate(endpoints, 1):
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]

            lines.extend([
                "    // " + "=" * 72,
                f"    // {i}. {desc} ({method} {path})",
                "    // " + "=" * 72,
                f"    console.log('\\n--- Running Example {i}: {desc} ---');"
            ])

            # Path variables
            path_vars = re.findall(r'\{(\w+)\}', path)
            for var in path_vars:
                lines.append(f"    const {var} = 'sample_{var}';")

            js_path = path
            for var in path_vars:
                js_path = js_path.replace(f"{{{var}}}", f"${{{var}}}")

            lines.append(f"    let path_str = `${js_path}`;")

            # Execute request
            lines.append("    try {")
            if method in ["POST", "PUT", "PATCH"]:
                lines.extend([
                    "        const payload = { example_key: 'example_value' };",
                    f"        const data = await client.request('{method}', path_str, {{ body: JSON.stringify(payload) }});"
                ])
            else:
                lines.extend([
                    "        const params = { limit: '10' };",
                    f"        path_str += '?' + new URLSearchParams(params).toString();",
                    f"        const data = await client.request('{method}', path_str);"
                ])
            lines.extend([
                "        console.log('Response JSON:', JSON.stringify(data, null, 2));",
                "    } catch (error) {",
                "        console.error('Request Failed:', error.message);",
                "    }"
            ])
            lines.append("")

        lines.append("}")
        lines.append("")
        lines.append("// To execute, run in Node.js 18+")
        lines.append("// runExamples();")

        return "\n".join(lines)
