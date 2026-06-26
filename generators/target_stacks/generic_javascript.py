from generators.target_stacks.base import BaseTargetStackGenerator
from generators.javascript import JavaScriptSDKGenerator
from generators.rest_javascript import JavaScriptRESTGenerator
from frontend_generator import generate_base_javascript_files

class GenericJavaScriptGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        gen = JavaScriptSDKGenerator(api_key=self.api_key)
        return gen.generate(api_metadata, use_case)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        gen = JavaScriptRESTGenerator(api_key=self.api_key)
        return gen.generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        files, _ = generate_base_javascript_files(blueprint)
        return files

    def get_folder_structure(self) -> dict:
        return {
            "src/": {
                "api/": {
                    "config/": {"apiConfig.js": None},
                    "constants/": {"apiRoutes.js": None},
                    "models/": {"Customer.js": None},
                    "services/": {"customerService.js": None},
                    "apiClient.js": None,
                    "errorUtils.js": None
                }
            }
        }

    def get_framework_features(self) -> list:
        return ["Centralized Axios HttpClient wrapper", "Request/Response interceptor chains", "Transient retries & Logging"]

    def get_generated_assets(self) -> list:
        return ["apiClient.js", "errorUtils.js", "apiRoutes.js", "apiConfig.js", ".env.example"]
