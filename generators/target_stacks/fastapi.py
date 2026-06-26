from generators.target_stacks.base import BaseTargetStackGenerator
import re

class FastAPIGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "FastClient"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            f"# FastAPI Async API Client for {api_name}",
            "import os",
            "import httpx",
            "from fastapi import Depends",
            "from typing import Optional",
            "",
            f"class {class_name}:",
            "    def __init__(self, api_key: str = None, base_url: str = 'https://api.example.com'):",
            "        self.api_key = api_key or os.getenv('API_KEY')",
            "        self.base_url = base_url.rstrip('/')",
            "        if not self.api_key:",
            "            raise ValueError('An API key must be configured.')",
            "        ",
            "        headers = {'Content-Type': 'application/json'}",
            "        if '" + auth_type + "' == 'Bearer Token':",
            "            headers['Authorization'] = f'Bearer {self.api_key}'",
            "        else:",
            "            headers['X-API-Key'] = self.api_key",
            "            ",
            "        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers)",
            "",
            "    async def close(self):",
            "        await self.client.aclose()",
            ""
        ]
        
        # Add endpoints
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
                f"    async def {method_name}(self, data: Optional[dict] = None) -> dict:",
                f"        \"\"\"",
                f"        {desc}",
                f"        \"\"\"",
                f"        response = await self.client.request('{method}', '{path}', json=data)" if method in ["POST", "PUT", "PATCH"] else f"        response = await self.client.request('{method}', '{path}', params=data)",
                "        response.raise_for_status()",
                "        return response.json()",
                ""
            ])
            
        # Add dependency injector function
        lines.extend([
            f"# Dependency provider for FastAPI routes",
            f"async def get_{api_name.lower().replace(' ', '_')}_client() -> {class_name}:",
            f"    client = {class_name}()",
            "    try:",
            "        yield client",
            "    finally:",
            "        await client.close()",
            ""
        ])
        
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.target_stacks.generic_python import GenericPythonGenerator
        return GenericPythonGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "FastAPI target stack has no frontend client configuration."}

    def get_folder_structure(self) -> dict:
        return {
            "clients/": {
                "__init__.py": None,
                "fast_client.py": None
            },
            "dependencies/": {
                "client.py": None
            },
            "config/": {"settings.py": None}
        }

    def get_framework_features(self) -> list:
        return ["Asynchronous HTTPX client connection", "FastAPI path dependencies injection", "Pydantic request payload validation bindings"]

    def get_generated_assets(self) -> list:
        return ["fast_client.py", "client.py", "settings.py", "README.md"]
