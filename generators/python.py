import os
import re
import json
import importlib
from generators.base import BaseSDKGenerator

try:
    genai = importlib.import_module("google.generativeai")
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

class PythonSDKGenerator(BaseSDKGenerator):
    """
    Python SDK Generator.
    Produces highly robust, production-ready, type-hinted Python clients using `requests`.
    """
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)

    def generate(self, api_metadata: dict, use_case: str) -> str:
        # 1. Filter endpoints: only keep Primary and Supporting
        endpoints = self.filter_endpoints(api_metadata.get("endpoints", []))
        # Fallback if no primary/supporting are found (e.g. mock analyzer issues)
        if not endpoints:
            endpoints = api_metadata.get("endpoints", [])
            
        api_name = api_metadata.get("api_name", "API")
        class_name = self.clean_class_name(api_name)
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        auth_desc = auth_info.get("description", "")

        # Try to generate using LLM if possible
        if self.api_key and HAS_GEMINI:
            endpoints_str = "\n".join([
                f"- {ep['method']} {ep['path']} : {ep['description']} (Category: {ep.get('category', 'Primary')})" 
                for ep in endpoints
            ])
            
            prompt = f"""
You are a Principal Software Engineer. Generate a production-ready, clean, and highly robust Python client SDK wrapper class.

API Name: {api_name}
Client Class Name: {class_name}
Use Case: {use_case}
Authentication: {auth_type} ({auth_desc})

Endpoints to implement in the wrapper (ONLY generate methods for these):
{endpoints_str}

Follow these strict requirements:
1. Imports: Use the `requests` library and standard library modules only. Include typing imports (`Dict`, `Any`, `Optional`, `List`, `Union`).
2. Exceptions:
   - Generate a base custom exception `APIClientError(Exception)`.
   - Subclass it into:
     * `AuthenticationError(APIClientError)`
     * `ValidationError(APIClientError)`
     * `RateLimitError(APIClientError)`
     * `ServerError(APIClientError)`
3. Client Class:
   - Name: `{class_name}`
   - Constructor (`__init__`):
     * Expose auth params matching '{auth_type}' (e.g. `api_key: Optional[str] = None` or `token: Optional[str] = None`).
     * Expose `base_url: str` with a default value.
     * Validate auth presence; raise `AuthenticationError` if missing.
     * Initialize a `requests.Session()` object.
     * Automatically apply authentication headers/credentials to the session so that all subsequent requests automatically carry authentication. E.g.
       - Bearer Token: session.headers['Authorization'] = f'Bearer {{token}}'
       - API Key: session.headers['X-API-Key'] = api_key (or standard headers)
       - Basic Auth: session.auth = (api_key, '')
       - OAuth2: scaffold header setup.
4. Request Helper method:
   - Implement a private `_request(self, method: str, path: str, ...)` method that handles:
     * Full URL building.
     * Executing requests via the session.
     * Raising specific custom exceptions based on HTTP status code (401/403 -> AuthenticationError, 429 -> RateLimitError, 400/422 -> ValidationError, 5xx -> ServerError, otherwise general APIClientError).
     * Parsing and returning the JSON response as a dictionary.
5. Endpoint Methods:
   - Create clear, type-hinted methods for each endpoint.
   - Method names must be derived cleanly (e.g., `POST /customers` -> `create_customer`, `GET /customers/{{id}}` -> `get_customer`).
   - Extract and expose path parameters (e.g., `id: str` or `customer_id: str`) directly as required arguments in the method signature.
   - Accept payload/body parameters (`data: Optional[Dict[str, Any]] = None` or individual arguments) and query parameters.
   - Construct path dynamically by replacing `{{param_name}}` with the parameter value.
   - Provide a comprehensive Google-style docstring for every method containing:
     * Brief summary / Purpose.
     * Args (names, types, description).
     * Returns (type, description).
     * Raises (exceptions).
     * Code example showing how to call the method using an instance of the class.
6. Runnable Usage Example Block:
   - Add a `if __name__ == "__main__":` block at the bottom of the file showing complete example code:
     * Instantiating the client (using an environment variable or dummy key).
     * Invoking the implemented methods with sample payloads.
     * Handling exceptions gracefully with `try/except APIClientError as e:`.

Return ONLY the raw Python code. Do not wrap it in markdown code blocks or add any conversational text.
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
                print(f"Gemini generation in PythonSDKGenerator failed ({str(e)}). Using local template.")
                
        # Fallback to local template matching all 13 requirements
        return self._generate_fallback(class_name, auth_type, auth_desc, endpoints)

    def _generate_fallback(self, class_name: str, auth_type: str, auth_desc: str, endpoints: list) -> str:
        """
        Creates a high-quality production-ready Python SDK fallback class when LLM fails or is missing.
        """
        lines = [
            f'# Python SDK Client for {class_name}',
            '# Generated dynamically from API specification endpoints',
            'import os',
            'import requests',
            'from typing import Any, Dict, List, Optional, Union',
            '',
            'class APIClientError(Exception):',
            '    """Base exception for all SDK wrapper requests."""',
            '    pass',
            '',
            'class AuthenticationError(APIClientError):',
            '    """Raised on 401/403 errors."""',
            '    pass',
            '',
            'class ValidationError(APIClientError):',
            '    """Raised on 400/422 client validation failures."""',
            '    pass',
            '',
            'class RateLimitError(APIClientError):',
            '    """Raised on 429 rate limit exceeded responses."""',
            '    pass',
            '',
            'class ServerError(APIClientError):',
            '    """Raised on 5xx server issues."""',
            '    pass',
            '',
            f'class {class_name}:',
            '    """',
            f'    API Client Wrapper for {class_name}.',
            '    """',
        ]

        # Init method
        if auth_type == "Bearer Token":
            init_signature = "    def __init__(self, token: Optional[str] = None, base_url: str = 'https://api.example.com'):"
            init_body = [
                "        self.token = token or os.getenv('API_TOKEN')",
                "        if not self.token:",
                "            raise AuthenticationError('Authentication token must be provided.')",
                "        self.base_url = base_url.rstrip('/')",
                "        self.session = requests.Session()",
                "        self.session.headers.update({",
                "            'Authorization': f'Bearer {self.token}',",
                "            'Content-Type': 'application/json'",
                "        })"
            ]
        elif auth_type == "Basic Auth":
            init_signature = "    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, base_url: str = 'https://api.example.com'):"
            init_body = [
                "        self.username = username or os.getenv('API_USERNAME')",
                "        self.password = password or os.getenv('API_PASSWORD')",
                "        if not self.username:",
                "            raise AuthenticationError('Basic auth username must be provided.')",
                "        self.base_url = base_url.rstrip('/')",
                "        self.session = requests.Session()",
                "        self.session.auth = (self.username, self.password or '')",
                "        self.session.headers.update({",
                "            'Content-Type': 'application/json'",
                "        })"
            ]
        else: # API Key / None
            init_signature = "    def __init__(self, api_key: Optional[str] = None, base_url: str = 'https://api.example.com'):"
            init_body = [
                "        self.api_key = api_key or os.getenv('API_KEY')",
                "        if not self.api_key:",
                "            raise AuthenticationError('API Key must be provided.')",
                "        self.base_url = base_url.rstrip('/')",
                "        self.session = requests.Session()",
                "        self.session.headers.update({",
                "            'X-API-Key': self.api_key,",
                "            'Content-Type': 'application/json'",
                "        })"
            ]

        lines.append(init_signature)
        lines.extend(init_body)
        lines.append("")

        # Private _request helper
        request_helper = [
            "    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:",
            "        url = f'{self.base_url}{path}'",
            "        try:",
            "            response = self.session.request(method, url, params=params, json=data)",
            "            status_code = response.status_code",
            "            if status_code in [401, 403]:",
            "                raise AuthenticationError(f'Authentication failed: {response.text}')",
            "            elif status_code == 429:",
            "                raise RateLimitError('Rate limit exceeded.')",
            "            elif 400 <= status_code < 500:",
            "                raise ValidationError(f'Validation/Client error: {response.text}')",
            "            elif status_code >= 500:",
            "                raise ServerError(f'Internal server error: {response.text}')",
            "            ",
            "            if response.text.strip():",
            "                return response.json()",
            "            return {}",
            "        except requests.RequestException as e:",
            "            raise APIClientError(f'Network connection failed: {str(e)}')",
            ""
        ]
        lines.extend(request_helper)

        # Endpoint Methods
        for ep in endpoints:
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]
            
            method_name = self.clean_method_name(method, path, desc)
            
            # Find path variables
            path_vars = re.findall(r'\{(\w+)\}', path)
            
            # Signature construction
            params_list = ["self"]
            for v in path_vars:
                params_list.append(f"{v}: str")
                
            if method in ["POST", "PUT", "PATCH"]:
                params_list.append("data: Optional[Dict[str, Any]] = None")
            else:
                params_list.append("params: Optional[Dict[str, Any]] = None")
                
            sig = f"    def {method_name}({', '.join(params_list)}) -> Dict[str, Any]:"
            lines.append(sig)
            
            # Google Docstring
            doc = [
                '        """',
                f'        {desc}',
                '        ',
                '        Args:'
            ]
            for v in path_vars:
                doc.append(f'            {v} (str): Path parameter.')
            if method in ["POST", "PUT", "PATCH"]:
                doc.append('            data (dict, optional): Request body payload.')
            else:
                doc.append('            params (dict, optional): Query parameters.')
            doc.extend([
                '            ',
                '        Returns:',
                '            dict: Deserialized JSON response dict.',
                '            ',
                '        Raises:',
                '            AuthenticationError: On 401/403 credentials failure.',
                '            ValidationError: On 400 validation issues.',
                '            RateLimitError: On 429 too many requests.',
                '            ServerError: On 5xx API failures.',
                '            ',
                '        Example:',
                f'            >>> client = {class_name}("your_key_here")'
            ])
            
            example_args = []
            for v in path_vars:
                example_args.append(f'{v}="sample_{v}"')
            if method in ["POST", "PUT", "PATCH"]:
                example_args.append('data={"key": "value"}')
            else:
                example_args.append('params={"key": "value"}')
                
            doc.extend([
                f'            >>> response = client.{method_name}({", ".join(example_args)})',
                '            >>> print(response)',
                '        """'
            ]
            )
            lines.extend(doc)
            
            # Path injection
            if path_vars:
                # Replace {var} with f-string formatted value
                formatted_path = path
                for v in path_vars:
                    formatted_path = formatted_path.replace(f"{{{v}}}", f"{{{v}}}")
                lines.append(f"        path_str = f'{formatted_path}'")
            else:
                lines.append(f"        path_str = '{path}'")
                
            # Invoke helper
            if method in ["POST", "PUT", "PATCH"]:
                lines.append(f"        return self._request('{method}', path_str, data=data)")
            else:
                lines.append(f"        return self._request('{method}', path_str, params=params)")
            lines.append("")

        # Runnable Main Block
        lines.extend([
            'if __name__ == "__main__":',
            '    # Local self-verification runner',
            f'    print("Initializing {class_name} integration test...")',
            f'    api_key = os.getenv("API_KEY", "YOUR_API_KEY_HERE")',
            f'    client = {class_name}(api_key=api_key)',
            '    ',
            '    try:',
            '        # Demonstrating standard request exception flow',
            '        print("Executing mock method invoke...")'
        ])
        
        # Call first method if available
        if endpoints:
            first_ep = endpoints[0]
            first_method = self.clean_method_name(first_ep["method"], first_ep["path"], first_ep["description"])
            vars_needed = re.findall(r'\{(\w+)\}', first_ep["path"])
            call_args = []
            for v in vars_needed:
                call_args.append(f'{v}="test_id"')
            if first_ep["method"].upper() in ["POST", "PUT", "PATCH"]:
                call_args.append('data={"test": "data"}')
                
            lines.append(f"        # response = client.{first_method}({', '.join(call_args)})")
            lines.append(f"        # print('Response:', response)")
            
        lines.extend([
            '        print("Setup complete! Edit environment variables to execute live requests.")',
            '    except APIClientError as e:',
            '        print(f"SDK failure encountered: {e}")'
        ])

        return "\n".join(lines)
