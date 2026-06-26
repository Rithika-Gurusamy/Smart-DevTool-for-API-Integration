import os
import re
import json
import importlib
from generators.rest_base import BaseRESTGenerator

try:
    genai = importlib.import_module("google.generativeai")
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

class JavaRESTGenerator(BaseRESTGenerator):
    """
    Generates standalone, copy-pasteable REST integration scripts in Java using Java 11+ HttpClient.
    """
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        endpoints = self.filter_endpoints(api_metadata.get("endpoints", []))
        if not endpoints:
            endpoints = api_metadata.get("endpoints", [])
            
        api_name = api_metadata.get("api_name", "API")
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        auth_desc = auth_info.get("description", "")

        # Try to generate using LLM if available
        if self.api_key and HAS_GEMINI:
            endpoints_str = "\n".join([
                f"- {ep['method']} {ep['path']} : {ep['description']} (Category: {ep.get('category', 'Primary')})" 
                for ep in endpoints
            ])
            
            prompt = f"""
You are a Principal Software Engineer. Generate standalone, production-ready REST integration examples in Java using the Java 11+ `java.net.http.HttpClient`.

API Name: {api_name}
Use Case: {use_case}
Authentication Method: {auth_type} ({auth_desc})

Endpoints to implement (ONLY generate standalone HttpClient request examples for these Primary/Supporting endpoints):
{endpoints_str}

Follow these strict requirements:
1. Generate a single, self-contained, valid Java file with the class name `RestExamples`.
2. Use standard Java 11+ features: `HttpClient.newHttpClient()`, `HttpRequest`, and `HttpResponse.BodyHandlers.ofString()`.
3. Separate each endpoint example clearly using standard methods inside `RestExamples` or distinct blocks within the `main` method.
4. Authentication: Apply the authentication method {auth_type} cleanly to the headers of the request builder.
5. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payloads) clearly at the top of each block/method so developers can easily replace them.
6. Execution: Build the URI (injecting path variables, parameters), set headers, configure the body publisher (`HttpRequest.BodyPublishers.ofString(bodyJson)`), and send synchronously.
7. Error Handling: Include try/catch blocks for `IOException` and `InterruptedException`. Perform check on `response.statusCode()` and print responses appropriately.

Return ONLY the raw Java code. Do not include markdown code blocks or conversational text.
"""
            try:
                model = genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                code = response.text.strip()
                
                # Clean any accidental markdown wrap
                if code.startswith("```"):
                    lines = code.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    code = "\n".join(lines).strip()
                return code
            except Exception as e:
                print(f"Gemini generation in JavaRESTGenerator failed ({str(e)}). Using local template.")

        # Fallback to dynamic local templates
        return self._generate_fallback(api_name, auth_type, auth_desc, endpoints)

    def _generate_fallback(self, api_name: str, auth_type: str, auth_desc: str, endpoints: list) -> str:
        """
        Dynamically builds a high-fidelity REST integration script in Java when LLM is unavailable.
        """
        lines = [
            "import java.io.IOException;",
            "import java.net.URI;",
            "import java.net.http.HttpClient;",
            "import java.net.http.HttpRequest;",
            "import java.net.http.HttpResponse;",
            "import java.net.URLEncoder;",
            "import java.nio.charset.StandardCharsets;",
            "",
            "/**",
            f" * Standalone Java REST Integration Examples for {api_name}.",
            f" * Auth Method: {auth_type}",
            " */",
            "public class RestExamples {",
            "",
            "    private static final String BASE_URL = \"https://api.example.com\";",
        ]

        if auth_type == "Bearer Token":
            lines.append("    private static final String API_TOKEN = System.getenv().getOrDefault(\"API_TOKEN\", \"YOUR_BEARER_TOKEN\");")
        else:
            lines.append("    private static final String API_KEY = System.getenv().getOrDefault(\"API_KEY\", \"YOUR_API_KEY\");")

        lines.append("")
        lines.append("    public static void main(String[] args) {")
        lines.append("        HttpClient client = HttpClient.newHttpClient();")
        lines.append("")

        for i, ep in enumerate(endpoints, 1):
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]

            lines.extend([
                "        // " + "=" * 68,
                f"        // {i}. {desc} ({method} {path})",
                "        // " + "=" * 68,
                f"        System.out.println(\"\\n--- Running Example {i}: {desc} ---\");"
            ])

            # Path variables
            path_vars = re.findall(r'\{(\w+)\}', path)
            for var in path_vars:
                lines.append(f"        String {var} = \"sample_{var}\";")

            java_path = path
            for var in path_vars:
                java_path = java_path.replace(f"{{{var}}}", f"\" + {var} + \"")
            java_path = f"\"{java_path}\"".replace(" + \"\"", "").replace("\"\" + ", "")

            # URL setup
            if method in ["POST", "PUT", "PATCH"]:
                lines.append(f"        String url = BASE_URL + {java_path};")
            else:
                lines.append(f"        String url = BASE_URL + {java_path} + \"?limit=10\";")

            # Request construction
            lines.append("        try {")
            lines.append("            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()")
            lines.append("                .uri(URI.create(url))")
            lines.append("                .header(\"Content-Type\", \"application/json\");")

            if auth_type == "Bearer Token":
                lines.append("            requestBuilder.header(\"Authorization\", \"Bearer \" + API_TOKEN);")
            elif auth_type == "API Key":
                lines.append("            requestBuilder.header(\"X-API-Key\", API_KEY);")

            # Configure Method & Body
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("            String payload = \"{\\\"example_key\\\": \\\"example_value\\\"}\";")
                lines.append(f"            requestBuilder.method(\"{method}\", HttpRequest.BodyPublishers.ofString(payload));")
            else:
                lines.append(f"            requestBuilder.method(\"{method}\", HttpRequest.BodyPublishers.noBody());")

            lines.extend([
                "            ",
                "            System.out.println(\"Sending request to: \" + url);",
                "            HttpRequest request = requestBuilder.build();",
                "            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());",
                "            ",
                "            System.out.println(\"Response Status: \" + response.statusCode());",
                "            if (response.statusCode() >= 200 && response.statusCode() < 300) {",
                "                System.out.println(\"Response: \" + response.body());",
                "            } else {",
                "                System.err.println(\"Request Failed: \" + response.statusCode() + \" - \" + response.body());",
                "            }",
                "        } catch (IOException | InterruptedException e) {",
                "            System.err.println(\"Execution Error: \" + e.getMessage());",
                "        }"
            ])
            lines.append("")

        lines.append("    }")
        lines.append("}")

        return "\n".join(lines)
