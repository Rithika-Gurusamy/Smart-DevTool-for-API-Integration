from generators.target_stacks.base import BaseTargetStackGenerator
import importlib

# Mapping of Language -> List of Supported Target Stacks
LANGUAGE_STACKS = {
    "Python": ["Generic Python", "Flask", "FastAPI", "Django"],
    "JavaScript": ["Vanilla JavaScript", "React", "Next.js", "Vue", "Angular", "Node.js", "Express"],
    "TypeScript": ["Vanilla JavaScript", "React", "Next.js", "Vue", "Angular", "Node.js", "Express"],
    "Java": ["Generic Java", "Spring Boot", "Jakarta EE"],
    "C#": ["Generic .NET", "ASP.NET Core", "Blazor"]
}

def get_stack_generator(stack_name: str, api_key: str = None) -> BaseTargetStackGenerator:
    """
    Dynamically loads and instantiates the target stack generator class.
    This pluggable factory approach keeps modules separate and easy to extend.
    """
    name_clean = stack_name.lower().strip()
    
    # Map stack string names to their respective module and class names
    mapping = {
        "generic python": ("generators.target_stacks.generic_python", "GenericPythonGenerator"),
        "flask": ("generators.target_stacks.flask", "FlaskGenerator"),
        "fastapi": ("generators.target_stacks.fastapi", "FastAPIGenerator"),
        "django": ("generators.target_stacks.generic_python", "GenericPythonGenerator"), # fallback to generic py
        
        "vanilla javascript": ("generators.target_stacks.generic_javascript", "GenericJavaScriptGenerator"),
        "react": ("generators.target_stacks.react", "ReactGenerator"),
        "next.js": ("generators.target_stacks.react", "ReactGenerator"), # Next.js maps to React
        "vue": ("generators.target_stacks.vue", "VueGenerator"),
        "angular": ("generators.target_stacks.angular", "AngularGenerator"),
        "node.js": ("generators.target_stacks.generic_javascript", "GenericJavaScriptGenerator"),
        "express": ("generators.target_stacks.express", "ExpressGenerator"),
        
        "generic java": ("generators.target_stacks.generic_java", "GenericJavaGenerator"),
        "spring boot": ("generators.target_stacks.springboot", "SpringBootGenerator"),
        "jakarta ee": ("generators.target_stacks.generic_java", "GenericJavaGenerator"),
        
        "generic .net": ("generators.target_stacks.generic_net", "GenericNetGenerator"),
        "asp.net core": ("generators.target_stacks.aspnet", "ASPNETCoreGenerator"),
        "blazor": ("generators.target_stacks.generic_net", "GenericNetGenerator")
    }
    
    module_path, class_name = mapping.get(name_clean, ("generators.target_stacks.generic_python", "GenericPythonGenerator"))
    
    try:
        mod = importlib.import_module(module_path)
        gen_cls = getattr(mod, class_name)
        return gen_cls(api_key=api_key)
    except Exception as e:
        print(f"Error loading target stack generator {class_name}: {str(e)}")
        # Ultimate fallback
        from generators.target_stacks.generic_python import GenericPythonGenerator
        return GenericPythonGenerator(api_key=api_key)

def validate_compatibility(language: str, stack_name: str) -> bool:
    """
    Validates if the selected target stack is compatible with the selected language.
    """
    lang_clean = language.strip()
    stacks = LANGUAGE_STACKS.get(lang_clean, [])
    if not stacks:
        # Check case insensitively
        for k, v in LANGUAGE_STACKS.items():
            if k.lower() == lang_clean.lower():
                stacks = v
                break
    return any(s.lower() == stack_name.lower().strip() for s in stacks)
