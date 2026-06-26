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
    clean_path = re.sub(r'\.\w+$', '', path)
    segments = [s for s in clean_path.split('/') if s and not s.startswith('{') and not s.startswith(':')]
    
    if segments and re.match(r'^v\d+$', segments[0]):
        segments.pop(0)
        
    if not segments:
        resource = service_name.replace("Service", "")
    else:
        resource = segments[-1]
        resource = "".join(x.title() for x in re.split(r'[-_]', resource))
        
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
        parts = re.split(r'[-_]', rp)
        camel = parts[0].lower() + "".join(p.title() for p in parts[1:])
        js_args.append(camel)
        param_mappings[rp] = camel
        
    js_path = path
    for rp, camel in param_mappings.items():
        js_path = js_path.replace(f"{{{rp}}}", f"${{{camel}}}")
        js_path = js_path.replace(f":{rp}", f"${{{camel}}}")
        
    return js_args, js_path

def get_default_js_value(field_type):
    t = str(field_type).lower()
    if 'string' in t:
        return '""'
    elif 'number' in t or 'int' in t or 'float' in t or 'double' in t:
        return '0'
    elif 'bool' in t:
        return 'false'
    elif 'array' in t or t.endswith('[]') or 'list' in t:
        return '[]'
    else:
        return 'null'

def generate_js_model_content(model_name, description, fields):
    ctor_params = []
    initializers = []
    jsdoc_params = []
    
    for f_name, f_type in fields.items():
        jsdoc_params.append(f" * @param {{{f_type}}} [params.{f_name}] - {f_name}")
        default_val = get_default_js_value(f_type)
        ctor_params.append(f"{f_name}")
        initializers.append(f"    this.{f_name} = {f_name} !== undefined ? {f_name} : {default_val};")
        
    jsdoc_str = "\n".join(jsdoc_params)
    initializers_str = "\n".join(initializers)
    
    content = f"""/**
 * {model_name} Model
 * {description}
 */
export class {model_name} {{
  /**
   * @param {{object}} [params]
{jsdoc_str}
   */
  constructor({{ {', '.join(ctor_params)} }} = {{}}) {{
{initializers_str}
  }}

  /**
   * Validates the model instance.
   * @returns {{boolean}} True if the instance is valid
   */
  validate() {{
    // Add custom validation logic here if required
    return true;
  }}
}}

export default {model_name};
"""
    return content

def generate_request_model_content(model_name, description, fields):
    ctor_params = []
    initializers = []
    jsdoc_params = []
    
    for f_name, f_type in fields.items():
        if f_name.lower() in ['id', 'created_at', 'createdat', 'updated_at', 'updatedat']:
            continue
        jsdoc_params.append(f" * @param {{{f_type}}} [params.{f_name}] - {f_name}")
        default_val = get_default_js_value(f_type)
        ctor_params.append(f"{f_name}")
        initializers.append(f"    this.{f_name} = {f_name} !== undefined ? {f_name} : {default_val};")
        
    jsdoc_str = "\n".join(jsdoc_params)
    initializers_str = "\n".join(initializers)
    
    content = f"""/**
 * Create{model_name}Request Model
 * Request payload for creating a {model_name}.
 */
export class Create{model_name}Request {{
  /**
   * @param {{object}} [params]
{jsdoc_str}
   */
  constructor({{ {', '.join(ctor_params)} }} = {{}}) {{
{initializers_str}
  }}

  /**
   * Validates the request payload.
   * @returns {{boolean}} True if the payload is valid
   */
  validate() {{
    // Add custom validation logic here if required
    return true;
  }}
}}

export default Create{model_name}Request;
"""
    return content

def generate_response_model_content(model_name, description, fields):
    initializers = []
    jsdoc_params = []
    
    for f_name, f_type in fields.items():
        jsdoc_params.append(f" * @property {{{f_type}}} {f_name} - {f_name}")
        default_val = get_default_js_value(f_type)
        initializers.append(f"    this.{f_name} = data.{f_name} !== undefined ? data.{f_name} : {default_val};")
        
    jsdoc_str = "\n".join(jsdoc_params)
    initializers_str = "\n".join(initializers)
    
    content = f"""/**
 * {model_name}Response Model
 * Response model representing the parsed response of a {model_name}.
 * 
{jsdoc_str}
 */
export class {model_name}Response {{
  /**
   * @param {{object}} [data] - Raw API response data
   */
  constructor(data = {{}}) {{
{initializers_str}
  }}
}}

export default {model_name}Response;
"""
    return content

def generate_frontend_client_files(blueprint: dict) -> dict:
    """
    Generate all files for the frontend networking and API service layers.
    Returns a dictionary mapping relative file paths to their file content string.
    """
    files = {}
    
    config_plan = blueprint.get("configuration_plan", {})
    auth_plan = blueprint.get("authentication_plan", {})
    service_plan = blueprint.get("service_plan", [])
    resource_groups = blueprint.get("resource_groups", [])
    crud_metadata = blueprint.get("crud_metadata", [])
    model_plan = blueprint.get("model_plan", [])
    
    api_name = blueprint.get("api_name", "API")
    framework = blueprint.get("framework", "React")
    
    # 1. Constants (src/api/constants/apiRoutes.js)
    routes_lines = []
    for group in resource_groups:
        for ep in group.get("endpoints", []):
            method = ep.get("method", "").upper()
            path = ep.get("path", "")
            
            clean_path = re.sub(r'\.\w+$', '', path)
            segments = [s for s in clean_path.split('/') if s and not s.startswith('{') and not s.startswith(':')]
            if segments and re.match(r'^v\d+$', segments[0]):
                segments.pop(0)
                
            if not segments:
                resource = "API"
            else:
                resource = "_".join(s.upper() for s in re.split(r'[-_]', segments[-1]))
                
            action = method
            if method == 'POST':
                action = 'CREATE'
            elif method == 'GET':
                if '{' in path or ':' in path:
                    action = 'GET'
                else:
                    action = 'LIST'
            elif method in ['PUT', 'PATCH']:
                action = 'UPDATE'
            elif method == 'DELETE':
                action = 'DELETE'
                
            const_name = f"{action}_{resource}"
            routes_lines.append(f"  {const_name}: '{path}',")
            
    unique_routes_lines = []
    seen = set()
    for line in routes_lines:
        if line not in seen:
            unique_routes_lines.append(line)
            seen.add(line)
            
    routes_str = "\n".join(unique_routes_lines)
    
    files["src/api/constants/apiRoutes.js"] = f"""/**
 * Reusable API Route constants and headers.
 */
export const API_ROUTES = {{
{routes_str}
}};

export const AUTH_KEYS = {{
  TOKEN_KEY: 'auth_token',
  REFRESH_TOKEN_KEY: 'refresh_token'
}};

export const HEADERS = {{
  CONTENT_TYPE_JSON: 'application/json',
  CONTENT_TYPE_FORM: 'application/x-www-form-urlencoded'
}};

export default {{
  API_ROUTES,
  AUTH_KEYS,
  HEADERS
}};
"""

    # 2. Centralized Config Module (src/api/config/apiConfig.js)
    base_url = config_plan.get("api_base_url", "https://api.example.com")
    timeout = config_plan.get("timeout_ms", 10000)
    default_headers = config_plan.get("default_headers", {"Content-Type": "application/json"})
    auth_strategy = auth_plan.get("strategy", "None")
    
    files["src/api/config/apiConfig.js"] = f"""/**
 * Centralized API configuration module.
 * Loads variables safely from environment variables (process.env) with fallbacks.
 */
export const apiConfig = {{
  baseURL: process.env.REACT_APP_API_BASE_URL || '{base_url}',
  timeout: parseInt(process.env.REACT_APP_API_TIMEOUT || '{timeout}', 10),
  authStrategy: process.env.REACT_APP_AUTH_STRATEGY || '{auth_strategy}',
  defaultHeaders: {json.dumps(default_headers, indent=2)},
  isDevelopment: process.env.NODE_ENV === 'development',
}};

export default apiConfig;
"""

    # 3. Environment Configuration template (.env.example)
    files[".env.example"] = f"""# Environment configuration template for Frontend Client
# Copy this file to .env and configure actual secrets or base URLs

# Base URL of the API gateway / backend proxy
REACT_APP_API_BASE_URL={base_url}

# Default request timeout in milliseconds
REACT_APP_API_TIMEOUT={timeout}

# Authentication Strategy (options: Bearer Token, JWT, API Key, Basic Auth, None)
REACT_APP_AUTH_STRATEGY={auth_strategy}

# Placeholders for API Keys / Credentials (DO NOT commit sensitive values!)
REACT_APP_API_KEY_DEV=your_dev_api_key_placeholder
REACT_APP_API_KEY_PROD=your_prod_api_key_placeholder
"""

    # 4. Error Utilities
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

    # 5. Centralized Axios Client (apiClient.js) consuming apiConfig
    login_ep = auth_plan.get("login_endpoint", "")
    logout_ep = auth_plan.get("logout_endpoint", "")
    refresh_ep = auth_plan.get("refresh_token_endpoint", "")
    storage_suggestion = auth_plan.get("token_storage_suggestion", "localStorage")
    auth_desc = auth_plan.get("description", "")
    
    refresh_interceptor = ""
    if refresh_ep:
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
import apiConfig from './config/apiConfig';
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
  baseURL: apiConfig.baseURL,
  timeout: apiConfig.timeout,
  headers: apiConfig.defaultHeaders
}});

// Request Interceptor: Inject Auth headers dynamically
apiClient.interceptors.request.use(
  (config) => {{
    const token = tokenStorage.getToken();
    if (token) {{
      if (apiConfig.authStrategy === 'Bearer Token' || apiConfig.authStrategy === 'JWT') {{
        config.headers['Authorization'] = `Bearer ${{token}}`;
      }} else if (apiConfig.authStrategy === 'API Key') {{
        config.headers['X-API-Key'] = token;
      }} else if (apiConfig.authStrategy === 'Basic Auth') {{
        config.headers['Authorization'] = `Basic ${{token}}`;
      }} else {{
        config.headers['Authorization'] = `Bearer ${{token}}`;
      }}
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
    
    # 6. Models Generation (Core, Request, Response models per entity)
    for model in model_plan:
        m_name = model.get("model_name", "Model")
        m_desc = model.get("description", "")
        m_fields = model.get("fields", {})
        
        # Core Model
        core_path = f"src/api/models/{m_name}.js"
        files[core_path] = generate_js_model_content(m_name, m_desc, m_fields)
        
        # Request Model
        req_path = f"src/api/models/Create{m_name}Request.js"
        files[req_path] = generate_request_model_content(m_name, m_desc, m_fields)
        
        # Response Model
        resp_path = f"src/api/models/{m_name}Response.js"
        files[resp_path] = generate_response_model_content(m_name, m_desc, m_fields)
        
    # 7. Services Generation
    endpoint_details = {}
    for group in resource_groups:
        for ep in group.get("endpoints", []):
            key = f"{ep.get('method', '').upper()} {ep.get('path', '')}"
            endpoint_details[key] = ep
            
    crud_patterns = {}
    for item in crud_metadata:
        key = f"{item.get('method', '').upper()} {item.get('path', '')}"
        crud_patterns[key] = item.get("pattern", "")
        
    def build_service_file(service):
        service_name = service.get("service_name", "ApiService")
        desc = service.get("description", f"Service layer for {service_name}")
        assigned_endpoints = service.get("endpoints", [])
        
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
            parts = ep_str.split(None, 1)
            if len(parts) != 2:
                continue
            method = parts[0].upper()
            path = parts[1]
            
            detail = endpoint_details.get(ep_str, {})
            ep_desc = detail.get("description", f"Executes {method} request to {path}")
            pattern = crud_patterns.get(ep_str)
            
            js_args, js_path = parse_path_params(path)
            method_name = get_js_method_name(method, path, service_name, pattern)
            
            js_args_str = ", ".join(js_args)
            axios_args = []
            
            if js_args:
                axios_args.append(f"`{js_path}`")
            else:
                axios_args.append(f"'{path}'")
                
            if method in ["POST", "PUT", "PATCH"]:
                if js_args_str:
                    js_args_str += ", data"
                else:
                    js_args_str = "data"
                axios_args.append("data")
            else:
                if js_args_str:
                    js_args_str += ", params = {}"
                else:
                    js_args_str = "params = {}"
                axios_args.append("{ params }")
                
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
        file_path = f"src/api/services/{svc_name}.js"
        
        content, m_count = build_service_file(svc)
        files[file_path] = content
        total_crud_methods += m_count
        generated_services_info.append({
            "service_name": svc_name,
            "methods_count": m_count,
            "description": svc.get("description", "")
        })
        
    # 8. README.md
    readme_services_list = []
    for s_info in generated_services_info:
        readme_services_list.append(f"- **{s_info['service_name']}**: {s_info['description']} ({s_info['methods_count']} methods)")
        
    usage_example = ""
    if generated_services_info:
        first_svc = generated_services_info[0]
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

Generated dynamically by Smart DevTool. Includes a centralized HTTP networking layer (Axios instance), authentication helpers, custom error normalization, configuration variables, routes, and models.

## Features
- **Centralized Client**: Centralized interceptors loading from custom configuration module.
- **Support Models**: Reusable entities, dedicated CreateRequest payloads, and Response payload classes.
- **Config & Constants**: Separated `.env.example`, constants routes, and central configuration files.

## Project Layout
```
.env.example             # Template for API base URL and timeouts
src/
└── api/
    ├── apiClient.js     # Axios configuration and token storage helpers
    ├── errorUtils.js    # Centralized error mapping and custom APIError class
    ├── config/
    │   └── apiConfig.js # Safely loads parameters from environment variables
    ├── constants/
    │   └── apiRoutes.js # Routes mapping keys and headers
    ├── models/          # Data Models (Entities, Requests, Responses)
    │   ├── Customer.js
    │   ├── CreateCustomerRequest.js
    │   └── CustomerResponse.js
    └── services/        # Service modules
        {"".join([f"├── {s['service_name']}.js\\n        " for s in generated_services_info])}
```

## Installation
Ensure you install Axios in your project root:
```bash
npm install axios
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
    files_map, _ = generate_frontend_client_files(blueprint)
    memory_zip = io.BytesIO()
    
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filepath, content in files_map.items():
            zipf.writestr(filepath, content)
            
    memory_zip.seek(0)
    return memory_zip.getvalue()
