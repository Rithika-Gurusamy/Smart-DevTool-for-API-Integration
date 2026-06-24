import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import os
import time
import datetime
import uuid


def fetch_docs(url: str) -> dict:
    """
    Fetches the documentation from the given URL and parses its content.
    Returns a dictionary with status, title, domain, raw_text, and a list of links.
    """
    if not url.strip():
        return {
            "success": False,
            "url": url,
            "domain": "",
            "title": "Local Knowledge Base",
            "text": "",
            "endpoints": [],
            "msg": "No URL provided. Using local knowledge base fallback."
        }

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    try:
        # Fetching with timeout
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        parsed = clean_html(html)
        
        domain = urlparse(url).netloc
        return {
            "success": True,
            "url": url,
            "domain": domain,
            "title": parsed.get("title", domain),
            "text": parsed.get("text", "")[:40000],  # Keep first 40k chars for LLM safety
            "endpoints": parsed.get("endpoints", []),
            "msg": "Fetched successfully."
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "domain": urlparse(url).netloc if url else "",
            "title": urlparse(url).netloc if url else "Local Knowledge Base",
            "text": "",
            "endpoints": [],
            "msg": f"Failed to fetch content ({str(e)}). Using knowledge base fallback."
        }

def clean_html(html_content: str) -> dict:
    """
    Strips script, style, and navigation tags. Extracts text content and scans for API routes.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract Title
    title = soup.title.string.strip() if soup.title else "API Documentation"
    
    # Remove script, style, head, nav, footer, iframe, noscript
    for element in soup(["script", "style", "head", "nav", "footer", "iframe", "noscript"]):
        element.decompose()
        
    # Get text
    text = soup.get_text(separator=' ')
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Look for possible REST patterns: GET/POST/PUT/DELETE/PATCH followed by path
    # e.g., "POST /v1/charges" or "GET /customers/{id}"
    endpoints = []
    rest_pattern = re.compile(r'\b(GET|POST|PUT|DELETE|PATCH)\s+([/\w\-\{\}:]+)', re.IGNORECASE)
    for match in rest_pattern.finditer(text):
        method, path = match.groups()
        if len(path) > 1 and path.startswith('/'):
            endpoints.append(f"{method.upper()} {path}")
        
    # Remove duplicates but preserve order
    seen = set()
    unique_endpoints = [x for x in endpoints if not (x in seen or seen.add(x))]
    
    return {
        "title": title,
        "text": text,
        "endpoints": unique_endpoints[:30]  # Grab first 30 endpoints
    }

def save_uploaded_file(uploaded_file, upload_dir="temp_uploads") -> dict:
    """
    Saves a Streamlit UploadedFile object to a temporary directory in the workspace.
    Returns a standardized document metadata dictionary.
    """
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)
        
    # Generate a unique file name to avoid collisions
    orig_name = uploaded_file.name
    base, ext = os.path.splitext(orig_name)
    # Clean the base name to keep it alphanumeric/simple
    clean_base = "".join(c for c in base if c.isalnum() or c in ('-', '_')).rstrip()
    unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{clean_base}{ext}"
    
    file_path = os.path.join(upload_dir, unique_name)
    abs_file_path = os.path.abspath(file_path)
    
    # Save the file content
    with open(abs_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    # Build standardized document metadata
    return {
        "source_type": "file",
        "file_name": orig_name,
        "file_extension": ext,
        "file_path": abs_file_path,
        "upload_timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

def extract_text_from_file(file_path: str, file_extension: str) -> str:
    """
    Reads plain-text file formats (markdown, text, json, yaml) and returns their content.
    Returns a placeholder for binary/non-text formats like pdf.
    """
    ext = file_extension.lower()
    if ext in ['.txt', '.md', '.json', '.yaml', '.yml']:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {os.path.basename(file_path)}: {str(e)}"
    elif ext == '.pdf':
        return f"[PDF document: {os.path.basename(file_path)}. Content extraction from PDF is a future enhancement and not yet supported in this commit.]"
    else:
        return f"[Unsupported file format: {ext}. Future versions will handle this format.]"

