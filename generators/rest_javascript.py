import re
from generators.rest_base import BaseRESTGenerator

class JavaScriptRESTGenerator(BaseRESTGenerator):
    """
    Generates standalone, copy-pasteable REST integration scripts in JavaScript using `axios`.
    """
    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        endpoints = self.filter_endpoints(api_metadata.get("endpoints", []))
        if not endpoints:
            endpoints = api_metadata.get("endpoints", [])
            
        api_name = api_metadata.get("api_name", "API")
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        auth_desc = auth_info.get("description", "")

        lines = [
            f"// Standalone JavaScript REST Integration Examples for {api_name}",
            f"// Auth Method: {auth_type} ({auth_desc})",
            "const axios = require('axios');",
            "",
            "// General Configuration",
            "const BASE_URL = 'https://api.example.com';",
        ]

        if auth_type == "Bearer Token":
            lines.append("const API_TOKEN = process.env.API_TOKEN || 'YOUR_BEARER_TOKEN';")
        else:
            lines.append("const API_KEY = process.env.API_KEY || 'YOUR_API_KEY';")

        lines.append("")
        lines.append("async function runExamples() {")

        for i, ep in enumerate(endpoints, 1):
            method = ep["method"].lower()
            path = ep["path"]
            desc = ep["description"]

            lines.extend([
                "    // " + "=" * 72,
                f"    // {i}. {desc} ({method.upper()} {path})",
                "    // " + "=" * 72,
                f"    console.log('\\n--- Running Example {i}: {desc} ---');"
            ])

            path_vars = re.findall(r'\{(\w+)\}', path)
            for var in path_vars:
                lines.append(f"    const {var} = 'sample_{var}';")

            js_path = path
            for var in path_vars:
                js_path = js_path.replace(f"{{{var}}}", f"${{{var}}}")

            lines.append(f"    const url = `${{BASE_URL}}{js_path}`;")

            # Headers
            lines.append("    const headers = {")
            lines.append("        'Content-Type': 'application/json',")
            if auth_type == "Bearer Token":
                lines.append("        'Authorization': `Bearer ${API_TOKEN}`")
            else:
                lines.append("        'X-API-Key': API_KEY")
            lines.append("    };")

            # Call
            if method in ["post", "put", "patch"]:
                lines.extend([
                    "    const payload = {",
                    "        example_key: 'example_value'",
                    "    };",
                    "    try {",
                    f"        const response = await axios.{method}(url, payload, {{ headers }});",
                    "        console.log('Success:', response.status, response.data);",
                    "    } catch (error) {",
                    "        console.error('Failed:', error.response ? error.response.status : error.message);",
                    "    }"
                ])
            else:
                lines.extend([
                    "    const params = {",
                    "        limit: 10",
                    "    };",
                    "    try {",
                    f"        const response = await axios.{method}(url, {{ headers, params }});",
                    "        console.log('Success:', response.status, response.data);",
                    "    } catch (error) {",
                    "        console.error('Failed:', error.response ? error.response.status : error.message);",
                    "    }"
                ])
            lines.append("")

        lines.append("}")
        lines.append("")
        lines.append("runExamples();")

        return "\n".join(lines)
