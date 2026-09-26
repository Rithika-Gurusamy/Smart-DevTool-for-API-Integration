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


def generate_integration_code(api_metadata: dict, output_format: str, use_case: str) -> str:
    """
    Generates frontend API integration code based on the selected output format.
    output_format: "Vanilla JS (Fetch)" or "React (Axios)"
    """
    if "React" in output_format or "Axios" in output_format:
        return generate_axios_code(api_metadata, use_case)
    else:
        return generate_fetch_code(api_metadata, use_case)


def generate_fetch_code(api_metadata: dict, use_case: str) -> str:
    """
    Generates clean Vanilla JavaScript fetch() request code for all relevant endpoints.
    Uses Gemini if available, falls back to a local template generator.
    """
    if api_key and HAS_GEMINI:
        return _generate_code_with_gemini(api_metadata, use_case, style="fetch")
    return _generate_fetch_local(api_metadata)


def generate_axios_code(api_metadata: dict, use_case: str) -> str:
    """
    Generates React-ready Axios service code for all relevant endpoints.
    Uses Gemini if available, falls back to a local template generator.
    """
    if api_key and HAS_GEMINI:
        return _generate_code_with_gemini(api_metadata, use_case, style="axios")
    return _generate_axios_local(api_metadata)


def _generate_code_with_gemini(api_metadata: dict, use_case: str, style: str) -> str:
    """
    Uses Gemini to generate high-quality frontend integration code.
    style: "fetch" or "axios"
    """
    api_name = api_metadata.get("api_name", "API")
    auth_info = api_metadata.get("auth_method", {})
    endpoints = api_metadata.get("endpoints", [])

    # Filter to Primary + Supporting endpoints only
    relevant_eps = [e for e in endpoints if e.get("category") in ["Primary", "Supporting"]]
    if not relevant_eps:
        relevant_eps = endpoints[:10]

    endpoints_desc = json.dumps(relevant_eps, indent=2)

    if style == "fetch":
        style_instruction = """Generate clean Vanilla JavaScript code using the native fetch() API.
- Use async/await syntax
- Create a reusable API configuration object with BASE_URL and headers
- Create one async function per endpoint (named descriptively e.g. createCustomer, getProducts)
- Include proper error handling with try/catch
- Include Content-Type and Authorization headers
- Add JSDoc comments for each function
- Export all functions at the bottom
- Make it ready to use in any HTML page with a <script type="module"> tag"""
    else:
        style_instruction = """Generate clean React-ready code using Axios.
- Import axios at the top
- Create an axios instance with baseURL, headers, and timeout
- Create one async function per endpoint (named descriptively e.g. createCustomer, getProducts)
- Include proper error handling with try/catch
- Include Content-Type and Authorization headers
- Add JSDoc comments for each function
- Export all functions as named exports
- Make it ready to import into any React component"""

    prompt = f"""You are a Senior Frontend Developer. Generate production-ready API integration code.

API Name: {api_name}
Authentication: {json.dumps(auth_info)}
Use Case: {use_case}
Endpoints:
{endpoints_desc}

{style_instruction}

CRITICAL RULES:
1. Return ONLY the code. No markdown fences, no explanations, no conversational text.
2. Make the code clean, well-commented, and immediately usable.
3. Use descriptive function names based on what each endpoint does.
4. Include a comment at the top explaining what this file does.
"""

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean any accidental markdown wrap
        if text.startswith("```javascript"):
            text = text[len("```javascript"):]
        if text.startswith("```js"):
            text = text[len("```js"):]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    except Exception as e:
        print(f"Gemini code generation failed ({str(e)}). Falling back to local template.")
        if style == "fetch":
            return _generate_fetch_local(api_metadata)
        else:
            return _generate_axios_local(api_metadata)


def _generate_fetch_local(api_metadata: dict) -> str:
    """
    Local template-based Vanilla JS fetch() code generator (fallback).
    """
    api_name = api_metadata.get("api_name", "API")
    auth_info = api_metadata.get("auth_method", {})
    endpoints = api_metadata.get("endpoints", [])
    auth_type = auth_info.get("type", "API Key")

    lines = [
        f"// =============================================================",
        f"// {api_name} — Vanilla JavaScript API Integration (Fetch)",
        f"// =============================================================",
        f"",
        f"const API_CONFIG = {{",
        f"  BASE_URL: 'https://api.example.com',",
        f"  API_KEY: 'YOUR_API_KEY_HERE',",
        f"}};",
        f"",
        f"/**",
        f" * Shared headers for all requests.",
        f" */",
        f"function getHeaders() {{",
        f"  return {{",
        f"    'Content-Type': 'application/json',",
    ]

    if auth_type == "Bearer Token":
        lines.append(f"    'Authorization': `Bearer ${{API_CONFIG.API_KEY}}`,")
    elif auth_type == "API Key":
        lines.append(f"    'X-API-Key': API_CONFIG.API_KEY,")
    elif auth_type == "Basic Auth":
        lines.append(f"    'Authorization': `Basic ${{btoa(API_CONFIG.API_KEY + ':')}}`,"  )

    lines.extend([
        f"  }};",
        f"}}",
        f"",
    ])

    # Filter to relevant endpoints
    relevant_eps = [e for e in endpoints if e.get("category") in ["Primary", "Supporting"]]
    if not relevant_eps:
        relevant_eps = endpoints[:10]

    for ep in relevant_eps:
        method = ep.get("method", "GET").upper()
        path = ep.get("path", "/")
        desc = ep.get("description", "")

        # Generate function name
        func_name = _make_function_name(method, path)

        # Detect path params
        path_params = re.findall(r'\{(\w+)\}', path)
        param_list = ", ".join(path_params)
        if method in ["POST", "PUT", "PATCH"]:
            param_list = f"{param_list}, data" if param_list else "data"
        elif method == "GET":
            param_list = f"{param_list}, params = {{}}" if param_list else "params = {}"

        # Build URL
        if path_params:
            url_expr = f"`${{API_CONFIG.BASE_URL}}{path}`".replace("{", "${")
        else:
            url_expr = f"`${{API_CONFIG.BASE_URL}}{path}`"

        lines.extend([
            f"/**",
            f" * {desc}",
            f" * {method} {path}",
            f" */",
            f"async function {func_name}({param_list}) {{",
            f"  try {{",
        ])

        if method == "GET":
            lines.extend([
                f"    const queryString = new URLSearchParams(params).toString();",
                f"    const url = queryString ? {url_expr} + '?' + queryString : {url_expr};",
                f"    const response = await fetch(url, {{",
                f"      method: '{method}',",
                f"      headers: getHeaders(),",
                f"    }});",
            ])
        elif method in ["POST", "PUT", "PATCH"]:
            lines.extend([
                f"    const response = await fetch({url_expr}, {{",
                f"      method: '{method}',",
                f"      headers: getHeaders(),",
                f"      body: JSON.stringify(data),",
                f"    }});",
            ])
        else:  # DELETE
            lines.extend([
                f"    const response = await fetch({url_expr}, {{",
                f"      method: '{method}',",
                f"      headers: getHeaders(),",
                f"    }});",
            ])

        lines.extend([
            f"",
            f"    if (!response.ok) {{",
            f"      const errorBody = await response.text();",
            f"      throw new Error(`{method} {path} failed: ${{response.status}} ${{errorBody}}`);",
            f"    }}",
            f"",
            f"    return await response.json();",
            f"  }} catch (error) {{",
            f"    console.error('[{api_name}] {func_name} error:', error);",
            f"    throw error;",
            f"  }}",
            f"}}",
            f"",
        ])

    # Export
    func_names = [_make_function_name(ep.get("method", "GET"), ep.get("path", "/")) for ep in relevant_eps]
    lines.append(f"// Export all functions")
    lines.append(f"export {{ {', '.join(func_names)} }};")

    return "\n".join(lines)


def _generate_axios_local(api_metadata: dict) -> str:
    """
    Local template-based React Axios service code generator (fallback).
    """
    api_name = api_metadata.get("api_name", "API")
    auth_info = api_metadata.get("auth_method", {})
    endpoints = api_metadata.get("endpoints", [])
    auth_type = auth_info.get("type", "API Key")

    lines = [
        f"// =============================================================",
        f"// {api_name} — React API Service (Axios)",
        f"// =============================================================",
        f"",
        f"import axios from 'axios';",
        f"",
        f"// Create a pre-configured Axios instance",
        f"const apiClient = axios.create({{",
        f"  baseURL: process.env.REACT_APP_API_BASE_URL || 'https://api.example.com',",
        f"  timeout: 10000,",
        f"  headers: {{",
        f"    'Content-Type': 'application/json',",
    ]

    if auth_type == "Bearer Token":
        lines.append(f"    'Authorization': `Bearer ${{process.env.REACT_APP_API_KEY}}`,")
    elif auth_type == "API Key":
        lines.append(f"    'X-API-Key': process.env.REACT_APP_API_KEY,")

    lines.extend([
        f"  }},",
        f"}});",
        f"",
    ])

    # Filter to relevant endpoints
    relevant_eps = [e for e in endpoints if e.get("category") in ["Primary", "Supporting"]]
    if not relevant_eps:
        relevant_eps = endpoints[:10]

    for ep in relevant_eps:
        method = ep.get("method", "GET").upper()
        path = ep.get("path", "/")
        desc = ep.get("description", "")

        func_name = _make_function_name(method, path)

        # Detect path params
        path_params = re.findall(r'\{(\w+)\}', path)
        param_list = ", ".join(path_params)
        if method in ["POST", "PUT", "PATCH"]:
            param_list = f"{param_list}, data" if param_list else "data"
        elif method == "GET":
            param_list = f"{param_list}, params = {{}}" if param_list else "params = {}"

        # Build URL
        if path_params:
            url_expr = f"`{path}`".replace("{", "${")
        else:
            url_expr = f"'{path}'"

        lines.extend([
            f"/**",
            f" * {desc}",
            f" * {method} {path}",
            f" */",
            f"export async function {func_name}({param_list}) {{",
            f"  try {{",
        ])

        if method == "GET":
            lines.extend([
                f"    const response = await apiClient.get({url_expr}, {{ params }});",
                f"    return response.data;",
            ])
        elif method == "POST":
            lines.extend([
                f"    const response = await apiClient.post({url_expr}, data);",
                f"    return response.data;",
            ])
        elif method == "PUT":
            lines.extend([
                f"    const response = await apiClient.put({url_expr}, data);",
                f"    return response.data;",
            ])
        elif method == "PATCH":
            lines.extend([
                f"    const response = await apiClient.patch({url_expr}, data);",
                f"    return response.data;",
            ])
        elif method == "DELETE":
            lines.extend([
                f"    const response = await apiClient.delete({url_expr});",
                f"    return response.data;",
            ])

        lines.extend([
            f"  }} catch (error) {{",
            f"    console.error('[{api_name}] {func_name} error:', error.response?.data || error.message);",
            f"    throw error;",
            f"  }}",
            f"}}",
            f"",
        ])

    return "\n".join(lines)


def _make_function_name(method: str, path: str) -> str:
    """
    Generates a clean camelCase function name from HTTP method + path.
    e.g. POST /v1/customers -> createCustomers
         GET /v1/customers/{id} -> getCustomer
         DELETE /v1/products/{id} -> deleteProduct
    """
    method = method.upper()

    # Strip version prefix and clean path
    clean_path = re.sub(r'/v\d+', '', path)
    segments = [s for s in clean_path.strip("/").split("/") if s and not s.startswith("{")]

    if not segments:
        resource = "resource"
    else:
        resource = segments[-1].replace("-", "_").replace(".", "_")

    # CamelCase resource
    resource = "".join(word.capitalize() for word in resource.split("_"))

    # Choose verb
    has_id = "{" in path
    if method == "POST":
        verb = "create"
    elif method == "GET":
        verb = "get" if has_id else "list"
    elif method in ["PUT", "PATCH"]:
        verb = "update"
    elif method == "DELETE":
        verb = "delete"
    else:
        verb = method.lower()

    return f"{verb}{resource}"


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

def generate_sequence_diagram(api_metadata: dict, output_format: str = "JavaScript") -> str:
    """
    Generates Mermaid sequence diagram markup.
    """
    api_name = api_metadata.get("api_name", "API")
    endpoints = api_metadata.get("endpoints", [])

    # Determine client label
    if "React" in output_format or "Axios" in output_format:
        client_label = "React App (Axios)"
    else:
        client_label = "Browser (Fetch)"

    lines = [
        "sequenceDiagram",
        "    autonumber",
        "    actor Developer",
        "    participant App as App Logic",
        f"    participant Client as {client_label}",
        f"    participant Gateway as {api_name} Gateway",
        ""
    ]

    # Filter to relevant endpoints
    relevant_eps = [e for e in endpoints if e.get("category") in ["Primary", "Supporting"]]
    if not relevant_eps:
        relevant_eps = endpoints[:10]

    for idx, ep in enumerate(relevant_eps, 1):
        method = ep["method"]
        path = ep["path"]
        desc = ep["description"]

        # Clean description for Mermaid safety
        desc_clean = re.sub(r'[^a-zA-Z0-9\s_\-\/]', '', desc)
        if len(desc_clean) > 40:
            desc_clean = desc_clean[:37] + "..."

        lines.append(f"    Note over App, Client: Step {idx}: {desc_clean}")
        lines.append(f"    Developer->>App: Initiates flow")
        lines.append(f"    App->>Client: Call {_make_function_name(method, path)}()")
        lines.append(f"    Note over Client: Attach auth headers")
        lines.append(f"    Client->>Gateway: {method} {path}")
        lines.append(f"    Gateway-->>Client: 200 OK (JSON Payload)")
        lines.append(f"    Client-->>App: Return parsed data")
        lines.append(f"    App-->>Developer: Render result in UI")
        lines.append("")

    return "\n".join(lines)
