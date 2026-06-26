from generators.target_stacks.base import BaseTargetStackGenerator
from frontend_generator import parse_path_params
import re
import json

class AngularGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        # Reuses JavaScript wrapper generator but marked as TS compatible
        from generators.javascript import JavaScriptSDKGenerator
        return JavaScriptSDKGenerator(api_key=self.api_key).generate(api_metadata, use_case)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.rest_javascript import JavaScriptRESTGenerator
        return JavaScriptRESTGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        files = {}
        api_name = blueprint.get("api_name", "API")
        config_plan = blueprint.get("configuration_plan", {})
        auth_plan = blueprint.get("authentication_plan", {})
        service_plan = blueprint.get("service_plan", [])
        model_plan = blueprint.get("model_plan", [])
        
        base_url = config_plan.get("api_base_url", "https://api.example.com")
        timeout = config_plan.get("timeout_ms", 10000)
        auth_strategy = auth_plan.get("strategy", "None")
        
        # 1. Environment config
        files["src/environments/environment.ts"] = f"""export const environment = {{
  production: false,
  apiBaseUrl: '{base_url}',
  apiTimeout: {timeout},
  authStrategy: '{auth_strategy}',
}};
"""
        
        # 2. Angular HttpInterceptor
        files["src/interceptors/auth.interceptor.ts"] = f"""import {{ Injectable }} from '@angular/core';
import {{ HttpInterceptor, HttpRequest, HttpHandler, HttpEvent }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ environment }} from '../environments/environment';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {{
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {{
    const token = localStorage.getItem('auth_token');
    let authReq = req;

    if (token) {{
      if (environment.authStrategy === 'Bearer Token') {{
        authReq = req.clone({{
          setHeaders: {{ Authorization: `Bearer ${{token}}` }}
        }});
      }} else if (environment.authStrategy === 'API Key') {{
        authReq = req.clone({{
          setHeaders: {{ 'X-API-Key': token }}
        }});
      }}
    }}

    return next.handle(authReq);
  }}
}}
"""

        # 3. Models
        for model in model_plan:
            m_name = model.get("model_name", "Model")
            m_fields = model.get("fields", {})
            
            fields_lines = []
            for f_name, f_type in m_fields.items():
                t = "string"
                if "int" in f_type or "num" in f_type or "float" in f_type:
                    t = "number"
                elif "bool" in f_type:
                    t = "boolean"
                elif "array" in f_type or f_type.endswith("[]"):
                    t = "any[]"
                fields_lines.append(f"  {f_name}?: {t};")
                
            model_code = f"""export interface {m_name} {{
{chr(10).join(fields_lines)}
}}
"""
            files[f"src/models/{m_name.lower()}.model.ts"] = model_code

        # 4. Services
        for svc in service_plan:
            service_name = svc.get("service_name", "ApiService")
            angular_service_name = service_name[0].upper() + service_name[1:]
            if not angular_service_name.endswith("Service"):
                angular_service_name += "Service"
                
            service_methods = []
            assigned_endpoints = svc.get("endpoints", [])
            for ep_str in assigned_endpoints:
                parts = ep_str.split(None, 1)
                if len(parts) != 2:
                    continue
                method = parts[0].upper()
                path = parts[1]
                
                js_args, js_path = parse_path_params(path)
                # create camelCase method name
                method_name = path.strip("/").replace("/", "_").replace("-", "_").replace("{", "").replace("}", "")
                method_name = re.sub(r'v\d+_', '', method_name)
                if not method_name:
                    method_name = "request"
                method_name = f"{method.lower()}{''.join([w.capitalize() for w in method_name.split('_')])}"
                
                js_args_str = ", ".join([f"{a}: string" for a in js_args])
                
                if method in ["POST", "PUT", "PATCH"]:
                    js_args_str = (js_args_str + ", data: any").strip(", ")
                    service_methods.append(f"""  {method_name}({js_args_str}): Observable<any> {{
    return this.http.{method.lower()}(`${{this.baseUrl}}{js_path}`, data);
  }}""")
                else:
                    js_args_str = (js_args_str + ", params?: any").strip(", ")
                    service_methods.append(f"""  {method_name}({js_args_str}): Observable<any> {{
    return this.http.{method.lower()}(`${{this.baseUrl}}{js_path}`, {{ params }});
  }}""")
            
            service_code = f"""import {{ Injectable }} from '@angular/core';
import {{ HttpClient }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ environment }} from '../../environments/environment';

@Injectable({{
  providedIn: 'root'
}})
export class {angular_service_name} {{
  private baseUrl = environment.apiBaseUrl;

  constructor(private http: HttpClient) {{}}

{chr(10).join(service_methods)}
}}
"""
            files[f"src/services/{service_name.lower()}.service.ts"] = service_code
            
        # 5. README
        files["README.md"] = f"""# {api_name} Angular Integration Client

Generated dynamically by Smart DevTool. Follows Angular conventions using HttpClient services, RxJS Observables, and HttpInterceptors.

## Directory structure
- `src/environments/environment.ts`: API endpoint configurations
- `src/interceptors/auth.interceptor.ts`: Angular HTTP authentication header injection interceptor
- `src/models/*.ts`: Data interfaces
- `src/services/*.ts`: Injectable client services
"""

        return files

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "environments/": {"environment.ts": None},
                "interceptors/": {"auth.interceptor.ts": None},
                "models/": {"customer.model.ts": None},
                "services/": {"customer.service.ts": None}
            }
        }

    def get_framework_features(self) -> list:
        return ["Angular Injectable services", "RxJS Observables streams integration", "HttpInterceptor authentication pipelines"]

    def get_generated_assets(self) -> list:
        return ["customer.service.ts", "auth.interceptor.ts", "environment.ts", "README.md"]
