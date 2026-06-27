import os
import sys
import json

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from diff_engine import OpenAPIDiffEngine, generate_markdown_report, generate_pdf_report
from spec_parser import detect_and_parse_spec

def test_evolution_diff():
    print("Testing API Specification Diff Engine...")
    
    # Define V1 spec
    v1_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Stripe-like Payment API",
            "version": "1.0.0"
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization"
                }
            },
            "schemas": {
                "Customer": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "email": {"type": "string"},
                        "age": {"type": "integer"}
                    },
                    "required": ["id", "email"]
                }
            }
        },
        "paths": {
            "/v1/customers": {
                "post": {
                    "summary": "Create Customer",
                    "operationId": "createCustomer",
                    "parameters": [
                        {
                            "name": "X-Request-Id",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Customer"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Success response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Customer"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Define V2 spec (with breaking changes, warnings, and safe additions)
    v2_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Stripe-like Payment API",
            "version": "2.0.0"
        },
        "components": {
            "securitySchemes": {
                # Security scheme changed from apiKey to oauth2 (Breaking!)
                "ApiKeyAuth": {
                    "type": "oauth2",
                    "flows": {}
                }
            },
            "schemas": {
                "Customer": {
                    "type": "object",
                    "properties": {
                        # email removed (Breaking response / warning request field removed!)
                        "id": {"type": "string"},
                        # age type changed from integer to string (Breaking!)
                        "age": {"type": "string"},
                        # phone added as required request property (Warning required field added!)
                        "phone": {"type": "string"},
                        # status added as optional request / new response property (Safe!)
                        "status": {"type": "string"}
                    },
                    "required": ["id", "phone"]
                }
            }
        },
        "paths": {
            # Route changed from /v1/customers to /v2/customers (matched via operationId)
            "/v2/customers": {
                "post": {
                    "summary": "Create Customer",
                    "operationId": "createCustomer",
                    "parameters": [
                        # Required header X-Request-Id removed (Warning parameter removed!)
                        # Optional query param limit added (Safe!)
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Customer"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Success response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Customer"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            # New endpoint added (Safe!)
            "/v2/refunds": {
                "post": {
                    "summary": "Refund Charge",
                    "operationId": "createRefund",
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            }
        }
    }
    
    # Normalize with spec_parser
    v1_parsed = detect_and_parse_spec(json.dumps(v1_spec))
    v2_parsed = detect_and_parse_spec(json.dumps(v2_spec))
    
    # Run comparison
    engine = OpenAPIDiffEngine(v1_parsed, v2_parsed, v1_spec, v2_spec, api_key="") # Offline check
    report = engine.compare()
    
    print(f"Comparison Score: {report.get('compatibility_score')}%")
    print(f"Metrics: {report.get('metrics')}")
    
    # Verify change list
    changes = report.get("changes", [])
    assert len(changes) > 0, "No changes detected"
    
    categories = [c["change_category"] for c in changes]
    print("Detected categories:", categories)
    
    # Assert specific changes
    assert any("Version Changed" in cat for cat in categories), "Version change not detected"
    assert any("Authentication Scheme Changed" in cat for cat in categories), "Security scheme type change not detected"
    assert any("Endpoint Path/Method Changed" in cat for cat in categories), "Endpoint path update not detected via operationId"
    assert any("Endpoint Added" in cat for cat in categories), "Refund endpoint addition not detected"
    assert any("Response Field Removed" in cat for cat in categories), "Response field deletion not detected"
    assert any("Field Type Changed" in cat for cat in categories), "Property type change not detected"
    
    print("[OK] Diff structural checks passed.")
    
    # Test exporters
    print("Testing Markdown report generation...")
    md_report = generate_markdown_report(report)
    assert "# API Evolution & Breaking Change Report" in md_report, "Markdown missing title"
    print("[OK] Markdown generation passed.")
    
    print("Testing PDF report generation...")
    pdf_bytes = generate_pdf_report(report)
    assert len(pdf_bytes) > 100, "PDF generation returned empty/too small document"
    print("[OK] PDF generation passed.")

if __name__ == "__main__":
    test_evolution_diff()
    print("All Automated Diff Engine Tests Passed successfully!")
