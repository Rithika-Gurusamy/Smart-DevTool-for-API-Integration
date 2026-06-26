from generators.target_stacks.base import BaseTargetStackGenerator
from generators.python import PythonSDKGenerator
from generators.rest_python import PythonRESTGenerator

class GenericPythonGenerator(BaseTargetStackGenerator):
    def generate_sdk(self, api_metadata: dict, use_case: str) -> str:
        gen = PythonSDKGenerator(api_key=self.api_key)
        return gen.generate(api_metadata, use_case)

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        gen = PythonRESTGenerator(api_key=self.api_key)
        return gen.generate_rest(api_metadata, use_case)

    def generate_frontend(self, blueprint: dict) -> dict:
        return {"README.md": "Generic Python Target Stack integration package."}

    def get_folder_structure(self) -> dict:
        return {
            "client/": {
                "__init__.py": None,
                "client.py": None,
                "exceptions.py": None
            }
        }

    def get_framework_features(self) -> list:
        return ["Normalized exceptions mapping", "Centralized requests Session base", "Retries & Rate Limits"]

    def get_generated_assets(self) -> list:
        return ["client.py", "exceptions.py", "README.md"]
