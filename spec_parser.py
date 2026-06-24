import json
import yaml

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

def detect_and_parse_spec(file_content: str) -> dict:
    """
    Parses file content (JSON or YAML) and automatically detects and normalizes
    OpenAPI 3.x or Swagger 2.0 specifications.
    Returns the normalized spec dictionary.
    """
    try:
        data = json.loads(file_content)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(file_content)
        except Exception as e:
            raise SpecParserError(f"File is not valid JSON or YAML: {str(e)}")
            
    if not isinstance(data, dict):
        raise SpecParserError("Parsed specification is not a dictionary/object.")
        
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
            
    else:
        raise SpecParserError("Could not detect any OpenAPI or Swagger specification signature in the file.")
