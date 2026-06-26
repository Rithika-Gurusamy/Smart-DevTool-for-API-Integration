from generators.target_stacks.base import BaseTargetStackGenerator
from frontend_generator import generate_base_javascript_files, get_js_method_name, parse_path_params
import re

class ReactGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        from generators.javascript import JavaScriptSDKGenerator
        return JavaScriptSDKGenerator(api_key=self.api_key).generate(api_metadata, use_case)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.rest_javascript import JavaScriptRESTGenerator
        return JavaScriptRESTGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        files, _ = generate_base_javascript_files(blueprint)
        
        # Add React hooks for each service in the service plan
        service_plan = blueprint.get("service_plan", [])
        
        for svc in service_plan:
            service_name = svc.get("service_name", "ApiService")
            hook_base = service_name
            if hook_base.lower().endswith("service"):
                hook_base = hook_base[:-7]
            hook_name = f"use{hook_base[0].upper()}{hook_base[1:]}"
            
            # Generate hook code
            methods_import = []
            hook_methods = []
            
            assigned_endpoints = svc.get("endpoints", [])
            for ep_str in assigned_endpoints:
                parts = ep_str.split(None, 1)
                if len(parts) != 2:
                    continue
                method = parts[0].upper()
                path = parts[1]
                
                js_args, js_path = parse_path_params(path)
                method_name = get_js_method_name(method, path, service_name)
                methods_import.append(method_name)
                
                js_args_str = ", ".join(js_args)
                if method in ["POST", "PUT", "PATCH"]:
                    js_args_str = (js_args_str + ", data").strip(", ")
                else:
                    js_args_str = (js_args_str + ", params").strip(", ")
                    
                hook_methods.append(f"""  const execute{method_name[0].upper()}{method_name[1:]} = async ({js_args_str}) => {{
    setLoading(true);
    setError(null);
    try {{
      const result = await {method_name}({js_args_str});
      return result;
    }} catch (err) {{
      setError(err);
      throw err;
    }} finally {{
      setLoading(false);
    }}
  }};""")
            
            # Use format lists since newline cannot be easily represented in f-strings inside lists
            methods_import_str = ",\n  ".join(methods_import)
            hook_methods_str = "\n\n".join(hook_methods)
            returns_methods_str = ",\n    ".join([f"execute{m[0].upper()}{m[1:]}" for m in methods_import])
            
            hook_code = f"""import {{ useState }} from 'react';
import {{
  {methods_import_str}
}} from '../services/{service_name}';

/**
 * React hook wrapping {service_name} with loading and error states.
 */
export const {hook_name} = () => {{
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

{hook_methods_str}

  return {{
    loading,
    error,
    {returns_methods_str}
  }};
}};

export default {hook_name};
"""
            files[f"src/api/hooks/{hook_name}.js"] = hook_code
            
        return files

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "api/": {
                    "config/": {"apiConfig.js": None},
                    "constants/": {"apiRoutes.js": None},
                    "models/": {"Customer.js": None},
                    "services/": {"customerService.js": None},
                    "hooks/": {"useCustomer.js": None},
                    "apiClient.js": None,
                    "errorUtils.js": None
                }
            }
        }

    def get_framework_features(self) -> list:
        return ["React Hooks with loading/error state management", "Axios central integration client", "Separate request/response models JSDoc"]

    def get_generated_assets(self) -> list:
        return ["useCustomer.js", "apiClient.js", "customerService.js", "README.md"]
