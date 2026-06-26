from generators.target_stacks.base import BaseTargetStackGenerator
from generators.rest_csharp import CSharpRESTGenerator
import re

class GenericNetGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        """
        Generates a standard C# SDK wrapper class using System.Net.Http.HttpClient.
        """
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "Client"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            "using System;",
            "using System.Net.Http;",
            "using System.Text;",
            "using System.Threading.Tasks;",
            "",
            "namespace RESTIntegration",
            "{",
            f"    public class {class_name}",
            "    {",
            "        private readonly HttpClient _client;",
            "        private readonly string _baseUrl;",
            "        private readonly string _apiKeyOrToken;",
            "",
            f"        public {class_name}(HttpClient client, string apiKeyOrToken, string baseUrl = \"https://api.example.com\")",
            "        {",
            "            _client = client;",
            "            _apiKeyOrToken = apiKeyOrToken;",
            "            _baseUrl = baseUrl.EndsWith(\"/\") ? baseUrl.Substring(0, baseUrl.Length - 1) : baseUrl;",
            "        }",
            "",
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
                "        /// <summary>",
                f"        /// {desc}",
                "        /// </summary>",
                f"        public async Task<string> {method_name}Async(string payload)",
                "        {",
                f"            string url = _baseUrl + \"{path}\";",
                f"            using var request = new HttpRequestMessage(new HttpMethod(\"{method}\"), url);",
                "            request.Headers.Add(\"Accept\", \"application/json\");"
            ])
            
            if auth_type == "Bearer Token":
                lines.append("            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(\"Bearer\", _apiKeyOrToken);")
            else:
                lines.append("            request.Headers.Add(\"X-API-Key\", _apiKeyOrToken);")
                
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("            request.Content = new StringContent(payload, Encoding.UTF8, \"application/json\");")
                
            lines.extend([
                "            using var response = await _client.SendAsync(request);",
                "            string responseBody = await response.Content.ReadAsStringAsync();",
                "            if (response.IsSuccessStatusCode)",
                "            {",
                "                return responseBody;",
                "            }",
                "            throw new HttpRequestException($\"Request failed: {(int)response.StatusCode} - {responseBody}\");",
                "        }",
                ""
            ])
            
        lines.append("    }")
        lines.append("}")
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        gen = CSharpRESTGenerator(api_key=self.api_key)
        return gen.generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Generic .NET Target Stack integration package."}

    def get_folder_structure(self) -> dict:
        return {
            "Config/": {"ApiSettings.cs": None},
            "Services/": {"ApiClient.cs": None},
            "Models/": {"Customer.cs": None}
        }

    def get_framework_features(self) -> list:
        return ["System.Net.Http.HttpClient integration", "Async/Await asynchronous endpoints", "C# custom exception handling"]

    def get_generated_assets(self) -> list:
        return ["ApiClient.cs", "RestExamples.cs", "README.md"]
