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
2. Imports: import `requests` and `json`.
3. Separate each endpoint example clearly with high-fidelity header comments and print statements. E.g.:
   # ==============================================================================
   # 1. Create Customer (POST /v1/customers)
   # ==============================================================================
4. Authentication: Show how to apply the authentication method {auth_type} cleanly to the headers or parameters.
5. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payload dictionaries) clearly at the top of each request example so developers can easily replace them.
6. Execution: Construct the full URL (injecting path variables), set headers, and invoke the request using `requests.get()`, `requests.post()`, etc.
7. Error Handling: Include a basic check of `response.status_code` to confirm success, and print the parsed JSON response or the raw response text on failure.
   Example:
   if response.status_code in [200, 201]:
       print("Success:", response.json())
   else:
       print("Error:", response.status_code, response.text)

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
            "import requests",
            "import json",
            "import os",
            "",
            "# General Configuration",
            "BASE_URL = 'https://api.example.com'",
        ]

        if auth_type == "Bearer Token":
            lines.append("API_TOKEN = os.getenv('API_TOKEN', 'YOUR_BEARER_TOKEN')")
        elif auth_type == "Basic Auth":
            lines.append("USERNAME = os.getenv('API_USERNAME', 'YOUR_USERNAME')")
            lines.append("PASSWORD = os.getenv('API_PASSWORD', 'YOUR_PASSWORD')")
        else:
            lines.append("API_KEY = os.getenv('API_KEY', 'YOUR_API_KEY')")

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
                lines.append(f"url = f'{{BASE_URL}}{formatted_path}'")
            else:
                lines.append(f"url = f'{{BASE_URL}}{path}'")

            # Headers and Auth
            lines.append("headers = {")
            lines.append("    'Content-Type': 'application/json',")
            if auth_type == "Bearer Token":
                lines.append("    'Authorization': f'Bearer {API_TOKEN}'")
            elif auth_type == "API Key":
                lines.append("    'X-API-Key': API_KEY")
            lines.append("}")

            # Basic Auth setup
            auth_arg = ""
            if auth_type == "Basic Auth":
                auth_arg = ", auth=(USERNAME, PASSWORD)"

            # Payload or Query Parameters
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("payload = {")
                lines.append("    'example_key': 'example_value'")
                lines.append("}")
                lines.append(f"print(f'Sending {method} request to: {{url}}')")
                lines.append(f"response = requests.{method.lower()}(url, headers=headers, json=payload{auth_arg})")
            else:
                lines.append("params = {")
                lines.append("    'limit': 10")
                lines.append("}")
                lines.append(f"print(f'Sending {method} request to: {{url}}')")
                lines.append(f"response = requests.{method.lower()}(url, headers=headers, params=params{auth_arg})")

            # Status Checking and Printing
            lines.extend([
                "print(f'Response Status: {response.status_code}')",
                "if response.status_code in [200, 201, 204]:",
                "    try:",
                "        print('Response JSON:', json.dumps(response.json(), indent=2))",
                "    except ValueError:",
                "        print('Response Text:', response.text)",
                "else:",
                "    print('Request Failed:', response.status_code, response.text)",
                ""
            ])

        return "\n".join(lines)
