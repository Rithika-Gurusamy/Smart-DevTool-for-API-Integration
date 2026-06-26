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

class PythonRESTGenerator(BaseRESTGenerator):
    """
    Generates standalone, copy-pasteable REST integration scripts in Python using `requests`.
    """
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        # Filter endpoints: only keep Primary and Supporting
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
You are a Principal Software Engineer. Generate standalone, production-ready REST integration examples in Python using the `requests` library.

API Name: {api_name}
Use Case: {use_case}
Authentication Method: {auth_type} ({auth_desc})

Endpoints to implement (ONLY generate standalone HTTP request examples for these Primary/Supporting endpoints):
{endpoints_str}

Follow these strict requirements:
1. Generate a single, self-contained Python script.
2. Centralized HTTPClient: Include the shared `HTTPClient` base class that manages request headers (auth strategy, Content-Type, Accept), transient retries with backoff, rate limit throttling, and error mappings.
3. Separation: Separate each endpoint example clearly with header comments.
4. Variables: Define parameters (e.g. BASE_URL, credentials) at the top.
5. Execution: Instantiate the client (`client = HTTPClient(...)`) and run requests through `client._request(method, path, ...)`.
6. Error Handling: Wrap examples in try-except blocks using the normalized exceptions: `AuthenticationError`, `ValidationError`, `RateLimitError`, `ServerError`, `NetworkError`, `TimeoutError`.

Return ONLY the raw Python code. Do not include markdown code blocks or conversational text.
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
                print(f"Gemini generation in PythonRESTGenerator failed ({str(e)}). Using local template.")

        # Fallback to dynamic local templates
        return self._generate_fallback(api_name, auth_type, auth_desc, endpoints)

    def _generate_fallback(self, api_name: str, auth_type: str, auth_desc: str, endpoints: list) -> str:
        """
        Dynamically builds a high-fidelity REST integration script when LLM is unavailable.
        """
        lines = [
            f"# Standalone Python REST Integration Examples for {api_name}",
            f"# Auth Method: {auth_type} ({auth_desc})",
            "import os",
            "import time",
            "import requests",
            "import json",
            "from typing import Any, Dict, List, Optional, Union",
            "",
            "class APIClientError(Exception): pass",
            "class AuthenticationError(APIClientError): pass",
            "class ValidationError(APIClientError): pass",
            "class RateLimitError(APIClientError): pass",
            "class ServerError(APIClientError): pass",
            "class NetworkError(APIClientError): pass",
            "class TimeoutError(APIClientError): pass",
            "",
            "class HTTPClient:",
            "    def __init__(self, base_url: str, auth_strategy: str, credentials: Dict[str, Any], max_retries: int = 3, backoff_factor: float = 2.0, enable_logging: bool = True):",
            "        self.base_url = base_url.rstrip('/')",
            "        self.auth_strategy = auth_strategy",
            "        self.credentials = credentials",
            "        self.max_retries = max_retries",
            "        self.backoff_factor = backoff_factor",
            "        self.enable_logging = enable_logging",
            "        self.session = requests.Session()",
            "        self.session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})",
            "        self._apply_auth()",
            "",
            "    def _apply_auth(self):",
            "        if self.auth_strategy == 'Bearer Token':",
            "            self.session.headers['Authorization'] = f\"Bearer {self.credentials.get('token')}\"",
            "        elif self.auth_strategy == 'API Key':",
            "            self.session.headers['X-API-Key'] = self.credentials.get('api_key')",
            "        elif self.auth_strategy == 'Basic Auth':",
            "            self.session.auth = (self.credentials.get('username'), self.credentials.get('password', ''))",
            "",
            "    def _log(self, level: str, msg: str):",
            "        if self.enable_logging:",
            "            print(f'[{level}] {msg}')",
            "",
            "    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:",
            "        url = f'{self.base_url}{path}'",
            "        retries = 0",
            "        delay = 1.0",
            "        while True:",
            "            self._log('DEBUG', f'Request: {method} {url} | Params: {params} | Data: {data}')",
            "            try:",
            "                self.session.headers['X-Request-ID'] = f'req_{int(time.time() * 1000)}'",
            "                response = self.session.request(method, url, params=params, json=data, timeout=10)",
            "                status = response.status_code",
            "                self._log('DEBUG', f'Response Status: {status}')",
            "                if 200 <= status < 300:",
            "                    return response.json() if response.text.strip() else {}",
            "                if status == 401 and 'refresh_token' in self.credentials:",
            "                    self._log('INFO', '401 Unauthorized. Refreshing token...')",
            "                    if self._refresh_token():",
            "                        self._apply_auth()",
            "                        continue",
            "                if status == 429:",
            "                    retry_after = response.headers.get('Retry-After')",
            "                    if retry_after:",
            "                        try:",
            "                            sleep_seconds = float(retry_after)",
            "                        except ValueError:",
            "                            sleep_seconds = delay",
            "                        self._log('WARNING', f'429 Rate Limited. Retrying after {sleep_seconds}s...')",
            "                        time.sleep(sleep_seconds)",
            "                        continue",
            "                if status in [502, 503, 504] and retries < self.max_retries:",
            "                    self._log('WARNING', f'Transient error {status}. Retrying in {delay}s...')",
            "                    time.sleep(delay)",
            "                    retries += 1",
            "                    delay *= self.backoff_factor",
            "                    continue",
            "                if status in [401, 403]:",
            "                    raise AuthenticationError(f'Authentication failed: {response.text}')",
            "                elif status == 429:",
            "                    raise RateLimitError('Rate limit exceeded.')",
            "                elif 400 <= status < 500:",
            "                    raise ValidationError(f'Validation failed: {response.text}')",
            "                else:",
            "                    raise ServerError(f'Server error: {response.text}')",
            "            except requests.Timeout as e:",
            "                if retries < self.max_retries:",
            "                    time.sleep(delay)",
            "                    retries += 1",
            "                    delay *= self.backoff_factor",
            "                    continue",
            "                raise TimeoutError(f'Request timed out: {str(e)}')",
            "            except requests.RequestException as e:",
            "                if retries < self.max_retries:",
            "                    time.sleep(delay)",
            "                    retries += 1",
            "                    delay *= self.backoff_factor",
            "                    continue",
            "                raise NetworkError(f'Network error: {str(e)}')",
            "",
            "    def _refresh_token(self) -> bool:",
            "        return True",
            "",
            "# General Configuration",
            "BASE_URL = 'https://api.example.com'",
        ]

        if auth_type == "Bearer Token":
            lines.append("API_TOKEN = os.getenv('API_TOKEN', 'YOUR_BEARER_TOKEN')")
            lines.append("credentials = {'token': API_TOKEN}")
            lines.append(f"client = HTTPClient(BASE_URL, 'Bearer Token', credentials)")
        elif auth_type == "Basic Auth":
            lines.append("USERNAME = os.getenv('API_USERNAME', 'YOUR_USERNAME')")
            lines.append("PASSWORD = os.getenv('API_PASSWORD', 'YOUR_PASSWORD')")
            lines.append("credentials = {'username': USERNAME, 'password': PASSWORD}")
            lines.append(f"client = HTTPClient(BASE_URL, 'Basic Auth', credentials)")
        else:
            lines.append("API_KEY = os.getenv('API_KEY', 'YOUR_API_KEY')")
            lines.append("credentials = {'api_key': API_KEY}")
            lines.append(f"client = HTTPClient(BASE_URL, 'API Key', credentials)")

        lines.append("")

        for i, ep in enumerate(endpoints, 1):
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]
            
            lines.extend([
                f"# {'=' * 76}",
                f"# {i}. {desc} ({method} {path})",
                f"# {'=' * 76}",
                f"print('\\n--- Running Example {i}: {desc} ---')"
            ])

            # Path parameters setup
            path_vars = re.findall(r'\{(\w+)\}', path)
            for var in path_vars:
                lines.append(f"{var} = 'sample_{var}'")

            # URL building
            if path_vars:
                formatted_path = path
                for var in path_vars:
                    formatted_path = formatted_path.replace(f"{{{var}}}", f"{{{var}}}")
                lines.append(f"path_str = f'{formatted_path}'")
            else:
                lines.append(f"path_str = '{path}'")

            # Payload or Query Parameters
            lines.append("try:")
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("    payload = {")
                lines.append("        'example_key': 'example_value'")
                lines.append("    }")
                lines.append(f"    response = client._request('{method}', path_str, data=payload)")
            else:
                lines.append("    params = {")
                lines.append("        'limit': 10")
                lines.append("    }")
                lines.append(f"    response = client._request('{method}', path_str, params=params)")

            lines.extend([
                "    print('Response JSON:', json.dumps(response, indent=2))",
                "except APIClientError as e:",
                "    print('Request Failed:', str(e))",
                ""
            ])

        return "\n".join(lines)
