import json
import yaml
import os
import importlib
from dotenv import load_dotenv

# Try to import Gemini
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

class SpecParserError(Exception):
    pass

class BaseSpecParser:
    def __init__(self, raw_data: dict):
        self.raw_data = raw_data
        
    def detect_type_and_version(self) -> tuple:
        """
        Returns (spec_type, version_str)
        spec_type: 'openapi' | 'swagger' | 'unknown'
        """
        raise NotImplementedError

    def parse(self) -> dict:
        raise NotImplementedError

    def _resolve_reference(self, ref_path: str):
        if not ref_path.startswith("#/"):
            return None
        parts = ref_path.split("/")[1:]
        current = self.raw_data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

class OpenAPIParser(BaseSpecParser):
    def detect_type_and_version(self) -> tuple:
        return "openapi", str(self.raw_data.get("openapi", ""))
        
    def parse(self) -> dict:
        spec_type, spec_version = self.detect_type_and_version()
        info = self.raw_data.get("info", {})
        
        # 1. Metadata
        title = info.get("title", "Untitled API")
        description = info.get("description", "")
        version = info.get("version", "1.0.0")
        
        # Servers / Base URLs
        base_urls = []
        servers = self.raw_data.get("servers", [])
        if servers:
            for s in servers:
                url = s.get("url", "")
                if url:
                    base_urls.append(url)
        if not base_urls:
            base_urls.append("/")
            
        contact = info.get("contact", None)
        license_info = info.get("license", None)
        
        metadata = {
            "title": title,
            "description": description,
            "version": version,
            "base_urls": base_urls,
            "contact": contact,
            "license": license_info
        }
        
        # 2. Authentication
        authentication = []
        components = self.raw_data.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        for name, scheme_data in security_schemes.items():
            auth_type = scheme_data.get("type", "")
            auth_item = {
                "name": name,
                "type": auth_type,
                "scheme": scheme_data.get("scheme"),
                "in": scheme_data.get("in"),
                "description": scheme_data.get("description")
            }
            authentication.append(auth_item)
            
        # 3. Endpoints
        endpoints = []
        paths = self.raw_data.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
                
            # Path-level parameters
            path_params = path_item.get("parameters", [])
            
            for method, operation in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "options", "head", "patch", "trace"]:
                    continue
                    
                summary = operation.get("summary", "")
                desc = operation.get("description", "")
                tags = operation.get("tags", [])
                op_id = operation.get("operationId", "")
                
                # Parameters
                op_params = operation.get("parameters", [])
                all_params_raw = path_params + op_params
                
                parameters = []
                for p in all_params_raw:
                    if "$ref" in p:
                        ref_path = p["$ref"]
                        resolved_param = self._resolve_reference(ref_path)
                        if resolved_param:
                            p = resolved_param
                        else:
                            continue
                            
                    p_name = p.get("name", "")
                    p_in = p.get("in", "query")
                    p_req = p.get("required", False)
                    p_desc = p.get("description", "")
                    
                    # Schema type
                    p_schema = p.get("schema", {})
                    p_type = p_schema.get("type", "string")
                    if "$ref" in p_schema:
                        p_type = f"ref:{p_schema['$ref'].split('/')[-1]}"
                        
                    parameters.append({
                        "name": p_name,
                        "in": p_in,
                        "type": p_type,
                        "required": p_req,
                        "description": p_desc
                    })
                    
                # Request Body
                request_body_schema = None
                req_body = operation.get("requestBody", {})
                if "$ref" in req_body:
                    req_body = self._resolve_reference(req_body["$ref"]) or {}
                    
                if req_body:
                    content = req_body.get("content", {})
                    for media_type, media_item in content.items():
                        schema = media_item.get("schema", {})
                        request_body_schema = {
                            "media_type": media_type,
                            "schema": schema
                        }
                        break # Grab first format
                        
                # Responses
                responses = {}
                op_responses = operation.get("responses", {})
                for status_code, resp in op_responses.items():
                    if "$ref" in resp:
                        resp = self._resolve_reference(resp["$ref"]) or {}
                    resp_desc = resp.get("description", "")
                    
                    schema_ref = None
                    content = resp.get("content", {})
                    for media_type, media_item in content.items():
                        schema = media_item.get("schema", {})
                        if "$ref" in schema:
                            schema_ref = schema["$ref"]
                        elif schema.get("type"):
                            schema_ref = schema["type"]
                        break
                        
                    responses[status_code] = {
                        "description": resp_desc,
                        "schema_ref": schema_ref
                    }
                    
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": summary,
                    "description": desc,
                    "tags": tags,
                    "operation_id": op_id,
                    "parameters": parameters,
                    "request_body_schema": request_body_schema,
                    "responses": responses
                })
                
        return {
            "spec_type": spec_type,
            "spec_version": spec_version,
            "metadata": metadata,
            "endpoints": endpoints,
            "authentication": authentication
        }

class SwaggerParser(BaseSpecParser):
    def detect_type_and_version(self) -> tuple:
        return "swagger", str(self.raw_data.get("swagger", ""))
        
    def parse(self) -> dict:
        spec_type, spec_version = self.detect_type_and_version()
        info = self.raw_data.get("info", {})
        
        # 1. Metadata
        title = info.get("title", "Untitled API")
        description = info.get("description", "")
        version = info.get("version", "1.0.0")
        
        # Base URL construction in Swagger 2.0
        host = self.raw_data.get("host", "")
        base_path = self.raw_data.get("basePath", "")
        schemes = self.raw_data.get("schemes", ["http"])
        
        base_urls = []
        if host:
            for scheme in schemes:
                base_urls.append(f"{scheme}://{host}{base_path}")
        else:
            if base_path:
                base_urls.append(base_path)
            else:
                base_urls.append("/")
                
        contact = info.get("contact", None)
        license_info = info.get("license", None)
        
        metadata = {
            "title": title,
            "description": description,
            "version": version,
            "base_urls": base_urls,
            "contact": contact,
            "license": license_info
        }
        
        # 2. Authentication
        authentication = []
        security_definitions = self.raw_data.get("securityDefinitions", {})
        for name, scheme_data in security_definitions.items():
            auth_type = scheme_data.get("type", "")
            if auth_type == "basic":
                normal_type = "basic"
            elif auth_type == "apiKey":
                normal_type = "apiKey"
            elif auth_type == "oauth2":
                normal_type = "oauth2"
            else:
                normal_type = auth_type
                
            auth_item = {
                "name": name,
                "type": normal_type,
                "in": scheme_data.get("in"),
                "description": scheme_data.get("description"),
                "flow": scheme_data.get("flow"),
                "authorizationUrl": scheme_data.get("authorizationUrl"),
                "tokenUrl": scheme_data.get("tokenUrl"),
                "scopes": scheme_data.get("scopes")
            }
            authentication.append(auth_item)
            
        # 3. Endpoints
        endpoints = []
        paths = self.raw_data.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
                
            # Path level parameters
            path_params = path_item.get("parameters", [])
            
            for method, operation in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "options", "head", "patch"]:
                    continue
                    
                summary = operation.get("summary", "")
                desc = operation.get("description", "")
                tags = operation.get("tags", [])
                op_id = operation.get("operationId", "")
                
                # Parameters
                op_params = operation.get("parameters", [])
                all_params_raw = path_params + op_params
                
                parameters = []
                request_body_schema = None
                
                for p in all_params_raw:
                    if "$ref" in p:
                        ref_path = p["$ref"]
                        resolved_param = self._resolve_reference(ref_path)
                        if resolved_param:
                            p = resolved_param
                        else:
                            continue
                            
                    p_name = p.get("name", "")
                    p_in = p.get("in", "query")
                    p_req = p.get("required", False)
                    p_desc = p.get("description", "")
                    
                    if p_in == "body":
                        schema = p.get("schema", {})
                        request_body_schema = {
                            "media_type": "application/json",
                            "schema": schema
                        }
                        p_type = schema.get("type", "object")
                        if "$ref" in schema:
                            p_type = f"ref:{schema['$ref'].split('/')[-1]}"
                    else:
                        p_type = p.get("type", "string")
                        
                    parameters.append({
                        "name": p_name,
                        "in": p_in,
                        "type": p_type,
                        "required": p_req,
                        "description": p_desc
                    })
                    
                # Responses
                responses = {}
                op_responses = operation.get("responses", {})
                for status_code, resp in op_responses.items():
                    if "$ref" in resp:
                        resp = self._resolve_reference(resp["$ref"]) or {}
                    resp_desc = resp.get("description", "")
                    
                    schema_ref = None
                    schema = resp.get("schema", {})
                    if schema:
                        if "$ref" in schema:
                            schema_ref = schema["$ref"]
                        elif schema.get("type"):
                            schema_ref = schema["type"]
                            
                    responses[status_code] = {
                        "description": resp_desc,
                        "schema_ref": schema_ref
                    }
                    
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": summary,
                    "description": desc,
                    "tags": tags,
                    "operation_id": op_id,
                    "parameters": parameters,
                    "request_body_schema": request_body_schema,
                    "responses": responses
                })
                
        return {
            "spec_type": spec_type,
            "spec_version": spec_version,
            "metadata": metadata,
            "endpoints": endpoints,
            "authentication": authentication
        }

class PostmanCollectionParser(BaseSpecParser):
    def detect_type_and_version(self) -> tuple:
        info_obj = self.raw_data.get("info", {})
        schema_url = info_obj.get("schema", "")
        if "postman" in schema_url.lower() or "item" in self.raw_data:
            return "postman", "2.1.0"
        return "unknown", ""
        
    def parse(self) -> dict:
        info = self.raw_data.get("info", {})
        title = info.get("name", "Postman Collection")
        description = info.get("description", "")
        version = "1.0.0"
        
        metadata = {
            "title": title,
            "description": description,
            "version": version,
            "base_urls": ["/"]
        }
        
        endpoints = []
        authentication = []
        
        # Traverse items recursively
        self._parse_items(self.raw_data.get("item", []), endpoints)
        
        # Extract basic auth if defined at collection level
        auth_data = self.raw_data.get("auth")
        if isinstance(auth_data, dict):
            auth_type = auth_data.get("type", "")
            authentication.append({
                "name": "CollectionAuth",
                "type": auth_type,
                "in": "header"
            })
            
        return {
            "spec_type": "postman",
            "spec_version": "2.1.0",
            "metadata": metadata,
            "endpoints": endpoints,
            "authentication": authentication
        }
        
    def _parse_items(self, items: list, endpoints: list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if "item" in item:
                # Folder: recurse
                self._parse_items(item["item"], endpoints)
            elif "request" in item:
                req = item["request"]
                name = item.get("name", "")
                desc = req.get("description", "")
                method = req.get("method", "GET").upper()
                
                # Parse URL
                url_data = req.get("url", "")
                path = "/"
                query_params = []
                
                if isinstance(url_data, dict):
                    # Path list to string path
                    path_parts = url_data.get("path", [])
                    if isinstance(path_parts, list):
                        path = "/" + "/".join([str(p) for p in path_parts])
                    elif isinstance(path_parts, str):
                        path = path_parts
                        
                    # Query params
                    for q in url_data.get("query", []):
                        if isinstance(q, dict):
                            query_params.append({
                                "name": q.get("key", ""),
                                "in": "query",
                                "type": "string",
                                "required": not q.get("disabled", False),
                                "description": q.get("description", "")
                            })
                elif isinstance(url_data, str):
                    path = url_data
                    
                # Headers
                headers = []
                for h in req.get("header", []):
                    if isinstance(h, dict):
                        headers.append({
                            "name": h.get("key", ""),
                            "in": "header",
                            "type": "string",
                            "required": not h.get("disabled", False),
                            "description": h.get("description", "")
                        })
                        
                parameters = query_params + headers
                
                # Request Body
                request_body_schema = None
                body_data = req.get("body", {})
                if isinstance(body_data, dict) and body_data.get("mode") == "raw":
                    raw_body = body_data.get("raw", "")
                    try:
                        # Try to parse raw body as json to extract schema structure
                        parsed_json = json.loads(raw_body)
                        schema = self._json_to_schema(parsed_json)
                        request_body_schema = {
                            "media_type": "application/json",
                            "schema": schema
                        }
                    except Exception:
                        request_body_schema = {
                            "media_type": "application/json",
                            "schema": {"type": "string", "example": raw_body}
                        }
                        
                endpoints.append({
                    "path": path,
                    "method": method,
                    "summary": name,
                    "description": desc,
                    "tags": [],
                    "operation_id": "",
                    "parameters": parameters,
                    "request_body_schema": request_body_schema,
                    "responses": {}
                })
                
    def _json_to_schema(self, data) -> dict:
        if isinstance(data, dict):
            properties = {}
            required = []
            for k, v in data.items():
                properties[k] = self._json_to_schema(v)
                required.append(k)
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
        elif isinstance(data, list):
            item_schema = {"type": "string"}
            if data:
                item_schema = self._json_to_schema(data[0])
            return {
                "type": "array",
                "items": item_schema
            }
        elif isinstance(data, bool):
            return {"type": "boolean"}
        elif isinstance(data, (int, float)):
            return {"type": "number"}
        return {"type": "string"}

class LLMSpecParser:
    def __init__(self, raw_content: str, api_key: str = None):
        self.raw_content = raw_content
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
    def parse(self) -> dict:
        if not self.api_key or not HAS_GEMINI:
            return self._fallback_empty()
            
        prompt = f"""
You are an expert API Architect and Specification Parser. Your task is to analyze the following unstructured content (which could be raw API documentation, markdown text, code snippets, example HTTP requests and responses, or sample JSON payloads) and convert it into a normalized API specification JSON object.

Unstructured Content:
---
{self.raw_content}
---

You MUST parse this content and extract all API endpoints, parameters, schemas, and authentication methods. 
Return your response as a valid JSON object matching the following structure:
{{
    "spec_type": "normalized_raw_text",
    "spec_version": "1.0.0",
    "metadata": {{
        "title": "API Title (extract from content or generate a suitable name)",
        "description": "Brief description of the API",
        "version": "1.0.0",
        "base_urls": ["Extract base URL or default to ['/']"]
    }},
    "endpoints": [
        {{
            "path": "/endpoint/path",
            "method": "GET or POST or PUT or DELETE",
            "summary": "Short endpoint summary",
            "description": "Detailed description of the endpoint",
            "tags": ["Resource tag"],
            "operation_id": "createSomething",
            "parameters": [
                {{
                    "name": "param_name",
                    "in": "query or path or header",
                    "type": "string or integer or number or boolean",
                    "required": true,
                    "description": "Parameter explanation"
                }}
            ],
            "request_body_schema": {{
                "media_type": "application/json",
                "schema": {{
                    "type": "object",
                    "properties": {{
                        "field_name": {{"type": "string"}}
                    }},
                    "required": ["field_name"]
                }}
            }},
            "responses": {{
                "200": {{
                    "description": "Success response",
                    "schema_ref": "object"
                }}
            }}
        }}
    ],
    "authentication": [
        {{
            "name": "AuthSchemeName",
            "type": "apiKey or http or oauth2",
            "in": "header or query"
        }}
    ]
}}

Return ONLY the raw JSON object. Do not include markdown wraps (like ```json), HTML tags, or any introductory text. Just the JSON object.
"""
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean markdown wraps
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            parsed = json.loads(text)
            return parsed
        except Exception as e:
            print(f"LLM specification parsing failed: {str(e)}")
            return self._fallback_empty()
            
    def _fallback_empty(self) -> dict:
        return {
            "spec_type": "unparsed_text",
            "spec_version": "1.0.0",
            "metadata": {
                "title": "Unparsed Content",
                "description": "Could not extract specification structurally.",
                "version": "1.0.0",
                "base_urls": ["/"]
            },
            "endpoints": [],
            "authentication": []
        }

def detect_and_parse_spec(file_content: str) -> dict:
    """
    Parses file content (JSON or YAML) and automatically detects and normalizes
    OpenAPI 3.x, Swagger 2.0, Postman collections, or uses LLM parsing for raw text.
    Returns the normalized spec dictionary.
    """
    # 1. First, try to parse as JSON or YAML
    data = None
    try:
        data = json.loads(file_content)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(file_content)
        except Exception:
            pass # Keep data = None
            
    # 2. If it is a dictionary, check for native structures
    if isinstance(data, dict):
        if "openapi" in data:
            version = str(data["openapi"])
            if version.startswith("3."):
                parser = OpenAPIParser(data)
                return parser.parse()
            else:
                raise SpecParserError(f"Unsupported OpenAPI version: {version}. Only OpenAPI 3.x is supported.")
                
        elif "swagger" in data:
            version = str(data["swagger"])
            if version == "2.0":
                parser = SwaggerParser(data)
                return parser.parse()
            else:
                raise SpecParserError(f"Unsupported Swagger version: {version}. Only Swagger 2.0 is supported.")
                
        # 3. Check for Postman Collection signature
        info_obj = data.get("info", {})
        schema_url = info_obj.get("schema", "") if isinstance(info_obj, dict) else ""
        if "postman" in schema_url.lower() or "item" in data:
            parser = PostmanCollectionParser(data)
            return parser.parse()
            
    # 4. If it's not a dictionary or native parsing failed, check if we can parse it using the LLM
    if api_key and HAS_GEMINI:
        parser = LLMSpecParser(file_content, api_key=api_key)
        parsed = parser.parse()
        if parsed.get("endpoints"):
            return parsed
            
    # 5. Offline fallback or error
    if isinstance(data, dict):
        raise SpecParserError("Could not detect any OpenAPI, Swagger, or Postman specification signature in the file.")
    else:
        raise SpecParserError("File is not valid JSON/YAML spec, and Gemini API is not configured for raw text parsing.")
