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
2. Define a hierarchy of custom exception classes: `APIClientException`, `ValidationException`, `AuthenticationException`, `RateLimitException`, `ServerException`, `NetworkException`, `TimeoutException` inheriting from a base `APIClientException`.
3. Implement a reusable delegation pipeline using `DelegatingHandler` classes:
   - `LoggingHandler`: logs requests and response metadata based on enableLogging flag.
   - `AuthHandler`: applies headers for {auth_type} to the request.
   - `ErrorMappingHandler`: translates non-success HTTP status codes into appropriate custom exceptions.
   - `RetryHandler`: handles retrying requests on transient failures (502, 503, 504 and network exceptions) using exponential backoff, and throttling rate-limited requests (429) using `Retry-After`.
4. Separate each endpoint example clearly using standard methods inside `RestExamples` or distinct blocks within the `Main` method.
5. Instantiate the `HttpClient` passing the chained handlers, and invoke requests with `SendAsync()`. Capture subclasses of `APIClientException` and print response outputs appropriately.
6. Variables: Define all parameters (e.g. BASE_URL, API_KEY, path variables, query parameters, payloads) clearly at the top of each block/method so developers can easily replace them.

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
            "using System.Net;",
            "using System.Net.Http;",
            "using System.Text;",
            "using System.Threading;",
            "using System.Threading.Tasks;",
            "",
            "namespace RESTIntegration",
            "{",
            "    // " + "=" * 64,
            "    // Custom Exceptions for Normalized Error Handling",
            "    // " + "=" * 64,
            "    public class APIClientException : Exception",
            "    {",
            "        public APIClientException(string message) : base(message) { }",
            "        public APIClientException(string message, Exception inner) : base(message, inner) { }",
            "    }",
            "",
            "    public class ValidationException : APIClientException",
            "    {",
            "        public ValidationException(string message) : base(message) { }",
            "    }",
            "",
            "    public class AuthenticationException : APIClientException",
            "    {",
            "        public AuthenticationException(string message) : base(message) { }",
            "    }",
            "",
            "    public class RateLimitException : APIClientException",
            "    {",
            "        public RateLimitException(string message) : base(message) { }",
            "    }",
            "",
            "    public class ServerException : APIClientException",
            "    {",
            "        public ServerException(string message) : base(message) { }",
            "    }",
            "",
            "    public class NetworkException : APIClientException",
            "    {",
            "        public NetworkException(string message, Exception inner) : base(message, inner) { }",
            "    }",
            "",
            "    public class TimeoutException : APIClientException",
            "    {",
            "        public TimeoutException(string message, Exception inner) : base(message, inner) { }",
            "    }",
            "",
            "    // " + "=" * 64,
            "    // Delegating Handlers for Interception Pipeline",
            "    // " + "=" * 64,
            "    public class LoggingHandler : DelegatingHandler",
            "    {",
            "        private readonly bool _enableLogging;",
            "        public LoggingHandler(bool enableLogging) { _enableLogging = enableLogging; }",
            "        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
            "        {",
            "            if (_enableLogging) Console.WriteLine($\"[INFO] Sending {request.Method} request to: {request.RequestUri}\");",
            "            var response = await base.SendAsync(request, cancellationToken);",
            "            if (_enableLogging) Console.WriteLine($\"[INFO] Response status: {(int)response.StatusCode} {response.ReasonPhrase}\");",
            "            return response;",
            "        }",
            "    }",
            "",
            "    public class AuthHandler : DelegatingHandler",
            "    {",
            "        private readonly string _authType;",
            "        private readonly string _tokenOrKey;",
            "        public AuthHandler(string authType, string tokenOrKey)",
            "        {",
            "            _authType = authType;",
            "            _tokenOrKey = tokenOrKey;",
            "        }",
            "        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
            "        {",
            "            if (_authType == \"Bearer Token\")",
            "            {",
            "                request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(\"Bearer\", _tokenOrKey);",
            "            }",
            "            else if (_authType == \"API Key\")",
            "            {",
            "                request.Headers.Add(\"X-API-Key\", _tokenOrKey);",
            "            }",
            "            return base.SendAsync(request, cancellationToken);",
            "        }",
            "    }",
            "",
            "    public class ErrorMappingHandler : DelegatingHandler",
            "    {",
            "        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
            "        {",
            "            var response = await base.SendAsync(request, cancellationToken);",
            "            if (response.IsSuccessStatusCode) return response;",
            "            var status = (int)response.StatusCode;",
            "            var errorText = await response.Content.ReadAsStringAsync();",
            "            if (status == 401 || status == 403) throw new AuthenticationException($\"Auth failed: {errorText}\");",
            "            if (status == 429) throw new RateLimitException(\"Rate limit exceeded.\");",
            "            if (status >= 400 && status < 500) throw new ValidationException($\"Validation failed: {errorText}\");",
            "            throw new ServerException($\"Server error: {errorText}\");",
            "        }",
            "    }",
            "",
            "    public class RetryHandler : DelegatingHandler",
            "    {",
            "        private readonly int _maxRetries;",
            "        public RetryHandler(int maxRetries) { _maxRetries = maxRetries; }",
            "        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
            "        {",
            "            int retries = 0;",
            "            int delay = 1000;",
            "            while (true)",
            "            {",
            "                HttpResponseMessage response = null;",
            "                HttpRequestMessage clonedRequest = await CloneRequestAsync(request);",
            "                try",
            "                {",
            "                    response = await base.SendAsync(clonedRequest, cancellationToken);",
            "                }",
            "                catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException || ex is System.IO.IOException)",
            "                {",
            "                    if (retries >= _maxRetries) throw new NetworkException(\"Network request failed after retries\", ex);",
            "                    Console.WriteLine($\"[WARNING] Transient failure: {ex.Message}. Retrying in {delay}ms...\");",
            "                    await Task.Delay(delay, cancellationToken);",
            "                    retries++; delay *= 2;",
            "                    continue;",
            "                }",
            "",
            "                int status = (int)response.StatusCode;",
            "                if (status == 429)",
            "                {",
            "                    int sleepMs = delay;",
            "                    if (response.Headers.RetryAfter != null)",
            "                    {",
            "                        if (response.Headers.RetryAfter.Delta.HasValue)",
            "                            sleepMs = (int)response.Headers.RetryAfter.Delta.Value.TotalMilliseconds;",
            "                        else if (response.Headers.RetryAfter.Date.HasValue)",
            "                            sleepMs = (int)(response.Headers.RetryAfter.Date.Value - DateTimeOffset.UtcNow).TotalMilliseconds;",
            "                    }",
            "                    if (sleepMs < 0) sleepMs = 1000;",
            "                    Console.WriteLine($\"[WARNING] 429 Rate Limited. Cooling down for {sleepMs}ms...\");",
            "                    await Task.Delay(sleepMs, cancellationToken);",
            "                    continue;",
            "                }",
            "",
            "                if ((status == 502 || status == 503 || status == 504) && retries < _maxRetries)",
            "                {",
            "                    Console.WriteLine($\"[WARNING] Transient error {status}. Retrying in {delay}ms...\");",
            "                    await Task.Delay(delay, cancellationToken);",
            "                    retries++; delay *= 2;",
            "                    continue;",
            "                }",
            "                return response;",
            "            }",
            "        }",
            "",
            "        private async Task<HttpRequestMessage> CloneRequestAsync(HttpRequestMessage req)",
            "        {",
            "            var clone = new HttpRequestMessage(req.Method, req.RequestUri);",
            "            foreach (var header in req.Headers) clone.Headers.TryAddWithoutValidation(header.Key, header.Value);",
            "            #if NET5_0_OR_GREATER",
            "            foreach (var option in req.Options) clone.Options.Set(new HttpRequestOptionsKey<object>(option.Key), option.Value);",
            "            #else",
            "            foreach (var prop in req.Properties) clone.Properties.Add(prop.Key, prop.Value);",
            "            #endif",
            "            if (req.Content != null)",
            "            {",
            "                var ms = new System.IO.MemoryStream();",
            "                await req.Content.CopyToAsync(ms);",
            "                ms.Position = 0;",
            "                clone.Content = new StreamContent(ms);",
            "                foreach (var header in req.Content.Headers) clone.Content.Headers.TryAddWithoutValidation(header.Key, header.Value);",
            "            }",
            "            return clone;",
            "        }",
            "    }",
            "",
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
        
        # Build client pipeline
        if auth_type == "Bearer Token":
            lines.extend([
                "            var loggingHandler = new LoggingHandler(true) { InnerHandler = new HttpClientHandler() };",
                "            var errorMappingHandler = new ErrorMappingHandler { InnerHandler = loggingHandler };",
                "            var authHandler = new AuthHandler(\"Bearer Token\", ApiToken) { InnerHandler = errorMappingHandler };",
                "            var retryHandler = new RetryHandler(3) { InnerHandler = authHandler };",
                "            using var client = new HttpClient(retryHandler);"
            ])
        else:
            lines.extend([
                "            var loggingHandler = new LoggingHandler(true) { InnerHandler = new HttpClientHandler() };",
                "            var errorMappingHandler = new ErrorMappingHandler { InnerHandler = loggingHandler };",
                "            var authHandler = new AuthHandler(\"API Key\", ApiKey) { InnerHandler = errorMappingHandler };",
                "            var retryHandler = new RetryHandler(3) { InnerHandler = authHandler };",
                "            using var client = new HttpClient(retryHandler);"
            ])
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

            # Configure Method & Body
            if method in ["POST", "PUT", "PATCH"]:
                lines.append("                string payload = \"{\\\"example_key\\\": \\\"example_value\\\"}\";")
                lines.append("                request.Content = new StringContent(payload, Encoding.UTF8, \"application/json\");")

            lines.extend([
                "                using var response = await client.SendAsync(request);",
                "                string responseBody = await response.Content.ReadAsStringAsync();",
                "                Console.WriteLine($\"Response: {responseBody}\");",
                "            }",
                "            catch (APIClientException e)",
                "            {",
                "                Console.Error.WriteLine($\"Request Failed: {e.Message}\");",
                "            }"
            ])
            lines.append("")

        lines.append("        }")
        lines.append("    }")
        lines.append("}")

        return "\n".join(lines)
