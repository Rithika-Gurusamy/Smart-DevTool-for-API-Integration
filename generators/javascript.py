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
            "class NetworkError extends APIClientError {}",
            "class TimeoutError extends APIClientError {}",
            "",
            "class HttpClient {",
            "    constructor(baseUrl, authStrategy, credentials, maxRetries = 3, enableLogging = false) {",
            "        this.baseUrl = baseUrl.replace(/\\/$/, '');",
            "        this.authStrategy = authStrategy;",
            "        this.credentials = credentials;",
            "        this.maxRetries = maxRetries;",
            "        this.enableLogging = enableLogging;",
            "        this.client = axios.create({",
            "            baseURL: this.baseUrl,",
            "            headers: {",
            "                'Content-Type': 'application/json',",
            "                'Accept': 'application/json'",
            "            }",
            "        });",
            "        this._applyAuth();",
            "        this._setupInterceptors();",
            "    }",
            "",
            "    _applyAuth() {",
            "        if (this.authStrategy === 'Bearer Token') {",
            "            this.client.defaults.headers.common['Authorization'] = `Bearer ${this.credentials.token}`;",
            "        } else if (this.authStrategy === 'API Key') {",
            "            this.client.defaults.headers.common['X-API-Key'] = this.credentials.apiKey;",
            "        } else if (this.authStrategy === 'Basic Auth') {",
            "            const authString = Buffer.from(`${this.credentials.username}:${this.credentials.password || ''}`).toString('base64');",
            "            this.client.defaults.headers.common['Authorization'] = `Basic ${authString}`;",
            "        }",
            "    }",
            "",
            "    _log(level, msg) {",
            "        if (this.enableLogging) {",
            "            console.log(`[${level}] ${msg}`);",
            "        }",
            "    }",
            "",
            "    _setupInterceptors() {",
            "        this.client.interceptors.request.use(",
            "            (config) => {",
            "                config.headers['X-Request-ID'] = `req_${Date.now()}`;",
            "                this._log('DEBUG', `Request: ${config.method.toUpperCase()} ${config.url}`);",
            "                return config;",
            "            },",
            "            (error) => Promise.reject(error)",
            "        );",
            "",
            "        this.client.interceptors.response.use(",
            "            (response) => {",
            "                this._log('DEBUG', `Response Success: ${response.status}`);",
            "                return response;",
            "            },",
            "            async (error) => {",
            "                const originalRequest = error.config;",
            "                const status = error.response ? error.response.status : null;",
            "                originalRequest._retryCount = originalRequest._retryCount || 0;",
            "                ",
            "                if (status === 429 && originalRequest._retryCount < this.maxRetries) {",
            "                    originalRequest._retryCount++;",
            "                    const retryAfter = error.response.headers['retry-after'];",
            "                    let delay = Math.pow(2, originalRequest._retryCount) * 1000;",
            "                    if (retryAfter) {",
            "                        delay = isNaN(retryAfter) ? Date.parse(retryAfter) - Date.now() : parseInt(retryAfter, 10) * 1000;",
            "                        if (delay < 0) delay = 1000;",
            "                    }",
            "                    this._log('WARNING', `429 Rate Limit. Retrying in ${delay}ms...`);",
            "                    await new Promise(resolve => setTimeout(resolve, delay));",
            "                    return this.client(originalRequest);",
            "                }",
            "",
            "                const isTransient = status === 502 || status === 503 || status === 504 || !status;",
            "                if (isTransient && originalRequest._retryCount < this.maxRetries) {",
            "                    originalRequest._retryCount++;",
            "                    const delay = Math.pow(2, originalRequest._retryCount) * 1000;",
            "                    this._log('WARNING', `Transient error ${status || 'Network'}. Retrying in ${delay}ms...`);",
            "                    await new Promise(resolve => setTimeout(resolve, delay));",
            "                    return this.client(originalRequest);",
            "                }",
            "",
            "                if (status === 401 && this.credentials.refreshToken) {",
            "                    this._log('INFO', '401 Unauthorized. Attempting token refresh...');",
            "                    return this.client(originalRequest);",
            "                }",
            "",
            "                return Promise.reject(error);",
            "            }",
            "        );",
            "    }",
            "",
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
            "            if (error.code === 'ECONNABORTED') {",
            "                throw new TimeoutError(`Request timed out: ${error.message}`);",
            "            }",
            "            throw new NetworkError(`Network failed: ${error.message}`);",
            "        }",
            "    }",
            "}",
            "",
            f"class {class_name} extends HttpClient {{",
        ]

        # Constructor
        if auth_type == "Bearer Token":
            lines.extend([
                "    constructor(token, baseUrl = 'https://api.example.com', maxRetries = 3, enableLogging = false) {",
                "        const activeToken = token || process.env.API_TOKEN;",
                "        if (!activeToken) {",
                "            throw new AuthenticationError('Authentication token must be provided.');",
                "        }",
                "        super(baseUrl, 'Bearer Token', { token: activeToken }, maxRetries, enableLogging);",
                "    }"
            ])
        else:
            lines.extend([
                "    constructor(apiKey, baseUrl = 'https://api.example.com', maxRetries = 3, enableLogging = false) {",
                "        const activeKey = apiKey || process.env.API_KEY;",
                "        if (!activeKey) {",
                "            throw new AuthenticationError('API Key must be provided.');",
                "        }",
                "        super(baseUrl, 'API Key', { apiKey: activeKey }, maxRetries, enableLogging);",
                "    }"
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
