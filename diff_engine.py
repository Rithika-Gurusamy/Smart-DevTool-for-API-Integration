import os
import json
import io
import re
import importlib
import yaml
from dotenv import load_dotenv

# Try to import ReportLab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Try to import Gemini
try:
    genai = importlib.import_module("google.generativeai")
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if api_key and HAS_GEMINI:
    genai.configure(api_key=api_key)


class BaseDiffEngine:
    def compare(self) -> dict:
        raise NotImplementedError


class OpenAPIDiffEngine(BaseDiffEngine):
    def __init__(self, old_spec: dict, new_spec: dict, old_raw: dict, new_raw: dict, api_key: str = None):
        self.old_spec = old_spec
        self.new_spec = new_spec
        self.old_raw = old_raw
        self.new_raw = new_raw
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GEMINI_API_KEY")

    def compare(self) -> dict:
        changes = []
        
        # 1. Global metadata diff
        old_meta = self.old_spec.get("metadata", {})
        new_meta = self.new_spec.get("metadata", {})
        
        old_ver = old_meta.get("version", "1.0.0")
        new_ver = new_meta.get("version", "1.0.0")
        if old_ver != new_ver:
            changes.append({
                "path": "API Metadata",
                "method": "META",
                "change_category": "API Version Changed",
                "previous_value": old_ver,
                "new_value": new_ver,
                "classification": "Safe"
            })

        # 2. Authentication diff
        old_auth = self.old_spec.get("authentication", [])
        new_auth = self.new_spec.get("authentication", [])
        
        old_auth_map = {item.get("name", "default"): item for item in old_auth}
        new_auth_map = {item.get("name", "default"): item for item in new_auth}
        
        for name, item in old_auth_map.items():
            if name not in new_auth_map:
                changes.append({
                    "path": "Authentication",
                    "method": "AUTH",
                    "change_category": "Authentication Scheme Removed",
                    "previous_value": f"{item.get('type')} ({name})",
                    "new_value": None,
                    "classification": "Breaking"
                })
            else:
                new_item = new_auth_map[name]
                if item.get("type") != new_item.get("type") or item.get("in") != new_item.get("in"):
                    changes.append({
                        "path": "Authentication",
                        "method": "AUTH",
                        "change_category": "Authentication Scheme Changed",
                        "previous_value": f"{item.get('type')} in {item.get('in')}",
                        "new_value": f"{new_item.get('type')} in {new_item.get('in')}",
                        "classification": "Breaking"
                    })
                    
        for name, item in new_auth_map.items():
            if name not in old_auth_map:
                changes.append({
                    "path": "Authentication",
                    "method": "AUTH",
                    "change_category": "Authentication Scheme Added",
                    "previous_value": None,
                    "new_value": f"{item.get('type')} ({name})",
                    "classification": "Safe"
                })

        # 3. Endpoint Comparison
        old_endpoints = self.old_spec.get("endpoints", [])
        new_endpoints = self.new_spec.get("endpoints", [])
        
        old_eps_map = {(ep["method"], ep["path"]): ep for ep in old_endpoints}
        new_eps_map = {(ep["method"], ep["path"]): ep for ep in new_endpoints}
        
        # Track resolved endpoints via operationId mapping
        old_op_map = {ep["operation_id"]: ep for ep in old_endpoints if ep.get("operation_id")}
        new_op_map = {ep["operation_id"]: ep for ep in new_endpoints if ep.get("operation_id")}
        
        matched_old_eps = set()
        matched_new_eps = set()
        
        # Check for path/method renames via operationId matches
        for op_id, old_ep in old_op_map.items():
            if op_id in new_op_map:
                new_ep = new_op_map[op_id]
                old_key = (old_ep["method"], old_ep["path"])
                new_key = (new_ep["method"], new_ep["path"])
                
                if old_key != new_key:
                    changes.append({
                        "path": new_ep["path"],
                        "method": new_ep["method"],
                        "change_category": "Endpoint Path/Method Changed",
                        "previous_value": f"{old_ep['method']} {old_ep['path']}",
                        "new_value": f"{new_ep['method']} {new_ep['path']}",
                        "classification": "Breaking"
                    })
                    # Compare details
                    changes.extend(self._compare_endpoint_details(old_ep, new_ep))
                    matched_old_eps.add(old_key)
                    matched_new_eps.add(new_key)
                    
        # Check exact path/method matches
        for old_key, old_ep in old_eps_map.items():
            if old_key in matched_old_eps:
                continue
            if old_key in new_eps_map:
                new_ep = new_eps_map[old_key]
                changes.extend(self._compare_endpoint_details(old_ep, new_ep))
                matched_old_eps.add(old_key)
                matched_new_eps.add(old_key)
            else:
                changes.append({
                    "path": old_ep["path"],
                    "method": old_ep["method"],
                    "change_category": "Endpoint Removed",
                    "previous_value": f"{old_ep['method']} {old_ep['path']}",
                    "new_value": None,
                    "classification": "Breaking"
                })
                matched_old_eps.add(old_key)
                
        # Add remaining new endpoints
        for new_key, new_ep in new_eps_map.items():
            if new_key not in matched_new_eps:
                changes.append({
                    "path": new_ep["path"],
                    "method": new_ep["method"],
                    "change_category": "Endpoint Added",
                    "previous_value": None,
                    "new_value": f"{new_ep['method']} {new_ep['path']}",
                    "classification": "Safe"
                })
                
        # 4. Attach default programmatic descriptions and impact mappings
        for c in changes:
            self._fill_programmatic_impact(c)
            
        # 5. Compatibility Score calculation
        breaking_count = sum(1 for c in changes if c["classification"] == "Breaking")
        warning_count = sum(1 for c in changes if c["classification"] == "Warning")
        safe_count = sum(1 for c in changes if c["classification"] == "Safe")
        
        deduction = (breaking_count * 10) + (warning_count * 3)
        score = max(0, 100 - deduction)
        
        report = {
            "compatibility_score": score,
            "metrics": {
                "total_changes": len(changes),
                "breaking_changes": breaking_count,
                "warnings": warning_count,
                "safe_changes": safe_count
            },
            "changes": changes,
            "executive_summary": f"We compared the two specifications. We identified {breaking_count} breaking changes, {warning_count} warnings, and {safe_count} safe changes. The overall compatibility score is {score}%.",
            "upgrade_risks": self._generate_default_risks(breaking_count, warning_count)
        }
        
        # 6. Try to enrich with Gemini if available
        if self.api_key and HAS_GEMINI:
            enriched = self._enrich_with_gemini(report)
            if enriched:
                report = enriched
                
        return report

    def _compare_endpoint_details(self, old_ep: dict, new_ep: dict) -> list:
        changes = []
        path = new_ep["path"]
        method = new_ep["method"]
        
        # A. Compare Parameters (Headers, Query params, path vars)
        old_params = { (p.get("name"), p.get("in")): p for p in old_ep.get("parameters", []) }
        new_params = { (p.get("name"), p.get("in")): p for p in new_ep.get("parameters", []) }
        
        for (name, pin), p in old_params.items():
            if (name, pin) not in new_params:
                changes.append({
                    "path": path,
                    "method": method,
                    "change_category": f"Parameter Removed ({pin})",
                    "previous_value": f"{name} (required={p.get('required')})",
                    "new_value": None,
                    "classification": "Warning"
                })
            else:
                new_p = new_params[(name, pin)]
                if p.get("type") != new_p.get("type"):
                    changes.append({
                        "path": path,
                        "method": method,
                        "change_category": f"Parameter Type Changed ({pin})",
                        "previous_value": f"{name} (type={p.get('type')})",
                        "new_value": f"type={new_p.get('type')}",
                        "classification": "Breaking"
                    })
                if not p.get("required") and new_p.get("required"):
                    changes.append({
                        "path": path,
                        "method": method,
                        "change_category": f"Parameter Made Required ({pin})",
                        "previous_value": f"{name} (optional)",
                        "new_value": "required",
                        "classification": "Breaking"
                    })
                elif p.get("required") and not new_p.get("required"):
                    changes.append({
                        "path": path,
                        "method": method,
                        "change_category": f"Parameter Made Optional ({pin})",
                        "previous_value": f"{name} (required)",
                        "new_value": "optional",
                        "classification": "Safe"
                    })
                    
        for (name, pin), p in new_params.items():
            if (name, pin) not in old_params:
                is_req = p.get("required", False)
                changes.append({
                    "path": path,
                    "method": method,
                    "change_category": f"Parameter Added ({pin})",
                    "previous_value": None,
                    "new_value": f"{name} (required={is_req})",
                    "classification": "Warning" if is_req else "Safe"
                })
                
        # B. Compare Request Body Schema
        old_body = old_ep.get("request_body_schema")
        new_body = new_ep.get("request_body_schema")
        
        if old_body and new_body:
            changes.extend(self._diff_schemas(
                old_body.get("schema", {}),
                new_body.get("schema", {}),
                path,
                method,
                is_request=True
            ))
        elif not old_body and new_body:
            # Check if new request body has required fields
            new_schema = new_body.get("schema", {})
            required_fields = new_schema.get("required", [])
            has_req = len(required_fields) > 0
            changes.append({
                "path": path,
                "method": method,
                "change_category": "Request Body Added",
                "previous_value": None,
                "new_value": "required payload" if has_req else "optional payload",
                "classification": "Warning" if has_req else "Safe"
            })
        elif old_body and not new_body:
            changes.append({
                "path": path,
                "method": method,
                "change_category": "Request Body Removed",
                "previous_value": "request payload",
                "new_value": None,
                "classification": "Warning"
            })
            
        # C. Compare Responses
        old_resps = old_ep.get("responses", {})
        new_resps = new_ep.get("responses", {})
        
        for status, old_resp in old_resps.items():
            if status not in new_resps:
                # Removing success codes is breaking
                is_breaking = status.startswith("2")
                changes.append({
                    "path": path,
                    "method": method,
                    "change_category": "Response Status Code Removed",
                    "previous_value": f"Status {status}",
                    "new_value": None,
                    "classification": "Breaking" if is_breaking else "Safe"
                })
            else:
                # Compare Response Schema
                old_raw_resp = self._get_raw_response(self.old_raw, old_ep["path"], method, status)
                new_raw_resp = self._get_raw_response(self.new_raw, new_ep["path"], method, status)
                
                old_schema = self._get_schema_from_raw_resp(old_raw_resp, self.old_raw)
                new_schema = self._get_schema_from_raw_resp(new_raw_resp, self.new_raw)
                
                if old_schema or new_schema:
                    changes.extend(self._diff_schemas(
                        old_schema,
                        new_schema,
                        path,
                        method,
                        is_request=False,
                        path_prefix=f"Response {status}"
                    ))
                    
        for status, new_resp in new_resps.items():
            if status not in old_resps:
                changes.append({
                    "path": path,
                    "method": method,
                    "change_category": "Response Status Code Added",
                    "previous_value": None,
                    "new_value": f"Status {status}",
                    "classification": "Safe"
                })
                
        return changes

    def _resolve_schema(self, schema_or_ref, raw_spec) -> dict:
        if not isinstance(schema_or_ref, dict):
            return {}
        if "$ref" in schema_or_ref:
            ref_path = schema_or_ref["$ref"]
            if not ref_path.startswith("#/"):
                return {}
            parts = ref_path.split("/")[1:]
            current = raw_spec
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return {}
            if isinstance(current, dict) and "$ref" in current:
                return self._resolve_schema(current, raw_spec)
            return current
        return schema_or_ref

    def _diff_schemas(self, old_schema, new_schema, path, method, is_request=True, path_prefix="") -> list:
        changes = []
        old_res = self._resolve_schema(old_schema, self.old_raw)
        new_res = self._resolve_schema(new_schema, self.new_raw)
        
        old_type = old_res.get("type", "object")
        new_type = new_res.get("type", "object")
        
        if old_type != new_type:
            changes.append({
                "path": path,
                "method": method,
                "change_category": f"{path_prefix} Schema Type Changed" if path_prefix else "Schema Type Changed",
                "previous_value": f"type={old_type}",
                "new_value": f"type={new_type}",
                "classification": "Breaking"
            })
            return changes
            
        if old_type == "object" or "properties" in old_res or "properties" in new_res:
            old_props = old_res.get("properties", {})
            new_props = new_res.get("properties", {})
            
            old_req = old_res.get("required", [])
            new_req = new_res.get("required", [])
            
            # Properties added
            for prop, prop_schema in new_props.items():
                if prop not in old_props:
                    prop_name = f"{path_prefix}.{prop}" if path_prefix else prop
                    is_req = prop in new_req
                    
                    if is_request:
                        cat = "Required Request Field Added" if is_req else "Optional Request Field Added"
                        sev = "Warning" if is_req else "Safe"
                    else:
                        cat = "Response Field Added"
                        sev = "Safe"
                        
                    changes.append({
                        "path": path,
                        "method": method,
                        "change_category": cat,
                        "previous_value": None,
                        "new_value": f"{prop_name} (type={prop_schema.get('type', 'any')})",
                        "classification": sev
                    })
                    
            # Properties removed
            for prop, prop_schema in old_props.items():
                if prop not in new_props:
                    prop_name = f"{path_prefix}.{prop}" if path_prefix else prop
                    is_req = prop in old_req
                    
                    if is_request:
                        cat = "Request Field Removed"
                        sev = "Warning"
                    else:
                        cat = "Response Field Removed"
                        sev = "Breaking"
                        
                    changes.append({
                        "path": path,
                        "method": method,
                        "change_category": cat,
                        "previous_value": f"{prop_name} (type={prop_schema.get('type', 'any')})",
                        "new_value": None,
                        "classification": sev
                    })
                    
            # Type and validation updates for common properties
            for prop in old_props:
                if prop in new_props:
                    prop_name = f"{path_prefix}.{prop}" if path_prefix else prop
                    old_p_schema = old_props[prop]
                    new_p_schema = new_props[prop]
                    
                    old_p_resolved = self._resolve_schema(old_p_schema, self.old_raw)
                    new_p_resolved = self._resolve_schema(new_p_schema, self.new_raw)
                    
                    old_p_type = old_p_resolved.get("type")
                    new_p_type = new_p_resolved.get("type")
                    
                    if old_p_type and new_p_type and old_p_type != new_p_type:
                        changes.append({
                            "path": path,
                            "method": method,
                            "change_category": "Request Field Type Changed" if is_request else "Response Field Type Changed",
                            "previous_value": f"{prop_name} (type={old_p_type})",
                            "new_value": f"type={new_p_type}",
                            "classification": "Breaking"
                        })
                    else:
                        # Check validation rule changes
                        val_fields = ["minLength", "maxLength", "minimum", "maximum", "pattern"]
                        for val_field in val_fields:
                            if old_p_resolved.get(val_field) != new_p_resolved.get(val_field):
                                prev_val = f"{val_field}={old_p_resolved.get(val_field)}" if old_p_resolved.get(val_field) is not None else None
                                new_val = f"{val_field}={new_p_resolved.get(val_field)}" if new_p_resolved.get(val_field) is not None else None
                                changes.append({
                                    "path": path,
                                    "method": method,
                                    "change_category": "Request Validation Changed" if is_request else "Response Validation Changed",
                                    "previous_value": f"{prop_name} ({prev_val or 'none'})",
                                    "new_value": new_val or 'removed',
                                    "classification": "Warning"
                                })
                                break # just flag one validation change per property
                                
                    # Required flag changes
                    was_req = prop in old_req
                    is_req = prop in new_req
                    if not was_req and is_req:
                        changes.append({
                            "path": path,
                            "method": method,
                            "change_category": "Request Field Made Required" if is_request else "Response Field Made Required",
                            "previous_value": f"{prop_name} (optional)",
                            "new_value": "required",
                            "classification": "Breaking" if is_request else "Safe"
                        })
                    elif was_req and not is_req:
                        changes.append({
                            "path": path,
                            "method": method,
                            "change_category": "Request Field Made Optional" if is_request else "Response Field Made Optional",
                            "previous_value": f"{prop_name} (required)",
                            "new_value": "optional",
                            "classification": "Safe" if is_request else "Warning" # response field made optional is a warning (clients might expect it)
                        })
                        
        return changes

    def _get_raw_response(self, raw_spec: dict, path: str, method: str, status_code: str) -> dict:
        paths = raw_spec.get("paths", {})
        path_item = paths.get(path, {})
        op = path_item.get(method.lower(), path_item.get(method.upper(), {}))
        responses = op.get("responses", {})
        return responses.get(str(status_code), responses.get(int(status_code) if status_code.isdigit() else status_code, {}))

    def _get_schema_from_raw_resp(self, raw_resp: dict, raw_spec: dict) -> dict:
        if not isinstance(raw_resp, dict):
            return {}
        if "schema" in raw_resp:
            return raw_resp["schema"]
        elif "content" in raw_resp:
            content = raw_resp["content"]
            for m_type, m_item in content.items():
                if "schema" in m_item:
                    return m_item["schema"]
        return {}

    def _fill_programmatic_impact(self, change: dict):
        cat = change["change_category"].lower()
        method = change.get("method", "GET")
        path = change.get("path", "")
        prev = change.get("previous_value")
        new = change.get("new_value")
        
        if "endpoint removed" in cat:
            change["description"] = f"The endpoint '{method} {path}' has been deleted from the API specification."
            change["frontend_impact"] = "Generated service files will have invalid API endpoints, causing 404 errors."
            change["sdk_impact"] = "SDK client wrapper class will lose this method, causing compilation or runtime exceptions."
            change["recommended_action"] = "Deprecate references to this endpoint in your codebase and find alternative routes."
            
        elif "endpoint added" in cat:
            change["description"] = f"A new endpoint '{method} {path}' is now available."
            change["frontend_impact"] = "None. New features can integrate this service route."
            change["sdk_impact"] = "None. Regenerate the SDK wrapper class to expose this new client method."
            change["recommended_action"] = "Regenerate target integrations to take advantage of this new capability."
            
        elif "path/method changed" in cat:
            change["description"] = f"Endpoint changed from '{prev}' to '{new}'."
            change["frontend_impact"] = "Service routes using the old path will fail with 404 Not Found."
            change["sdk_impact"] = "SDK wrapper method calls will point to the deprecated route, breaking clients."
            change["recommended_action"] = "Update API configuration URLs and regenerate the wrapper class."
            
        elif "authentication scheme removed" in cat:
            change["description"] = f"Authentication scheme '{prev}' has been removed."
            change["frontend_impact"] = "Calls requiring this security scheme will fail with 401 Unauthorized."
            change["sdk_impact"] = "SDK interceptor authentication configuration is outdated and requires cleanup."
            change["recommended_action"] = "Update environment settings to remove or swap this authentication method."
            
        elif "authentication scheme changed" in cat:
            change["description"] = f"Authentication type changed from '{prev}' to '{new}'."
            change["frontend_impact"] = "Centralized Axios client config / interceptors must be updated to inject the new auth format."
            change["sdk_impact"] = "SDK authentication setup must be updated to pass the new credential headers."
            change["recommended_action"] = "Update environment credentials and update headers setup in your API Client class."
            
        elif "required request field added" in cat or "parameter made required" in cat:
            val = new or prev
            change["description"] = f"A required field/parameter '{val}' was added to request."
            change["frontend_impact"] = "Form submissions or service parameters missing this field will fail with 400 Bad Request."
            change["sdk_impact"] = "SDK wrapper method arguments must include this parameter."
            change["recommended_action"] = "Modify client calls to pass the required field '{val}' in the request payload."
            
        elif "request field type changed" in cat or "parameter type changed" in cat:
            val = prev
            change["description"] = f"The parameter type for '{val}' changed to '{new}'."
            change["frontend_impact"] = "Submitting values of the previous type will fail server-side validation rules."
            change["sdk_impact"] = "SDK request wrapper type serialization will fail."
            change["recommended_action"] = "Update variable data types in caller methods and UI state."
            
        elif "response field removed" in cat:
            val = prev
            change["description"] = f"Field '{val}' was removed from response."
            change["frontend_impact"] = "Frontend UI components binding to this response field will render as empty or crash."
            change["sdk_impact"] = "SDK response model class will no longer have this attribute, causing property errors."
            change["recommended_action"] = "Update UI templates and clean up property bindings to `{val}`."
            
        elif "response field type changed" in cat:
            val = prev
            change["description"] = f"The field type for '{val}' changed to '{new}' in the response."
            change["frontend_impact"] = "Frontend UI components or models expecting the previous type will experience parsing failures."
            change["sdk_impact"] = "SDK deserializers will fail to parse response models."
            change["recommended_action"] = "Update response model definitions and UI mapping functions."
            
        else:
            change["description"] = f"Structural diff detected in {change['change_category']}."
            change["frontend_impact"] = "Potential minor updates or model refinements required."
            change["sdk_impact"] = "May require updating client wrapper signatures."
            change["recommended_action"] = "Review the specification changes and update your client integrations."

    def _generate_default_risks(self, breaking: int, warning: int) -> list:
        risks = []
        if breaking > 0:
            risks.append("Risk of client runtime exceptions due to removed endpoints or response fields.")
            risks.append("Authorization failures if authentication requirements or scheme details changed.")
        if warning > 0:
            risks.append("Form submissions failing with validation errors due to new required parameters.")
        if not risks:
            risks.append("Low risk. Upgrades include backward-compatible additions only.")
        return risks

    def _enrich_with_gemini(self, report_data: dict) -> dict:
        prompt = f"""
You are an expert API Architect and Evolution Analyst. Compare the two versions of the API specification and enrich the following structural diff report with detailed context.

Here is the deterministic diff report:
{json.dumps(report_data, indent=2)}

Please enrich this report. You must:
1. Write a clear, comprehensive Executive Summary (2-3 paragraphs) detailing the architectural impact of this upgrade.
2. List the top 3-5 Upgrade Risks for development teams upgrading to this API version.
3. For each item in the "changes" array, enrich the "description", "frontend_impact", "sdk_impact", and "recommended_action" fields with specific context (e.g. refer to actual domain names like Customer, Invoice instead of generic placeholders if they appear in the path or values).

You MUST return your response as a valid JSON object matching the following structure:
{{
    "executive_summary": "Your executive summary...",
    "upgrade_risks": [
        "Risk 1: ...",
        "Risk 2: ..."
    ],
    "changes": [
        {{
            "path": "/v1/charges",
            "method": "POST",
            "change_category": "...",
            "previous_value": "...",
            "new_value": "...",
            "classification": "...",
            "description": "Enriched description...",
            "frontend_impact": "Enriched frontend impact...",
            "sdk_impact": "Enriched SDK impact...",
            "recommended_action": "Enriched recommended action..."
        }}
    ]
}}
Return ONLY the raw JSON object. Do not include markdown wraps (like ```json), HTML tags, or any introductory text. Just the JSON object.
"""
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean markdown wraps
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            enrichment = json.loads(text)
            
            report_data["executive_summary"] = enrichment.get("executive_summary", report_data["executive_summary"])
            report_data["upgrade_risks"] = enrichment.get("upgrade_risks", report_data["upgrade_risks"])
            
            # Map enriched changes by matching path, method, and category
            enriched_changes = enrichment.get("changes", [])
            for ec in enriched_changes:
                for rc in report_data["changes"]:
                    if rc["path"] == ec.get("path") and rc["method"] == ec.get("method") and rc["change_category"] == ec.get("change_category"):
                        rc["description"] = ec.get("description", rc["description"])
                        rc["frontend_impact"] = ec.get("frontend_impact", rc["frontend_impact"])
                        rc["sdk_impact"] = ec.get("sdk_impact", rc["sdk_impact"])
                        rc["recommended_action"] = ec.get("recommended_action", rc["recommended_action"])
                        
            return report_data
        except Exception as e:
            print(f"Gemini API enrichment failed: {str(e)}. Using programmatic fallbacks.")
            return None


def generate_markdown_report(report_data: dict) -> str:
    lines = []
    lines.append("# API Evolution & Breaking Change Report")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(report_data.get("executive_summary", ""))
    lines.append("")
    
    score = report_data.get("compatibility_score", 100)
    lines.append(f"## Version Compatibility Score")
    lines.append(f"**{score}% Compatible**")
    lines.append("")
    
    metrics = report_data.get("metrics", {})
    lines.append("### Summary Metrics")
    lines.append(f"- **Total Changes:** {metrics.get('total_changes', 0)}")
    lines.append(f"- **🔴 Breaking Changes:** {metrics.get('breaking_changes', 0)}")
    lines.append(f"- **🟡 Warnings:** {metrics.get('warnings', 0)}")
    lines.append(f"- **+ Safe Changes:** {metrics.get('safe_changes', 0)}")
    lines.append("")
    
    lines.append("## Upgrade Risks")
    for r in report_data.get("upgrade_risks", []):
        lines.append(f"- {r}")
    lines.append("")
    
    lines.append("## Detailed Change Registry")
    lines.append("")
    
    for idx, c in enumerate(report_data.get("changes", []), 1):
        icon = "🔴"
        if c.get("classification") == "Warning":
            icon = "🟡"
        elif c.get("classification") == "Safe":
            icon = "🟢"
            
        lines.append(f"### {idx}. {icon} {c.get('method', 'GET')} {c.get('path', '')}")
        lines.append(f"- **Change Category:** {c.get('change_category', '')}")
        lines.append(f"- **Severity:** {c.get('classification', '')}")
        lines.append(f"- **Description:** {c.get('description', '')}")
        if c.get("previous_value") is not None:
            lines.append(f"- **Previous Value:** `{c.get('previous_value')}`")
        if c.get("new_value") is not None:
            lines.append(f"- **New Value:** `{c.get('new_value')}`")
        lines.append(f"- **Frontend Impact:** {c.get('frontend_impact', '')}")
        lines.append(f"- **SDK Impact:** {c.get('sdk_impact', '')}")
        lines.append(f"- **Recommended Action:** {c.get('recommended_action', '')}")
        lines.append("")
        
    return "\n".join(lines)


def generate_pdf_report(report_data: dict) -> bytes:
    if not HAS_REPORTLAB:
        buffer = io.BytesIO()
        buffer.write(b"%PDF-1.4 Mock PDF (ReportLab unavailable)")
        return buffer.getvalue()
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1e1b4b'),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#312e81'),
        spaceBefore=15,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    
    bold_body_style = ParagraphStyle(
        'Bold_Body_Custom',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0f172a')
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell_style,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("API Evolution & Breaking Change Report", title_style))
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(report_data.get("executive_summary", ""), body_style))
    
    score = report_data.get("compatibility_score", 100)
    metrics = report_data.get("metrics", {})
    
    story.append(Paragraph("Version Compatibility Score", h2_style))
    story.append(Paragraph(f"Compatibility Score: <b>{score}%</b>", bold_body_style))
    story.append(Paragraph(
        f"Summary: {metrics.get('total_changes')} total changes detected (🔴 {metrics.get('breaking_changes')} breaking, 🟡 {metrics.get('warnings')} warnings, 🟢 {metrics.get('safe_changes')} safe).",
        body_style
    ))
    
    story.append(Paragraph("Upgrade Risks", h2_style))
    for r in report_data.get("upgrade_risks", []):
        story.append(Paragraph(f"&bull; {r}", body_style))
        
    story.append(Spacer(1, 10))
    story.append(Paragraph("Detailed Change Registry", h2_style))
    
    changes = report_data.get("changes", [])
    if not changes:
        story.append(Paragraph("No changes identified.", body_style))
    else:
        # Table headers
        data = [[
            Paragraph("Endpoint", table_cell_bold),
            Paragraph("Category", table_cell_bold),
            Paragraph("Severity", table_cell_bold),
            Paragraph("Frontend Impact", table_cell_bold),
            Paragraph("Action Required", table_cell_bold)
        ]]
        
        for c in changes:
            method = c.get("method", "GET")
            path = c.get("path", "")
            endpoint = f"{method} {path}"
            cat = c.get("change_category", "")
            sev = c.get("classification", "")
            front = c.get("frontend_impact", "")
            rec = c.get("recommended_action", "")
            
            data.append([
                Paragraph(endpoint, table_cell_style),
                Paragraph(cat, table_cell_style),
                Paragraph(sev, table_cell_style),
                Paragraph(front, table_cell_style),
                Paragraph(rec, table_cell_style)
            ])
            
        t = Table(data, colWidths=[100, 100, 50, 130, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(t)
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
