import os
import re
import json
import io
import zipfile

def get_js_method_name(method, path, service_name, crud_pattern=None):
    """
    Generate a camelCase JavaScript method name for the endpoint based on method, path,
    and optional CRUD pattern.
    """
    # Clean file extensions
    clean_path = re.sub(r'\.\w+$', '', path)
    
    # Split path and remove path variables
    segments = [s for s in clean_path.split('/') if s and not s.startswith('{') and not s.startswith(':')]
    
    # Strip common versioning prefixes (e.g. v1, v2)
    if segments and re.match(r'^v\d+$', segments[0]):
        segments.pop(0)
        
    if not segments:
        resource = service_name.replace("Service", "")
    else:
        resource = segments[-1]
        # Convert kebab-case or snake_case to PascalCase
        resource = "".join(x.title() for x in re.split(r'[-_]', resource))
        
    # Singularize resource for specific resource-oriented HTTP methods
    is_singular = '{' in path or ':' in path or method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']
    if is_singular:
        if resource.endswith('ies'):
            resource = resource[:-3] + 'y'
        elif resource.endswith('s') and not resource.endswith('ss'):
            resource = resource[:-1]
            
    method_lower = method.lower()
    
    if crud_pattern:
        pattern_lower = crud_pattern.lower()
        if "create" in pattern_lower:
            action = "create"
        elif "read" in pattern_lower or "get" in pattern_lower:
            action = "get"
        elif "update" in pattern_lower:
            action = "update"
        elif "delete" in pattern_lower:
            action = "delete"
        elif "list" in pattern_lower or "search" in pattern_lower:
            action = "list" if resource.endswith('s') else "get"
        else:
            action = method_lower
    else:
        if method_lower == 'post':
            action = 'create'
        elif method_lower == 'get':
            action = 'get' if is_singular else 'list'
        elif method_lower in ['put', 'patch']:
            action = 'update'
        elif method_lower == 'delete':
            action = 'delete'
        else:
            action = method_lower
            
    method_name = action + resource[0].upper() + resource[1:]
    return method_name

def parse_path_params(path):
    """
    Extracts path parameters (like {id} or :id) from path.
    Returns normalized camelCase js argument names and the ES6-ready path string.
    """
    braces_params = re.findall(r'\{(\w+)\}', path)
    colon_params = re.findall(r':(\w+)', path)
    all_raw_params = braces_params + colon_params
    
    js_args = []
    param_mappings = {}
    for rp in all_raw_params:
        # Convert snake_case / PascalCase to camelCase
        parts = re.split(r'[-_]', rp)
        camel = parts[0].lower() + "".join(p.title() for p in parts[1:])
        js_args.append(camel)
        param_mappings[rp] = camel
        
    js_path = path
    for rp, camel in param_mappings.items():
        js_path = js_path.replace(f"{{{rp}}}", f"${{{camel}}}")
        js_path = js_path.replace(f":{rp}", f"${{{camel}}}")
        
    return js_args, js_path

def generate_frontend_client_files(blueprint: dict) -> dict:
    """
    Generate all files for the frontend networking and API service layers.
    Returns a dictionary mapping relative file paths to their file content string.
    """
    files = {}
    
    # Extract blueprint config and auth
    config_plan = blueprint.get("configuration_plan", {})
    auth_plan = blueprint.get("authentication_plan", {})
    service_plan = blueprint.get("service_plan", [])
    resource_groups = blueprint.get("resource_groups", [])
    crud_metadata = blueprint.get("crud_metadata", [])
    
    api_name = blueprint.get("api_name", "API")
    framework = blueprint.get("framework", "React")
    
    # 1. Error Utilities
    files["src/api/errorUtils.js"] = """/**
 * Custom API Error class to normalize error responses from the backend.
 */
export class APIError extends Error {
  constructor(message, status = null, data = null, originalError = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
    this.originalError = originalError;
    
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, APIError);
    }
  }
}

/**
 * Normalizes Axios errors into a standard format.
 * @param {object} error - The Axios error object
 * @returns {APIError} The normalized API error
 */
export const handleAPIError = (error) => {
  let message = 'An unexpected error occurred.';
  let status = null;
  let data = null;

  if (error.response) {
    status = error.response.status;
    data = error.response.data;
    
    if (typeof data === 'string') {
      message = data;
    } else if (data) {
      message = data.message || data.error || data.err || `Request failed with status ${status}`;
    }
  } else if (error.request) {
    message = 'No response received from the server. Please check your network connection or CORS settings.';
  } else {
    message = error.message;
  }

  return new APIError(message, status, data, error);
};
"""

    # 2. Centralized Axios Client (apiClient.js)
    base_url = config_plan.get("api_base_url", "https://api.example.com")
    timeout = config_plan.get("timeout_ms", 10000)
    default_headers = config_plan.get("default_headers", {"Content-Type": "application/json"})
    
    auth_strategy = auth_plan.get("strategy", "None")
    login_ep = auth_plan.get("login_endpoint", "")
    logout_ep = auth_plan.get("logout_endpoint", "")
    refresh_ep = auth_plan.get("refresh_token_endpoint", "")
    storage_suggestion = auth_plan.get("token_storage_suggestion", "localStorage")
    auth_desc = auth_plan.get("description", "")
    
    # Generate auth interceptor header injection
    auth_injection = ""
    if auth_strategy in ["Bearer Token", "JWT"]:
        auth_injection = "config.headers['Authorization'] = `Bearer ${token}`;"
    elif auth_strategy == "API Key":
        auth_injection = "config.headers['X-API-Key'] = token;"
    elif auth_strategy == "Basic Auth":
        auth_injection = "config.headers['Authorization'] = `Basic ${token}`;"
    else:
        auth_injection = "config.headers['Authorization'] = `Bearer ${token}`;"
        
    # Generate refresh token interceptor code if available
    refresh_interceptor = ""
    if refresh_ep:
        # Extract path and method from refresh token endpoint string (e.g. POST /v1/auth/refresh)
        refresh_parts = refresh_ep.split()
        refresh_method = "post"
        refresh_path = refresh_ep
        if len(refresh_parts) == 2:
            refresh_method = refresh_parts[0].lower()
            refresh_path = refresh_parts[1]
            
        refresh_interceptor = f"""
    if (status === 401 && !originalRequest._retry) {{
      originalRequest._retry = true;
      try {{
        const refreshToken = tokenStorage.getRefreshToken();
        if (refreshToken) {{
          // Request refresh token using a clean Axios instance to avoid loops
          const response = await axios.create().{refresh_method}('{base_url}{refresh_path}', {{ refresh_token: refreshToken }});
          const token = response.data.token || response.data.accessToken || response.data.auth_token;
          const newRefreshToken = response.data.refresh_token || response.data.refreshToken;
          
          tokenStorage.setToken(token);
          if (newRefreshToken) {{
            tokenStorage.setRefreshToken(newRefreshToken);
          }}
          
          // Retry original request with new token
          originalRequest.headers['Authorization'] = `Bearer ${{token}}`;
          return apiClient(originalRequest);
        }}
      }} catch (refreshError) {{
        tokenStorage.clearToken();
        tokenStorage.clearRefreshToken();
        return Promise.reject(handleAPIError(refreshError));
      }}
    }}
"""

    api_client_code = f"""import axios from 'axios';
import {{ handleAPIError }} from './errorUtils';

/**
 * Abstraction layer for authentication token storage.
 * Follows suggested pattern: {storage_suggestion}
 */
export const tokenStorage = {{
  getToken: () => localStorage.getItem('auth_token'),
  setToken: (token) => localStorage.setItem('auth_token', token),
  clearToken: () => localStorage.removeItem('auth_token'),
  getRefreshToken: () => localStorage.getItem('refresh_token'),
  setRefreshToken: (token) => localStorage.setItem('refresh_token', token),
  clearRefreshToken: () => localStorage.removeItem('refresh_token'),
}};

/**
 * Centralized HTTP Client Instance using Axios.
 * Configured for {api_name} API.
 */
const apiClient = axios.create({{
  baseURL: process.env.REACT_APP_API_BASE_URL || '{base_url}',
  timeout: {timeout},
  headers: {json.dumps(default_headers, indent=2)}
}});

// Request Interceptor: Inject Auth headers dynamically
apiClient.interceptors.request.use(
  (config) => {{
    const token = tokenStorage.getToken();
    if (token) {{
      {auth_injection}
    }}
    return config;
  }},
  (error) => Promise.reject(error)
);

// Response Interceptor: Centralized formatting & auto-refresh
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error) => {{
    const originalRequest = error.config;
    const status = error.response ? error.response.status : null;
    {refresh_interceptor}
    return Promise.reject(handleAPIError(error));
  }}
);

export default apiClient;
"""
    files["src/api/apiClient.js"] = api_client_code
    
    # 3. Services Generation
    # Flatten endpoint mappings from resource groups to query details (description, crud pattern)
    endpoint_details = {}
    for group in resource_groups:
        for ep in group.get("endpoints", []):
            key = f"{ep.get('method', '').upper()} {ep.get('path', '')}"
            endpoint_details[key] = ep
            
    crud_patterns = {}
    for item in crud_metadata:
        key = f"{item.get('method', '').upper()} {item.get('path', '')}"
        crud_patterns[key] = item.get("pattern", "")
        
    # Helper to build a service file
    def build_service_file(service):
        service_name = service.get("service_name", "ApiService")
        desc = service.get("description", f"Service layer for {service_name}")
        assigned_endpoints = service.get("endpoints", [])
        
        # Imports
        code_lines = [
            f"import apiClient from '../apiClient';",
            "",
            "/**",
            f" * {desc}",
            " */"
        ]
        
        methods_code = []
        method_count = 0
        
        for ep_str in assigned_endpoints:
            # Parse endpoint method and path
            parts = ep_str.split(None, 1)
            if len(parts) != 2:
                continue
            method = parts[0].upper()
            path = parts[1]
            
            # Lookup metadata
            detail = endpoint_details.get(ep_str, {})
            ep_desc = detail.get("description", f"Executes {method} request to {path}")
            pattern = crud_patterns.get(ep_str)
            
            # Generate JS-safe method names and arguments
            js_args, js_path = parse_path_params(path)
            method_name = get_js_method_name(method, path, service_name, pattern)
            
            # Determine method arguments and calls
            js_args_str = ", ".join(js_args)
            
            # Formulate Axios request arguments
            axios_args = []
            
            # URL is always first argument, formatted as template literal if parameters exist
            if js_args:
                axios_args.append(f"`{js_path}`")
            else:
                axios_args.append(f"'{path}'")
                
            # If payload methods (POST, PUT, PATCH), we accept data
            if method in ["POST", "PUT", "PATCH"]:
                if js_args_str:
                    js_args_str += ", data"
                else:
                    js_args_str = "data"
                axios_args.append("data")
            # If read/query methods (GET, DELETE), we accept query parameters
            else:
                if js_args_str:
                    js_args_str += ", params = {}"
                else:
                    js_args_str = "params = {}"
                axios_args.append("{ params }")
                
            # Render JSDoc comments
            param_docs = []
            for arg in js_args:
                param_docs.append(f" * @param {{string|number}} {arg} - Path parameter")
            if method in ["POST", "PUT", "PATCH"]:
                param_docs.append(" * @param {object} data - Request body payload")
            else:
                param_docs.append(" * @param {object} [params] - Query parameters object")
                
            jsdoc = "\n".join([
                "/**",
                f" * {ep_desc}",
                f" * {method} {path}",
                *param_docs,
                " * @returns {Promise<any>} The parsed server response",
                " */"
            ])
            
            method_body = f"""export const {method_name} = async ({js_args_str}) => {{
  return apiClient.{method.lower()}({', '.join(axios_args)});
}};"""
            
            methods_code.append(jsdoc + "\n" + method_body + "\n")
            method_count += 1
            
        code_lines.extend(methods_code)
        return "\n".join(code_lines), method_count

    total_crud_methods = 0
    generated_services_info = []
    
    for svc in service_plan:
        svc_name = svc.get("service_name", "ApiService")
        # Ensure it has .js extension
        file_path = f"src/api/services/{svc_name}.js"
        
        # Build file
        content, m_count = build_service_file(svc)
        files[file_path] = content
        total_crud_methods += m_count
        generated_services_info.append({
            "service_name": svc_name,
            "methods_count": m_count,
            "description": svc.get("description", "")
        })
        
    # 4. README.md
    readme_services_list = []
    for s_info in generated_services_info:
        readme_services_list.append(f"- **{s_info['service_name']}**: {s_info['description']} ({s_info['methods_count']} methods)")
        
    usage_example = ""
    if generated_services_info:
        first_svc = generated_services_info[0]
        # Build import/usage code example
        usage_example = f"""// Import client config and service layer
import {{ {first_svc['service_name']} }} from './api/services/{first_svc['service_name']}';

// Set up authorization token if needed (e.g. after login)
import {{ tokenStorage }} from './api/apiClient';
tokenStorage.setToken('your-auth-token');

// Execute call
const fetchData = async () => {{
  try {{
    const response = await {first_svc['service_name']}.methods... // Call one of the generated methods
    console.log('Success:', response);
  }} catch (error) {{
    console.error('Error (Status: ' + error.status + '):', error.message);
  }}
}};
"""
        
    readme_content = f"""# {api_name} Frontend API Client

Generated dynamically by Smart DevTool. Includes a centralized HTTP networking layer (Axios instance), authentication injection helpers, custom error normalization, and resource-focused service classes.

## Features
- **Centralized Client**: Centralized interceptors for appending tokens and mapping API Errors.
- **Unified Errors**: Normalized error exceptions containing status code, error body, and original wrapper details.
- **Resource Services**: Modular service classes mapped according to parsed documentation resources.

## Project Layout
```
src/
└── api/
    ├── apiClient.js     # Axios configuration and token storage helpers
    ├── errorUtils.js    # Centralized error mapping and custom APIError class
    └── services/        # Service modules
        {"".join([f"├── {s['service_name']}.js\\n        " for s in generated_services_info])}
```

## Installation
Ensure you install Axios in your project root:
```bash
npm install axios
# or
yarn add axios
```

## Configuration
Set the following environment variable to override the default API URL:
- React: `REACT_APP_API_BASE_URL`

## Authentication setup
This wrapper includes helper functions for token management. Save the auth token to local storage via the `tokenStorage` helper:
```javascript
import {{ tokenStorage }} from './api/apiClient';

// Store token (automatically injected to subsequent requests)
tokenStorage.setToken('user-jwt-or-api-key');

// Get active token
const token = tokenStorage.getToken();

// Clear token (e.g. on user logout)
tokenStorage.clearToken();
```

## Service Summary
{"\\n".join(readme_services_list)}

## Example Usage
```javascript
{usage_example}
```
"""
    files["README.md"] = readme_content
    
    return files, total_crud_methods

def generate_frontend_zip(blueprint: dict) -> bytes:
    """
    Generates a zip archive containing the frontend networking and service files.
    Returns the ZIP file contents as bytes.
    """
    files_map, _ = generate_frontend_client_files(blueprint)
    
    # Create an in-memory byte stream
    memory_zip = io.BytesIO()
    
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filepath, content in files_map.items():
            # Write file
            zipf.writestr(filepath, content)
            
    memory_zip.seek(0)
    return memory_zip.getvalue()
