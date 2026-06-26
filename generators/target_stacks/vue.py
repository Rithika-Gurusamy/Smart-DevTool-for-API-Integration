from generators.target_stacks.base import BaseTargetStackGenerator
from frontend_generator import generate_base_javascript_files, get_js_method_name, parse_path_params
import re

class VueGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        from generators.javascript import JavaScriptSDKGenerator
        return JavaScriptSDKGenerator(api_key=self.api_key).generate(api_metadata, use_case)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.rest_javascript import JavaScriptRESTGenerator
        return JavaScriptRESTGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        files, _ = generate_base_javascript_files(blueprint)
        
        service_plan = blueprint.get("service_plan", [])
        
        for svc in service_plan:
            service_name = svc.get("service_name", "ApiService")
            comp_base = service_name
            if comp_base.lower().endswith("service"):
                comp_base = comp_base[:-7]
            comp_name = f"use{comp_base[0].upper()}{comp_base[1:]}"
            
            # Generate composable code
            methods_import = []
            comp_methods = []
            
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
                    
                comp_methods.append(f"""  const execute{method_name[0].upper()}{method_name[1:]} = async ({js_args_str}) => {{
    loading.value = true;
    error.value = null;
    try {{
      const result = await {method_name}({js_args_str});
      return result;
    }} catch (err) {{
      error.value = err;
      throw err;
    }} finally {{
      loading.value = false;
    }}
  }};""")
            
            methods_import_str = ",\n  ".join(methods_import)
            comp_methods_str = "\n\n".join(comp_methods)
            returns_methods_str = ",\n    ".join([f"execute{m[0].upper()}{m[1:]}" for m in methods_import])
            
            comp_code = f"""import {{ ref }} from 'vue';
import {{
  {methods_import_str}
}} from '../api/services/{service_name}';

/**
 * Vue Composable wrapping {service_name} with reactive refs.
 */
export const {comp_name} = () => {{
  const loading = ref(false);
  const error = ref(null);

{comp_methods_str}

  return {{
    loading,
    error,
    {returns_methods_str}
  }};
}};

export default {comp_name};
"""
            files[f"src/composables/{comp_name}.js"] = comp_code
            
        return files

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "composables/": {"useCustomer.js": None},
                "api/": {
                    "config/": {"apiConfig.js": None},
                    "constants/": {"apiRoutes.js": None},
                    "models/": {"Customer.js": None},
                    "services/": {"customerService.js": None},
                    "apiClient.js": None,
                    "errorUtils.js": None
                }
            }
        }

    def get_framework_features(self) -> list:
        return ["Vue Composition API composables", "Reactive state management using ref()", "Modular API service injections"]

    def get_generated_assets(self) -> list:
        return ["useCustomer.js", "customerService.js", "apiClient.js", "README.md"]
