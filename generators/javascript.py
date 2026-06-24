import re
from generators.base import BaseSDKGenerator

class JavaScriptSDKGenerator(BaseSDKGenerator):
    """
    JavaScript SDK Generator.
    Future-ready scaffolding class for JavaScript/TypeScript client SDK generation.
    """
    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key

    def generate(self, api_metadata: dict, use_case: str) -> str:
        endpoints = self.filter_endpoints(api_metadata.get("endpoints", []))
        if not endpoints:
            endpoints = api_metadata.get("endpoints", [])
            
        api_name = api_metadata.get("api_name", "API")
        class_name = self.clean_class_name(api_name)
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")

        lines = [
            f"// JavaScript SDK Client for {class_name}",
            "// Requires 'axios' npm library",
            "const axios = require('axios');",
            "",
            "class APIClientError extends Error {",
            "    constructor(message) {",
            "        super(message);",
            "        this.name = 'APIClientError';",
            "    }",
            "}",
            "",
            "class AuthenticationError extends APIClientError {}",
            "class ValidationError extends APIClientError {}",
            "class RateLimitError extends APIClientError {}",
            "class ServerError extends APIClientError {}",
            "",
            f"class {class_name} {{",
        ]

        # Constructor
        if auth_type == "Bearer Token":
            lines.extend([
                "    constructor(token, baseUrl = 'https://api.example.com') {",
                "        this.token = token || process.env.API_TOKEN;",
                "        if (!this.token) {",
                "            throw new AuthenticationError('Authentication token must be provided.');",
                "        }",
                "        this.baseUrl = baseUrl.replace(/\\/$/, '');",
                "        this.client = axios.create({",
                "            baseURL: this.baseUrl,",
                "            headers: {",
                "                'Authorization': `Bearer ${this.token}`,",
                "                'Content-Type': 'application/json'",
                "            }",
                "        });",
                "    }"
            ])
        else:
            lines.extend([
                "    constructor(apiKey, baseUrl = 'https://api.example.com') {",
                "        this.apiKey = apiKey || process.env.API_KEY;",
                "        if (!this.apiKey) {",
                "            throw new AuthenticationError('API Key must be provided.');",
                "        }",
                "        this.baseUrl = baseUrl.replace(/\\/$/, '');",
                "        this.client = axios.create({",
                "            baseURL: this.baseUrl,",
                "            headers: {",
                "                'X-API-Key': this.apiKey,",
                "                'Content-Type': 'application/json'",
                "            }",
                "        });",
                "    }"
            ])

        lines.append("")

        # Private request helper
        lines.extend([
            "    async _request(config) {",
            "        try {",
            "            const response = await this.client(config);",
            "            return response.data;",
            "        } catch (error) {",
            "            if (error.response) {",
            "                const status = error.response.status;",
            "                const data = error.response.data;",
            "                if (status === 401 || status === 403) {",
            "                    throw new AuthenticationError(`Auth failed: ${JSON.stringify(data)}`);",
            "                } else if (status === 429) {",
            "                    throw new RateLimitError('Rate limit exceeded.');",
            "                } else if (status >= 400 && status < 500) {",
            "                    throw new ValidationError(`Validation failed: ${JSON.stringify(data)}`);",
            "                } else {",
            "                    throw new ServerError(`Server error: ${status}`);",
            "                }",
            "            }",
            "            throw new APIClientError(`Network failed: ${error.message}`);",
            "        }",
            "    }",
            ""
        ])

        # Methods
        for ep in endpoints:
            method = ep["method"].lower()
            path = ep["path"]
            desc = ep["description"]
            
            method_name = self.clean_method_name(method, path, desc)
            # convert snake_case to camelCase
            parts = method_name.split("_")
            camel_method = parts[0] + "".join(p.title() for p in parts[1:])
            
            path_vars = re.findall(r'\{(\w+)\}', path)
            
            params_list = []
            for v in path_vars:
                params_list.append(v)
            if method in ["post", "put", "patch"]:
                params_list.append("data = {}")
            else:
                params_list.append("params = {}")
                
            lines.extend([
                "    /**",
                f"     * {desc}",
                "     */",
                f"    async {camel_method}({', '.join(params_list)}) {{"
            ])
            
            # URL Interpolation
            js_path = path
            for v in path_vars:
                js_path = js_path.replace(f"{{{v}}}", f"${{{v}}}")
                
            lines.append(f"        const path = `{js_path}`;")
            
            if method in ["post", "put", "patch"]:
                lines.append(f"        return this._request({{ method: '{method}', url: path, data }});")
            else:
                lines.append(f"        return this._request({{ method: '{method}', url: path, params }});")
                
            lines.extend([
                "    }",
                ""
            ])

        lines.extend([
            "}",
            "",
            f"module.exports = {class_name};"
        ])

        return "\n".join(lines)
