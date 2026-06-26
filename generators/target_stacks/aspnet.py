from generators.target_stacks.base import BaseTargetStackGenerator
import re

class ASPNETCoreGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "Service"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            "using System;",
            "using System.Net.Http;",
            "using System.Text;",
            "using System.Threading.Tasks;",
            "using Microsoft.Extensions.Configuration;",
            "",
            "namespace WebApplication.Services",
            "{",
            "    /// <summary>",
            f"    /// Typed HttpClient Service for {api_name} injected via Dependency Injection.",
            "    /// </summary>",
            f"    public class {class_name}",
            "    {",
            "        private readonly HttpClient _client;",
            "        private readonly string _apiKey;",
            "",
            f"        public {class_name}(HttpClient client, IConfiguration configuration)",
            "        {",
            "            _client = client;",
            f"            _apiKey = configuration[\"{api_name.replace(' ', '')}:ApiKey\"];",
            f"            var baseUrl = configuration[\"{api_name.replace(' ', '')}:BaseUrl\"] ?? \"https://api.example.com\";",
            "            _client.BaseAddress = new Uri(baseUrl);",
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
                f"            using var request = new HttpRequestMessage(new HttpMethod(\"{method}\"), \"{path}\");",
                "            request.Headers.Add(\"Accept\", \"application/json\");"
            ])
            
            if auth_type == "Bearer Token":
                lines.append("            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(\"Bearer\", _apiKey);")
            else:
                lines.append("            request.Headers.Add(\"X-API-Key\", _apiKey);")
                
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
            
        lines.extend([
            "    }",
            "",
            "    // DI Registration Helper Extensions example",
            "    // Add this inside Program.cs: builder.Services.AddHttpClient<" + class_name + ">();",
            "}"
        ])
        
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        from generators.target_stacks.generic_net import GenericNetGenerator
        return GenericNetGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "ASP.NET Core target stack has no frontend client configuration."}

    def get_folder_structure(self) -> dict:
        return {
            "Config/": {"appsettings.json": None},
            "Services/": {
                "ClientService.cs": None
            },
            "Controllers/": {
                "ApiController.cs": None
            },
            "Program.cs": None
        }

    def get_framework_features(self) -> list:
        return ["Typed HttpClient integration", "ASP.NET Dependency injection integration", "appsettings.json property integration"]

    def get_generated_assets(self) -> list:
        return ["ClientService.cs", "appsettings.json", "Program.cs", "README.md"]
