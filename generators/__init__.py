from generators.python import PythonSDKGenerator
from generators.javascript import JavaScriptSDKGenerator

def get_generator(language: str, api_key: str = None):
    """
    Factory function to get the appropriate SDK generator.
    """
    lang = language.lower().strip()
    
    if lang == "python":
        return PythonSDKGenerator(api_key=api_key)
    elif lang in ["javascript", "typescript"]:
        # Share javascript structure or we can map typescript specifically in future
        return JavaScriptSDKGenerator(api_key=api_key)
    else:
        # Fallback to python as the primary language or a base generator
        return PythonSDKGenerator(api_key=api_key)
