from generators.python import PythonSDKGenerator
from generators.javascript import JavaScriptSDKGenerator
from generators.rest_python import PythonRESTGenerator
from generators.rest_javascript import JavaScriptRESTGenerator

def get_generator(language: str, api_key: str = None):
    """
    Factory function to get the appropriate SDK generator.
    """
    lang = language.lower().strip()
    
    if lang == "python":
        return PythonSDKGenerator(api_key=api_key)
    elif lang in ["javascript", "typescript"]:
        return JavaScriptSDKGenerator(api_key=api_key)
    else:
        return PythonSDKGenerator(api_key=api_key)

def get_rest_generator(language: str, api_key: str = None):
    """
    Factory function to get the appropriate REST generator.
    """
    lang = language.lower().strip()
    
    if lang == "python":
        return PythonRESTGenerator(api_key=api_key)
    elif lang in ["javascript", "typescript"]:
        return JavaScriptRESTGenerator(api_key=api_key)
    else:
        return PythonRESTGenerator(api_key=api_key)
