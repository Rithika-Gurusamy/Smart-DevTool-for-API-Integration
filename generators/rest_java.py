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
2. Define a hierarchy of custom exception classes: `APIClientError`, `ValidationError`, `AuthenticationError`, `RateLimitError`, `ServerError`, `NetworkError`, `TimeoutError` as package-private classes at the bottom of the file or static nested classes.
3. Implement a centralized `HttpClientWrapper` helper class that encapsulates a Java 11+ `HttpClient`, injecting appropriate headers for {auth_type}, handles transient error retries (status 502, 503, 504 and network errors) with exponential backoff, respects `Retry-After` header for rate limit (429 status code), handles logging hooks (request/response logs based on enableLogging flag), and throws the appropriate custom exceptions.
4. Separate each endpoint example clearly using standard methods inside `RestExamples` or distinct blocks within the `main` method.
5. In the examples, instantiate `HttpClientWrapper` with the appropriate baseUrl and authentication credentials, and route all requests through `HttpClientWrapper.sendRequest()`. Capture client exceptions and print response outputs appropriately.
6. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payloads) clearly at the top of each block/method so developers can easily replace them.

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
            "import java.time.Duration;",
            "import java.util.Map;",
            "import java.util.HashMap;",
            "",
            "// " + "=" * 68,
            "// Custom Exceptions for Normalized Error Handling",
            "// " + "=" * 68,
            "class APIClientError extends RuntimeException {",
            "    public APIClientError(String msg) { super(msg); }",
            "    public APIClientError(String msg, Throwable cause) { super(msg, cause); }",
            "}",
            "",
            "class ValidationError extends APIClientError {",
            "    public ValidationError(String msg) { super(msg); }",
            "}",
            "",
            "class AuthenticationError extends APIClientError {",
            "    public AuthenticationError(String msg) { super(msg); }",
            "}",
            "",
            "class RateLimitError extends APIClientError {",
            "    public RateLimitError(String msg) { super(msg); }",
            "}",
            "",
            "class ServerError extends APIClientError {",
            "    public ServerError(String msg) { super(msg); }",
            "}",
            "",
            "class NetworkError extends APIClientError {",
            "    public NetworkError(String msg, Throwable cause) { super(msg, cause); }",
            "}",
            "",
            "class TimeoutError extends APIClientError {",
            "    public TimeoutError(String msg, Throwable cause) { super(msg, cause); }",
            "}",
            "",
            "// " + "=" * 68,
            "// Reusable HttpClient Wrapper with Interceptors & Retries",
            "// " + "=" * 68,
            "class HttpClientWrapper {",
            "    private final HttpClient client;",
            "    private final String baseUrl;",
            "    private final String authType;",
            "    private final Map<String, String> credentials;",
            "    private final int maxRetries;",
            "    private final boolean enableLogging;",
            "",
            "    public HttpClientWrapper(String baseUrl, String authType, Map<String, String> credentials, int maxRetries, boolean enableLogging) {",
            "        this.baseUrl = baseUrl.endsWith(\"/\") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;",
            "        this.authType = authType;",
            "        this.credentials = credentials;",
            "        this.maxRetries = maxRetries;",
            "        this.enableLogging = enableLogging;",
            "        this.client = HttpClient.newBuilder()",
            "            .connectTimeout(Duration.ofSeconds(10))",
            "            .build();",
            "    }",
            "",
            "    private void log(String level, String msg) {",
            "        if (enableLogging) {",
            "            System.out.println(\"[\" + level + \"] \" + msg);",
            "        }",
            "    }",
            "",
            "    public String sendRequest(String method, String path, String body) {",
            "        int retries = 0;",
            "        long delay = 1000;",
            "        String url = baseUrl + path;",
            "        while (true) {",
            "            HttpRequest.Builder builder = HttpRequest.newBuilder()",
            "                .uri(URI.create(url))",
            "                .header(\"Content-Type\", \"application/json\");",
            "",
            "            if (\"Bearer Token\".equals(authType) && credentials.containsKey(\"token\")) {",
            "                builder.header(\"Authorization\", \"Bearer \" + credentials.get(\"token\"));",
            "            } else if (\"API Key\".equals(authType) && credentials.containsKey(\"apiKey\")) {",
            "                builder.header(\"X-API-Key\", credentials.get(\"apiKey\"));",
            "            }",
            "",
            "            if (body != null && (method.equals(\"POST\") || method.equals(\"PUT\") || method.equals(\"PATCH\"))) {",
            "                builder.method(method, HttpRequest.BodyPublishers.ofString(body));",
            "            } else {",
            "                builder.method(method, HttpRequest.BodyPublishers.noBody());",
            "            }",
            "",
            "            HttpRequest request = builder.build();",
            "            log(\"INFO\", \"Sending \" + method + \" request to: \" + url);",
            "",
            "            try {",
            "                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());",
            "                int status = response.statusCode();",
            "                log(\"INFO\", \"Response Status: \" + status);",
            "",
            "                if (status >= 200 && status < 300) {",
            "                    return response.body();",
            "                }",
            "",
            "                if (status == 429) {",
            "                    String retryAfter = response.headers().firstValue(\"Retry-After\").orElse(null);",
            "                    long sleepMs = delay;",
            "                    if (retryAfter != null) {",
            "                        try {",
            "                            sleepMs = Long.parseLong(retryAfter) * 1000;",
            "                        } catch (NumberFormatException e) {",
            "                            sleepMs = delay;",
            "                        }",
            "                    }",
            "                    log(\"WARNING\", \"429 Rate Limited. Cooling down for \" + sleepMs + \"ms...\");",
            "                    Thread.sleep(sleepMs);",
            "                    continue;",
            "                }",
            "",
            "                if ((status == 502 || status == 503 || status == 504) && retries < maxRetries) {",
            "                    log(\"WARNING\", \"Transient error \" + status + \". Retrying in \" + delay + \"ms...\");",
            "                    Thread.sleep(delay);",
            "                    retries++;",
            "                    delay *= 2;",
            "                    continue;",
            "                }",
            "",
            "                String errBody = response.body();",
            "                if (status == 401 || status == 403) {",
            "                    throw new AuthenticationError(\"Auth failed: \" + errBody);",
            "                } else if (status == 429) {",
            "                    throw new RateLimitError(\"Rate limit exceeded.\");",
            "                } else if (status >= 400 && status < 500) {",
            "                    throw new ValidationError(\"Validation failed: \" + errBody);",
            "                } else {",
            "                    throw new ServerError(\"Server error: \" + errBody);",
            "                }",
            "",
            "            } catch (IOException e) {",
            "                if (retries < maxRetries) {",
            "                    log(\"WARNING\", \"Network error: \" + e.getMessage() + \". Retrying in \" + delay + \"ms...\");",
            "                    try { Thread.sleep(delay); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }",
            "                    retries++;",
            "                    delay *= 2;",
            "                    continue;",
            "                }",
            "                throw new NetworkError(\"Network failed: \" + e.getMessage(), e);",
            "            } catch (InterruptedException e) {",
            "                Thread.currentThread().interrupt();",
            "                throw new APIClientError(\"Request interrupted: \" + e.getMessage(), e);",
            "            }",
            "        }",
            "    }",
            "}",
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
        
        # Instantiate HttpClientWrapper
        if auth_type == "Bearer Token":
            lines.append("        Map<String, String> credentials = Map.of(\"token\", API_TOKEN);")
            lines.append("        HttpClientWrapper client = new HttpClientWrapper(BASE_URL, \"Bearer Token\", credentials, 3, true);")
        else:
            lines.append("        Map<String, String> credentials = Map.of(\"apiKey\", API_KEY);")
            lines.append("        HttpClientWrapper client = new HttpClientWrapper(BASE_URL, \"API Key\", credentials, 3, true);")
            
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
                lines.append(f"        String urlPath = {java_path};")
            else:
                lines.append(f"        String urlPath = {java_path} + \"?limit=10\";")

            # Request construction using HttpClientWrapper
            lines.append("        try {")
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("            String payload = \"{\\\"example_key\\\": \\\"example_value\\\"}\";")
                lines.append(f"            String response = client.sendRequest(\"{method}\", urlPath, payload);")
            else:
                lines.append(f"            String response = client.sendRequest(\"{method}\", urlPath, null);")

            lines.extend([
                "            System.out.println(\"Response Data: \" + response);",
                "        } catch (APIClientError e) {",
                "            System.err.println(\"Error encountered: \" + e.getMessage());",
                "        }"
            ])
            lines.append("")

        lines.append("    }")
        lines.append("}")

        return "\n".join(lines)
