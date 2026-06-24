import re

class BaseSDKGenerator:
    """
    Base class for language-specific SDK wrapper generators.
    """
    def __init__(self):
        pass

    def filter_endpoints(self, endpoints: list) -> list:
        """
        Only return endpoints categorized as Primary or Supporting.
        """
        return [
            ep for ep in endpoints 
            if ep.get("category") in ["Primary", "Supporting"]
        ]

    def clean_class_name(self, api_name: str) -> str:
        """
        Sanitize and format class names (e.g. 'Stripe Payments' -> 'StripePaymentsClient').
        """
        # Remove non-alphanumeric chars
        clean = re.sub(r'[^a-zA-Z0-9\s_\-]', '', api_name)
        # Convert to TitleCase
        words = re.split(r'[\s_\-]+', clean)
        title_words = [w.capitalize() for w in words if w]
        class_name = "".join(title_words)
        
        # Strip suffix 'API' or 'Client' if already present, then add 'Client'
        if class_name.endswith("Api"):
            class_name = class_name[:-3]
        elif class_name.endswith("API"):
            class_name = class_name[:-3]
        if class_name.endswith("Client"):
            class_name = class_name[:-6]
            
        return f"{class_name}Client"

    def clean_method_name(self, method: str, path: str, description: str = "") -> str:
        """
        Derive clean method names from method, path, and description.
        e.g., POST /customers -> create_customer
              GET /customers/{id} -> get_customer
              DELETE /customers/{id} -> delete_customer
              GET /customers -> list_customers
        """
        method = method.upper()
        
        # Clean path variables and split
        clean_path = path.strip("/")
        # Replace path parameters with empty or placeholder-less names
        clean_path = re.sub(r'\{(\w+)\}', '', clean_path)
        
        # Split path segments
        segments = [s.lower() for s in re.split(r'[\s_\-\/]+', clean_path) if s]
        
        # Filter out common API version prefixes (e.g. v1, v2)
        if segments and re.match(r'^v\d+$', segments[0]):
            segments = segments[1:]
            
        # Determine verb
        verb = "request"
        if method == "POST":
            # If path ends with something like 'search' or 'send', use that verb
            if segments and segments[-1] in ["search", "send", "refund", "verify", "cancel", "completions", "embeddings"]:
                verb = segments[-1]
                segments = segments[:-1]
            else:
                verb = "create"
        elif method == "GET":
            # If path has path params (indicated by {id} in original path), it's likely a get single
            if "{" in path:
                verb = "get"
            else:
                verb = "list"
        elif method == "PUT" or method == "PATCH":
            verb = "update"
        elif method == "DELETE":
            verb = "delete"
            
        # Resource name
        resource = "_".join(segments)
        
        # Deduplicate resource ending if it matches verb (e.g. create_customer_creation -> create_customer)
        if resource:
            # Singularize common items if needed, or keep as is
            # E.g. create_customers -> create_customer
            if verb in ["create", "get", "update", "delete"] and resource.endswith("s"):
                # Very basic singularization
                if resource.endswith("ies"):
                    resource = resource[:-3] + "y"
                elif not resource.endswith("ss"):
                    resource = resource[:-1]
            
            method_name = f"{verb}_{resource}"
        else:
            method_name = verb
            
        # Clean up any consecutive underscores
        method_name = re.sub(r'_+', '_', method_name).strip("_")
        
        # Avoid python keywords or empty names
        if method_name in ["class", "def", "return", "import", "from", "as", "global", "nonlocal", "pass"]:
            method_name = f"{method_name}_call"
            
        return method_name

    def generate(self, api_metadata: dict, use_case: str) -> str:
        raise NotImplementedError
