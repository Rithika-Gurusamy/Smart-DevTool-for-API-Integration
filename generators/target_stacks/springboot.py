from generators.target_stacks.base import BaseTargetStackGenerator
import re

class SpringBootGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        api_name = api_metadata.get("api_name", "API")
        class_name = api_name.replace(" ", "").replace("-", "") + "Service"
        auth_info = api_metadata.get("auth_method", {})
        auth_type = auth_info.get("type", "API Key")
        endpoints = api_metadata.get("endpoints", [])
        
        lines = [
            "package com.example.api.service;",
            "",
            "import org.springframework.beans.factory.annotation.Value;",
            "import org.springframework.stereotype.Service;",
            "import org.springframework.web.client.RestTemplate;",
            "import org.springframework.http.HttpEntity;",
            "import org.springframework.http.HttpHeaders;",
            "import org.springframework.http.HttpMethod;",
            "import org.springframework.http.ResponseEntity;",
            "",
            "@Service",
            f"public class {class_name} {{",
            "",
            "    private final RestTemplate restTemplate;",
            "",
            f"    @Value(\"${{{api_name.lower().replace(' ', '.')}.api-key}}\")",
            "    private String apiKey;",
            "",
            f"    @Value(\"${{{api_name.lower().replace(' ', '.')}.base-url:https://api.example.com}}\")",
            "    private String baseUrl;",
            "",
            f"    public {class_name}(RestTemplate restTemplate) {{",
            "        this.restTemplate = restTemplate;",
            "    }",
            "",
            "    private HttpHeaders createHeaders() {",
            "        HttpHeaders headers = new HttpHeaders();",
            "        headers.set(\"Content-Type\", \"application/json\");",
            f"        if (\"Bearer Token\".equals(\"{auth_type}\")) {{",
            "            headers.set(\"Authorization\", \"Bearer \" + apiKey);",
            "        } else {",
            "            headers.set(\"X-API-Key\", apiKey);",
            "        }",
            "        return headers;",
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
                "    /**",
                f"     * {desc}",
                "     */",
                f"    public String {method_name}(String payload) {{",
                f"        String url = baseUrl + \"{path}\";",
                "        HttpHeaders headers = createHeaders();",
                "        HttpEntity<String> entity = new HttpEntity<>(payload, headers);",
                f"        ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.{method}, entity, String.class);",
                "        return response.getBody();",
                "    }",
                ""
            ])
            
        lines.append("}")
        return "\n".join(lines)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        # Reuses JavaRESTGenerator but wraps inside Spring Boot class
        from generators.target_stacks.generic_java import GenericJavaGenerator
        return GenericJavaGenerator(api_key=self.api_key).generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Spring Boot backend target stack has no frontend client configuration."}

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "main/": {
                    "java/": {
                        "com/": {
                            "example/": {
                                "api/": {
                                    "config/": {
                                        "ClientConfig.java": None
                                    },
                                    "service/": {
                                        "ClientService.java": None
                                    },
                                    "model/": {}
                                }
                            }
                        }
                    },
                    "resources/": {
                        "application.properties": None
                    }
                }
            }
        }

    def get_framework_features(self) -> list:
        return ["Spring Boot @Service components", "@Value configurations injections", "RestTemplate HTTP exchange configuration bean"]

    def get_generated_assets(self) -> list:
        return ["ClientService.java", "ClientConfig.java", "application.properties", "README.md"]
