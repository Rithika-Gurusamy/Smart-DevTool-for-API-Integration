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

class CSharpRESTGenerator(BaseRESTGenerator):
    """
    Generates standalone, copy-pasteable REST integration scripts in C# using .NET HttpClient.
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
You are a Principal Software Engineer. Generate standalone, production-ready REST integration examples in C# (.NET) using `System.Net.Http.HttpClient`.

API Name: {api_name}
Use Case: {use_case}
Authentication Method: {auth_type} ({auth_desc})

Endpoints to implement (ONLY generate standalone HttpClient request examples for these Primary/Supporting endpoints):
{endpoints_str}

Follow these strict requirements:
1. Generate a single, self-contained, valid C# file with class name `RestExamples`.
2. Use standard async/await syntax and `System.Net.Http.HttpClient`.
3. Separate each endpoint example clearly using standard methods inside `RestExamples` or distinct blocks within the `Main` method.
4. Authentication: Apply the authentication method {auth_type} cleanly to the client headers or HttpRequestMessage headers.
5. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payloads) clearly at the top of each block/method so developers can easily replace them.
6. Execution: Build the URL (injecting path variables), construct `HttpRequestMessage`, configure `StringContent` for payload requests, and send using `SendAsync()`.
7. Error Handling: Include try/catch blocks for `HttpRequestException`. Perform checks on `response.IsSuccessStatusCode` and print responses or status codes appropriately.

Return ONLY the raw C# code. Do not include markdown code blocks or conversational text.
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
                print(f"Gemini generation in CSharpRESTGenerator failed ({str(e)}). Using local template.")

        # Fallback to dynamic local templates
        return self._generate_fallback(api_name, auth_type, auth_desc, endpoints)

    def _generate_fallback(self, api_name: str, auth_type: str, auth_desc: str, endpoints: list) -> str:
        """
        Dynamically builds a high-fidelity REST integration script in C# when LLM is unavailable.
        """
        lines = [
            "using System;",
            "using System.Net.Http;",
            "using System.Text;",
            "using System.Threading.Tasks;",
            "",
            "namespace RESTIntegration",
            "{",
            "    /// <summary>",
            f"    /// Standalone C# REST Integration Examples for {api_name}.",
            f"    /// Auth Method: {auth_type}",
            "    /// </summary>",
            "    public class RestExamples",
            "    {",
            "        private const string BaseUrl = \"https://api.example.com\";",
        ]

        if auth_type == "Bearer Token":
            lines.append("        private static readonly string ApiToken = Environment.GetEnvironmentVariable(\"API_TOKEN\") ?? \"YOUR_BEARER_TOKEN\";")
        else:
            lines.append("        private static readonly string ApiKey = Environment.GetEnvironmentVariable(\"API_KEY\") ?? \"YOUR_API_KEY\";")

        lines.append("")
        lines.append("        public static async Task Main(string[] args)")
        lines.append("        {")
        lines.append("            using var client = new HttpClient();")
        lines.append("")

        for i, ep in enumerate(endpoints, 1):
            method = ep["method"].upper()
            path = ep["path"]
            desc = ep["description"]

            lines.extend([
                "            // " + "=" * 68,
                f"            // {i}. {desc} ({method} {path})",
                "            // " + "=" * 68,
                f"            Console.WriteLine(\"\\n--- Running Example {i}: {desc} ---\");"
            ])

            # Path variables
            path_vars = re.findall(r'\{(\w+)\}', path)
            for var in path_vars:
                lines.append(f"            string {var} = \"sample_{var}\";")

            csharp_path = path
            for var in path_vars:
                csharp_path = csharp_path.replace(f"{{{var}}}", f"{{{var}}}")
                
            if path_vars:
                lines.append(f"            string path = $\"{csharp_path}\";")
            else:
                lines.append(f"            string path = \"{path}\";")

            # URL setup
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("            string url = BaseUrl + path;")
            else:
                lines.append("            string url = BaseUrl + path + \"?limit=10\";")

            # Request construction
            lines.append("            try")
            lines.append("            {")
            lines.append(f"                using var request = new HttpRequestMessage(new HttpMethod(\"{method}\"), url);")

            if auth_type == "Bearer Token":
                lines.append("                request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(\"Bearer\", ApiToken);")
            elif auth_type == "API Key":
                lines.append("                request.Headers.Add(\"X-API-Key\", ApiKey);")

            # Configure Method & Body
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("                string payload = \"{\\\"example_key\\\": \\\"example_value\\\"}\";")
                lines.append("                request.Content = new StringContent(payload, Encoding.UTF8, \"application/json\");")

            lines.extend([
                "                Console.WriteLine($\"Sending request to: {url}\");",
                "                using var response = await client.SendAsync(request);",
                "                string responseBody = await response.Content.ReadAsStringAsync();",
                "                ",
                "                Console.WriteLine($\"Response Status: {(int)response.StatusCode} {response.ReasonPhrase}\");",
                "                if (response.IsSuccessStatusCode)",
                "                {",
                "                    Console.WriteLine($\"Response: {responseBody}\");",
                "                }",
                "                else",
                "                {",
                "                    Console.Error.WriteLine($\"Request Failed: {response.StatusCode} - {responseBody}\");",
                "                }",
                "            }",
                "            catch (HttpRequestException e)",
                "            {",
                "                Console.Error.WriteLine($\"Network Error: {e.Message}\");",
                "            }"
            ])
            lines.append("")

        lines.append("        }")
        lines.append("    }")
        lines.append("}")

        return "\n".join(lines)
