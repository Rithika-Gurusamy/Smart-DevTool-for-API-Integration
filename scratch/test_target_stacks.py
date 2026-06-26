import os
import sys

# Ensure project root is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from generators.target_stacks import (
    get_stack_generator,
    validate_compatibility,
    LANGUAGE_STACKS
)

def test_compatibility():
    print("Testing Compatibility Validations...")
    assert validate_compatibility("Python", "Generic Python") == True
    assert validate_compatibility("Python", "Flask") == True
    assert validate_compatibility("Python", "FastAPI") == True
    assert validate_compatibility("Python", "Django") == True
    
    assert validate_compatibility("JavaScript", "React") == True
    assert validate_compatibility("JavaScript", "Vue") == True
    assert validate_compatibility("JavaScript", "Angular") == True
    
    assert validate_compatibility("Python", "React") == False
    assert validate_compatibility("Java", "Flask") == False
    assert validate_compatibility("C#", "Spring Boot") == False
    print("[OK] Compatibility Validations passed.")

def test_generator_instantiation():
    print("Testing Stack Generator Instantiation...")
    
    # Python stacks
    for stack in ["Generic Python", "Flask", "FastAPI"]:
        gen = get_stack_generator(stack)
        assert gen is not None, f"Failed to instantiate {stack}"
        assert gen.get_framework_features() is not None
        assert gen.get_folder_structure() is not None
        assert gen.get_generated_assets() is not None
        
    # JavaScript/TypeScript stacks
    for stack in ["Vanilla JavaScript", "React", "Vue", "Angular", "Express"]:
        gen = get_stack_generator(stack)
        assert gen is not None, f"Failed to instantiate {stack}"
        assert gen.get_framework_features() is not None
        assert gen.get_folder_structure() is not None
        assert gen.get_generated_assets() is not None
        
    # Java stacks
    for stack in ["Generic Java", "Spring Boot"]:
        gen = get_stack_generator(stack)
        assert gen is not None, f"Failed to instantiate {stack}"
        assert gen.get_framework_features() is not None
        assert gen.get_folder_structure() is not None
        assert gen.get_generated_assets() is not None
        
    # C# stacks
    for stack in ["Generic .NET", "ASP.NET Core"]:
        gen = get_stack_generator(stack)
        assert gen is not None, f"Failed to instantiate {stack}"
        assert gen.get_framework_features() is not None
        assert gen.get_folder_structure() is not None
        assert gen.get_generated_assets() is not None

    print("[OK] Stack Generator Instantiations passed.")

def test_code_generation_fallbacks():
    print("Testing Code Generation Methods...")
    mock_api_metadata = {
        "api_name": "Test Payment API",
        "auth_method": {"type": "API Key", "description": "X-API-Key header auth"},
        "endpoints": [
            {
                "method": "POST",
                "path": "/v1/charges",
                "description": "Create a charge object",
                "category": "Primary",
                "relevance_score": 95,
                "reasoning": "Direct payment charge endpoint"
            },
            {
                "method": "GET",
                "path": "/v1/charges/{id}",
                "description": "Retrieve a charge by ID",
                "category": "Supporting",
                "relevance_score": 80,
                "reasoning": "Inspect past charges"
            }
        ]
    }
    
    mock_blueprint = {
        "api_name": "Test Payment API",
        "framework": "React",
        "configuration_plan": {
            "api_base_url": "https://api.testpayment.com",
            "timeout_ms": 5000,
            "default_headers": {"Content-Type": "application/json"}
        },
        "authentication_plan": {
            "strategy": "API Key",
            "token_storage_suggestion": "localStorage",
            "login_endpoint": "/v1/login",
            "logout_endpoint": "/v1/logout"
        },
        "resource_groups": [
            {
                "name": "Charges",
                "endpoints": [
                    {"method": "POST", "path": "/v1/charges", "description": "Create charge"},
                    {"method": "GET", "path": "/v1/charges/{id}", "description": "Retrieve charge"}
                ]
            }
        ],
        "service_plan": [
            {
                "service_name": "chargesService",
                "description": "Service for charges endpoints",
                "endpoints": ["POST /v1/charges", "GET /v1/charges/{id}"]
            }
        ],
        "model_plan": [
            {
                "model_name": "Charge",
                "description": "Charge data model",
                "fields": {
                    "id": "String",
                    "amount": "Number",
                    "currency": "String",
                    "status": "String"
                }
            }
        ]
    }
    
    # Verify Flask SDK generation
    flask_gen = get_stack_generator("Flask")
    sdk_code = flask_gen.generate_sdk(mock_api_metadata, "Payment flow integration")
    assert "class" in sdk_code or "def" in sdk_code, "Flask SDK generation empty"
    print("[OK] Flask SDK generation check passed.")
    
    # Verify React Frontend files generation
    react_gen = get_stack_generator("React")
    frontend_files = react_gen.generate_frontend(mock_blueprint)
    assert len(frontend_files) > 0, "React Frontend generation failed"
    assert "src/api/hooks/useCharges.js" in frontend_files, "React hooks not generated in hook folder"
    print("[OK] React Frontend files generation check passed.")
    
    # Verify Vue Frontend files generation
    vue_gen = get_stack_generator("Vue")
    vue_files = vue_gen.generate_frontend(mock_blueprint)
    assert len(vue_files) > 0, "Vue Frontend generation failed"
    assert "src/composables/useCharges.js" in vue_files or "src/composables/useCharges.ts" in vue_files, "Vue composables not generated"
    print("[OK] Vue Frontend files generation check passed.")
    
    # Verify Angular Frontend files generation
    angular_gen = get_stack_generator("Angular")
    angular_files = angular_gen.generate_frontend(mock_blueprint)
    assert len(angular_files) > 0, "Angular Frontend generation failed"
    print("[OK] Angular Frontend files generation check passed.")

if __name__ == "__main__":
    test_compatibility()
    test_generator_instantiation()
    test_code_generation_fallbacks()
    print("All Automated Tests Passed successfully!")
