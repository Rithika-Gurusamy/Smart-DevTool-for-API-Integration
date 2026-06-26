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
2. Use native `fetch` (with async/await).
3. Separate each endpoint example clearly with high-fidelity comments and console logs. E.g.:
   // ==============================================================================
   // 1. Create Customer (POST /v1/customers)
   // ==============================================================================
4. Authentication: Apply the authentication method {auth_type} cleanly to the headers or parameters.
5. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payload objects) clearly at the top of each request example so developers can easily replace them.
6. Execution: Construct the full URL (injecting path variables, formatting query parameters using `URLSearchParams` or string building), set headers, and invoke `fetch()`.
7. Error Handling: Include standard error checks on `response.ok`, parsing JSON on success, and printing the status code and text/error on failure. Use try/catch blocks to capture network failures.

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

    def _generate_fallback(self, api_name: str, auth_type: str, auth_desc: str, endpoints: list) -> str:
        """
        Dynamically builds a high-fidelity REST integration script using Fetch API when LLM is unavailable.
        """
        lines = [
            f"// Standalone JavaScript REST Integration Examples for {api_name}",
            f"// Auth Method: {auth_type} ({auth_desc})",
            "",
            "// General Configuration",
            "const BASE_URL = 'https://api.example.com';",
        ]

        if auth_type == "Bearer Token":
            lines.append("const API_TOKEN = process.env.API_TOKEN || 'YOUR_BEARER_TOKEN';")
        else:
            lines.append("const API_KEY = process.env.API_KEY || 'YOUR_API_KEY';")

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

            lines.append(f"    let url = `${{BASE_URL}}{js_path}`;")

            # Headers
            lines.append("    const headers = {")
            lines.append("        'Content-Type': 'application/json',")
            if auth_type == "Bearer Token":
                lines.append("        'Authorization': `Bearer ${API_TOKEN}`")
            elif auth_type == "API Key":
                lines.append("        'X-API-Key': API_KEY")
            lines.append("    };")

            # Fetch Config options
            fetch_options = {
                "method": method,
                "headers": "headers"
            }

            if method in ["POST", "PUT", "PATCH"]:
                lines.extend([
                    "    const payload = {",
                    "        example_key: 'example_value'",
                    "    };"
                ])
                fetch_options["body"] = "JSON.stringify(payload)"
            else:
                lines.extend([
                    "    const params = {",
                    "        limit: '10'",
                    "    };",
                    "    url += '?' + new URLSearchParams(params).toString();"
                ])

            # Format options string
            opt_strs = [f"        {k}: {v}" for k, v in fetch_options.items()]
            lines.append("    const options = {")
            lines.append(",\n".join(opt_strs))
            lines.append("    };")

            # Execute fetch request
            lines.extend([
                "    try {",
                "        console.log(`Sending ${options.method} request to: ${url}`);",
                "        const response = await fetch(url, options);",
                "        console.log(`Response Status: ${response.status}`);",
                "        if (response.ok) {",
                "            try {",
                "                const data = await response.json();",
                "                console.log('Response JSON:', JSON.stringify(data, null, 2));",
                "            } catch (e) {",
                "                const text = await response.text();",
                "                console.log('Response Text:', text);",
                "            }",
                "        } else {",
                "            const errorText = await response.text();",
                "            console.error('Request Failed:', response.status, errorText);",
                "        }",
                "    } catch (error) {",
                "        console.error('Network Error:', error.message);",
                "    }"
            ])
            lines.append("")

        lines.append("}")
        lines.append("")
        lines.append("// To execute, run in an environment with fetch support (e.g. Node.js 18+ or browser)")
        lines.append("// runExamples();")

        return "\n".join(lines)
