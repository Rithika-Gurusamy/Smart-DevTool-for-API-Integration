import os
import sys
import json

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from spec_parser import detect_and_parse_spec, SpecParserError
from diff_engine import OpenAPIDiffEngine, generate_markdown_report

def test_postman_parsing():
    print("Testing Postman Collection Programmatic Parser...")
    
    postman_data = {
        "info": {
            "_postman_id": "12345",
            "name": "Ecom Test Collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [
            {
                "name": "Create Customer",
                "request": {
                    "method": "POST",
                    "header": [
                        {"key": "Content-Type", "value": "application/json"}
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": "{\"email\": \"john@example.com\", \"firstName\": \"John\"}"
                    },
                    "url": {
                        "raw": "https://api.example.com/v1/customers",
                        "protocol": "https",
                        "host": ["api", "example", "com"],
                        "path": ["v1", "customers"]
                    },
                    "description": "Create a new customer profile."
                }
            },
            {
                "name": "Get Products",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "https://api.example.com/v1/products?limit=10",
                        "protocol": "https",
                        "host": ["api", "example", "com"],
                        "path": ["v1", "products"],
                        "query": [
                            {"key": "limit", "value": "10"}
                        ]
                    },
                    "description": "List all products."
                }
            }
        ]
    }
    
    parsed = detect_and_parse_spec(json.dumps(postman_data))
    
    assert parsed["spec_type"] == "postman"
    assert parsed["metadata"]["title"] == "Ecom Test Collection"
    assert len(parsed["endpoints"]) == 2
    
    # Verify Create Customer endpoint
    post_ep = [ep for ep in parsed["endpoints"] if ep["method"] == "POST"][0]
    assert post_ep["path"] == "/v1/customers"
    assert post_ep["request_body_schema"] is not None
    assert "email" in post_ep["request_body_schema"]["schema"]["properties"]
    
    print("[OK] Postman Collection programmatic parser works perfectly.")

def test_unstructured_diff():
    print("Testing Diff Engine with different spec inputs...")
    
    # Old V1: Postman collection representing baseline API
    v1_postman = {
        "info": {
            "name": "Ecom API V1",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [
            {
                "name": "List Users",
                "request": {
                    "method": "GET",
                    "url": {
                        "path": ["users"]
                    }
                }
            }
        ]
    }
    
    # New V2: OpenAPI specification representing upgraded API (adding an endpoint)
    v2_openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Ecom API V2",
            "version": "2.0.0"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "List Users",
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get User Detail",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "OK"}}
                }
            }
        }
    }
    
    v1_parsed = detect_and_parse_spec(json.dumps(v1_postman))
    v2_parsed = detect_and_parse_spec(json.dumps(v2_openapi))
    
    # Compare Postman V1 spec against OpenAPI V2 spec!
    engine = OpenAPIDiffEngine(v1_parsed, v2_parsed, v1_postman, v2_openapi, api_key="")
    report = engine.compare()
    
    print(f"Compatibility Score: {report['compatibility_score']}%")
    print(f"Changes count: {len(report['changes'])}")
    
    # We should have Endpoint Added (/users/{id}) and API Version Changed
    categories = [c["change_category"] for c in report["changes"]]
    assert "Endpoint Added" in categories
    assert "API Version Changed" in categories
    
    print("[OK] Mixed-format (Postman vs OpenAPI) diff comparison passes successfully!")

if __name__ == "__main__":
    test_postman_parsing()
    test_unstructured_diff()
    print("All Extended Parser Tests Passed successfully!")
