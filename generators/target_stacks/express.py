from generators.target_stacks.base import BaseTargetStackGenerator
import re

class ExpressGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "ExpressService"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            f"// Express Service and Router Integration for {api_name}",
            "const axios = require('axios');",
            "const express = require('express');",
            "",
            f"class {class_name} {{",
            "    constructor() {",
            "        this.apiKey = process.env.API_KEY;",
            "        this.baseUrl = process.env.API_BASE_URL || 'https://api.example.com';",
            "        ",
            "        const headers = { 'Content-Type': 'application/json' };",
            f"        if ('{auth_type}' === 'Bearer Token') {{",
            "            headers['Authorization'] = `Bearer ${this.apiKey}`;",
            "        } else {",
            "            headers['X-API-Key'] = this.apiKey;",
            "        }",
            "        ",
            "        this.client = axios.create({",
            "            baseURL: this.baseUrl,",
            "            headers: headers",
            "        });",
            "    }",
            ""
        ]
        
        for ep in endpoints:
            if ep.get("category") not in ["Primary", "Supporting"]:
                continue
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]
            
            # Clean method name
            method_name = path.strip("/").replace("/", "_").replace("-", "_").replace("{", "").replace("}", "")
            method_name = re.sub(r'v\d+_\b', '', method_name)
            if not method_name:
                method_name = "request"
            method_name = f"{method.lower()}{''.join([w.capitalize() for w in method_name.split('_')])}"
            
            lines.extend([
                f"    /**",
                f"     * {desc}",
                f"     */",
                f"    async {method_name}(data = {{}}) {{",
                f"        const response = await this.client.{method.lower()}('{path}', data);",
                "        return response.data;",
                "    }",
                ""
            ])
            
        lines.extend([
            "}",
            "",
            "// Express middleware mapping helper",
            f"const clientInstance = new {class_name}();",
            "const router = express.Router();",
            "",
            "// Middleware injecting client connection into express request context",
            "const injectClient = (req, res, next) => {",
            "    req.apiClient = clientInstance;",
            "    next();",
            "};",
            "",
            "router.use(injectClient);",
            "",
            "router.get('/health', async (req, res) => {",
            "    res.json({ status: 'connected', service: '" + class_name + "' });",
            "});",
            "",
            "module.exports = {",
            f"    {class_name},",
            "    apiRouter: router,",
            "    injectClient",
            "};"
        ])
        
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.target_stacks.generic_javascript import GenericJavaScriptGenerator
        return GenericJavaScriptGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Express target stack has no frontend client configuration."}

    def get_folder_structure(self) -> dict:
        return {
            "middleware/": {
                "injectClient.js": None
            },
            "controllers/": {
                "apiController.js": None
            },
            "services/": {
                "apiService.js": None
            },
            "config/": {"api.config.js": None}
        }

    def get_framework_features(self) -> list:
        return ["Express Router blueprints integration", "Express request lifecycle middleware injection", "Axios backend service client creation"]

    def get_generated_assets(self) -> list:
        return ["apiService.js", "injectClient.js", "apiController.js", "api.config.js", "README.md"]
