from generators.target_stacks.base import BaseTargetStackGenerator
from generators.rest_java import JavaRESTGenerator
import re

class GenericJavaGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        """
        Generates a standard Java SDK class wrapping the endpoints.
        """
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "Client"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        # Build Java wrapper fallback
        lines = [
            "package com.example.client;",
            "",
            "import java.io.IOException;",
            "import java.net.URI;",
            "import java.net.http.HttpClient;",
            "import java.net.http.HttpRequest;",
            "import java.net.http.HttpResponse;",
            "import java.time.Duration;",
            "import java.util.Map;",
            "",
            f"public class {class_name} {{",
            "    private final HttpClient client;",
            "    private final String baseUrl;",
            "    private final String apiKeyOrToken;",
            "",
            f"    public {class_name}(String apiKeyOrToken, String baseUrl) {{",
            "        this.apiKeyOrToken = apiKeyOrToken;",
            "        this.baseUrl = baseUrl.endsWith(\"/\") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;",
            "        this.client = HttpClient.newBuilder()",
            "            .connectTimeout(Duration.ofSeconds(10))",
            "            .build();",
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
            method_name = re.sub(r'v\d+_', '', method_name)
            if not method_name:
                method_name = "request"
            method_name = f"{method.lower()}{''.join([w.capitalize() for w in method_name.split('_')])}"
            
            lines.extend([
                f"    /**",
                f"     * {desc}",
                f"     */",
                f"    public String {method_name}(String payload) throws IOException, InterruptedException {{",
                f"        String url = this.baseUrl + \"{path}\";",
                f"        HttpRequest.Builder builder = HttpRequest.newBuilder()",
                f"            .uri(URI.create(url))",
                f"            .header(\"Content-Type\", \"application/json\");"
            ])
            
            if auth_type == "Bearer Token":
                lines.append("        builder.header(\"Authorization\", \"Bearer \" + this.apiKeyOrToken);")
            else:
                lines.append("        builder.header(\"X-API-Key\", this.apiKeyOrToken);")
                
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("        builder.method(\"" + method + "\", HttpRequest.BodyPublishers.ofString(payload));")
            else:
                lines.append("        builder.method(\"" + method + "\", HttpRequest.BodyPublishers.noBody());")
                
            lines.extend([
                "        HttpResponse<String> response = this.client.send(builder.build(), HttpResponse.BodyHandlers.ofString());",
                "        if (response.statusCode() >= 200 && response.statusCode() < 300) {",
                "            return response.body();",
                "        } else {",
                "            throw new RuntimeException(\"Request failed: \" + response.statusCode() + \" - \" + response.body());",
                "        }",
                "    }",
                ""
            ])
            
        lines.append("}")
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        gen = JavaRESTGenerator(api_key=self.api_key)
        return gen.generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Generic Java Target Stack integration package."}

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "main/": {
                    "java/": {
                        "com/": {
                            "example/": {
                                "client/": {
                                    "ApiClient.java": None,
                                    "exceptions/": {}
                                }
                            }
                        }
                    }
                }
            }
        }

    def get_framework_features(self) -> list:
        return ["Java 11+ HttpClient wrapper", "Normalized static exception classes", "Dynamic token authorization headers"]

    def get_generated_assets(self) -> list:
        return ["ApiClient.java", "RestExamples.java", "README.md"]
