from generators.target_stacks.base import BaseTargetStackGenerator
import re

class FlaskGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "FlaskClient"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            f"# Flask Extension Client wrapper for {api_name}",
            "import os",
            "import requests",
            "from flask import current_app, g",
            "",
            f"class {class_name}(object):",
            "    def __init__(self, app=None):",
            "        self.app = app",
            "        if app is not None:",
            "            self.init_app(app)",
            "",
            "    def init_app(self, app):",
            f"        app.config.setdefault('{api_name.upper()}_API_KEY', os.getenv('API_KEY'))",
            f"        app.config.setdefault('{api_name.upper()}_BASE_URL', 'https://api.example.com')",
            "",
            "    @property",
            "    def session(self):",
            "        if 'api_client_session' not in g:",
            f"            api_key = current_app.config.get('{api_name.upper()}_API_KEY')",
            f"            base_url = current_app.config.get('{api_name.upper()}_BASE_URL')",
            "            if not api_key:",
            f"                raise ValueError('Configuration {api_name.upper()}_API_KEY is missing.')",
            "            ",
            "            session = requests.Session()",
            "            session.headers.update({'Content-Type': 'application/json'})",
            "            "
        ]
        
        if auth_type == "Bearer Token":
            lines.append("            session.headers.update({'Authorization': f'Bearer {api_key}'})")
        else:
            lines.append(f"            session.headers.update({{'X-API-Key': api_key}})")
            
        lines.extend([
            "            g.api_client_session = session",
            "        return g.api_client_session",
            "",
            "    def _get_url(self, path):",
            f"        base_url = current_app.config.get('{api_name.upper()}_BASE_URL').rstrip('/')",
            "        return f\"{base_url}{path}\"",
            ""
        ])
        
        for ep in endpoints:
            if ep.get("category") not in ["Primary", "Supporting"]:
                continue
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]
            
            # Clean method name
            method_name = path.strip("/").replace("/", "_").replace("-", "_").replace("{", "").replace("}", "")
            method_name = re.sub(r'v\d+_', '', method_name)
            if not method_name:
                method_name = "request"
            method_name = f"{method.lower()}_{method_name}"
            
            lines.extend([
                f"    def {method_name}(self, data=None):",
                f"        \"\"\"",
                f"        {desc}",
                f"        \"\"\"",
                f"        url = self._get_url('{path}')",
                f"        response = self.session.{method.lower()}(url, json=data)" if method in ["POST", "PUT", "PATCH"] else f"        response = self.session.{method.lower()}(url, params=data)",
                "        response.raise_for_status()",
                "        return response.json()",
                ""
            ])
            
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        # Reuses generic python generator for standalone REST, but outputs it
        from generators.target_stacks.generic_python import GenericPythonGenerator
        return GenericPythonGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Flask backend target stack has no frontend client configuration."}

    def get_folder_structure(self) -> dict:
        return {
            "client/": {
                "__init__.py": None,
                "flask_client.py": None,
                "config.py": None
            },
            "templates/": {},
            "routes.py": None
        }

    def get_framework_features(self) -> list:
        return ["Flask Application Context binding", "Flask App configuration bindings", "Custom blueprints routing"]

    def get_generated_assets(self) -> list:
        return ["flask_client.py", "config.py", "routes.py", "README.md"]
