import streamlit as st
import json
import base64
import os
from parser import fetch_docs, save_uploaded_file, extract_text_from_file
from analyzer import analyze_api_docs
from generator import generate_wrapper, generate_postman_collection, generate_sequence_diagram
from spec_parser import detect_and_parse_spec, SpecParserError

# Page configuration
st.set_page_config(
    page_title="Smart DevTool | SDK & Postman Builder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-Fidelity CSS
st.markdown("""
<style>
    /* Global styles */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Header Container styling */
    .header-container {
        padding: 1.5rem;
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        border-radius: 12px;
        border: 1px solid #312e81;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(to right, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
    }
    
    /* Card Styles */
    .custom-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
    }
    
    .badge-auth {
        background-color: #312e81;
        color: #c084fc;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
        border: 1px solid #4f46e5;
        display: inline-block;
    }
    
    .badge-method {
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8rem;
        display: inline-block;
        margin-right: 0.5rem;
        min-width: 60px;
        text-align: center;
    }
    
    .method-get { background-color: #0e7490; }
    .method-post { background-color: #1d4ed8; }
    .method-put { background-color: #b45309; }
    .method-delete { background-color: #b91c1c; }
    .method-patch { background-color: #6d28d9; }
    
    /* Code container block styling */
    .stCodeBlock {
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
    }
    
    /* Presets Container */
    .preset-box {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* Download Button styling */
    .download-btn {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white !important;
        padding: 0.5rem 1.2rem;
        border-radius: 6px;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        margin-top: 1rem;
        border: none;
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3);
        transition: opacity 0.2s;
    }
    .download-btn:hover {
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("""
<div class="header-container">
    <div class="header-title">⚡ Smart DevTool</div>
    <div class="header-subtitle">Instantly transform any API Documentation URL & Use Case into custom client SDK wrappers, Postman Collections, and Sequence Diagrams.</div>
</div>
""", unsafe_allow_html=True)

# Initialize Session States for inputs if needed
if "url_input" not in st.session_state:
    st.session_state["url_input"] = ""
if "use_case_input" not in st.session_state:
    st.session_state["use_case_input"] = ""
if "lang_input" not in st.session_state:
    st.session_state["lang_input"] = "Python"
if "doc_source_selection" not in st.session_state:
    st.session_state["doc_source_selection"] = "Documentation URL"

# Preset triggers
def select_preset(url, use_case, lang):
    st.session_state["url_input"] = url
    st.session_state["use_case_input"] = use_case
    st.session_state["lang_input"] = lang
    st.session_state["doc_source_selection"] = "Documentation URL"

# Sidebar controls
st.sidebar.markdown("### 🛠️ Controller")
st.sidebar.markdown("Use presets below to instantly test standard workflows:")

col_pre1, col_pre2 = st.sidebar.columns(2)
with col_pre1:
    if st.button("Stripe Payments", use_container_width=True):
        select_preset(
            url="https://api.stripe.com/docs",
            use_case="I want to create a checkout customer payment system with billing support",
            lang="Python"
        )
    if st.button("Twilio SMS Alert", use_container_width=True):
        select_preset(
            url="https://www.twilio.com/docs/usage/api",
            use_case="Send transactional SMS verification codes to users",
            lang="JavaScript"
        )
with col_pre2:
    if st.button("OpenAI Chat Completion", use_container_width=True):
        select_preset(
            url="https://platform.openai.com/docs/api-reference",
            use_case="Generate completions for conversational chatbots",
            lang="Python"
        )
    if st.button("Clear Inputs", use_container_width=True):
        select_preset("", "", "Python")

st.sidebar.divider()
st.sidebar.markdown("""
### 🧠 Engine Info
- **AI Backend**: Gemini 2.5 Flash
- **Features Enabled**:
  - HTML DOM Fetcher
  - Knowledge Base Fallback
  - Custom Class Generator
  - Postman Collection Generator
  - Mermaid Sequence Generator
""")

# Main Forms Columns
col_form, col_meta = st.columns([2, 1])

with col_form:
    st.markdown("### 📋 Configuration")
    doc_source = st.radio(
        "Select Documentation Source:",
        ["Documentation URL", "Upload Documentation File"],
        index=["Documentation URL", "Upload Documentation File"].index(st.session_state["doc_source_selection"]),
        horizontal=True
    )
    
    # Store doc source in session state to handle page refreshes
    st.session_state["doc_source_selection"] = doc_source
    
    if doc_source == "Documentation URL":
        url_input = st.text_input(
            "API Documentation URL:", 
            value=st.session_state["url_input"], 
            placeholder="e.g. https://api.stripe.com/docs"
        )
        uploaded_file = None
    else:
        uploaded_file = st.file_uploader(
            "Upload API Documentation File:",
            type=['pdf', 'md', 'txt', 'json', 'yaml', 'yml'],
            help="Supported formats: PDF, MD, TXT, JSON, YAML, YML. Max size: 10 MB."
        )
        url_input = ""
        
        # UI Validation & Details
        if uploaded_file is not None:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            if file_size_mb > 10.0:
                st.error(f"❌ File too large: **{uploaded_file.name}** ({file_size_mb:.2f} MB). Max size allowed is 10 MB.")
            else:
                _, ext = os.path.splitext(uploaded_file.name)
                if ext.lower() not in ['.pdf', '.md', '.txt', '.json', '.yaml', '.yml']:
                    st.error(f"❌ Unsupported file format: **{ext}**.")
                else:
                    st.success(f"✔️ Upload success! File: **{uploaded_file.name}** | Type: **{ext.upper()}** ({uploaded_file.type}) | Size: **{file_size_mb:.2f} MB**")
                    
    use_case_input = st.text_area(
        "Describe your Use Case:", 
        value=st.session_state["use_case_input"],
        placeholder="e.g. I want to create a payment system to charge cards and list customer records",
        height=100
    )

with col_meta:
    st.markdown("### ⚙️ Target Options")
    lang_input = st.selectbox(
        "Target Language:",
        ["Python", "JavaScript", "TypeScript", "Go", "Java", "C#"],
        index=["Python", "JavaScript", "TypeScript", "Go", "Java", "C#"].index(st.session_state["lang_input"])
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("⚡ Generate SDK & Integration Package", use_container_width=True, type="primary")

# Run Generation Process
if generate_btn:
    if "parsed_spec" in st.session_state:
        del st.session_state["parsed_spec"]
    is_valid = True
    
    # In-depth validation before proceeding
    if doc_source == "Documentation URL":
        if not url_input.strip():
            st.warning("⚠️ Please provide a Documentation URL.")
            is_valid = False
    else:  # File Upload
        if uploaded_file is None:
            st.warning("⚠️ Please upload an API Documentation File.")
            is_valid = False
        else:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            if file_size_mb > 10.0:
                st.error(f"❌ File size exceeds 10 MB limit ({file_size_mb:.2f} MB). Please upload a smaller file.")
                is_valid = False
            else:
                _, ext = os.path.splitext(uploaded_file.name)
                if ext.lower() not in ['.pdf', '.md', '.txt', '.json', '.yaml', '.yml']:
                    st.error(f"❌ Unsupported file extension: {ext}.")
                    is_valid = False
                    
    if is_valid and not use_case_input.strip():
        st.warning("⚠️ Please describe your Use Case.")
        is_valid = False
        
    if is_valid:
        # Step 1: Documentation Ingestion status
        with st.status("🛠️ Processing API Package...", expanded=True) as status:
            if doc_source == "Documentation URL":
                status.update(label="Scraping HTML Documentation URL...", state="running")
                doc_result = fetch_docs(url_input)
                scraped_text = doc_result.get("text", "")
                source_url = url_input
                
                # Standardized document input object for URL
                doc_input_metadata = {
                    "source_type": "url",
                    "url": url_input
                }
            else:
                status.update(label="Ingesting uploaded documentation file...", state="running")
                # Save the file temporarily
                doc_input_metadata = save_uploaded_file(uploaded_file)
                # Extract text
                raw_text = extract_text_from_file(doc_input_metadata["file_path"], doc_input_metadata["file_extension"])
                
                # Attempt to parse as OpenAPI/Swagger
                try:
                    parsed_spec = detect_and_parse_spec(raw_text)
                    st.session_state["parsed_spec"] = parsed_spec
                    scraped_text = json.dumps(parsed_spec, indent=2)
                except SpecParserError as e:
                    scraped_text = raw_text # fallback to raw text if not a valid spec
                    
                source_url = "" # No URL source
                
            # Log/display standard metadata object to verify its creation
            st.write("📄 Standardized Document Input Object:", doc_input_metadata)
            
            if "parsed_spec" in st.session_state:
                ps = st.session_state["parsed_spec"]
                st.markdown("### 🔍 API Specification Detected")
                st.info(f"**Type:** {ps.get('spec_type', '').upper()} | **Version:** {ps.get('spec_version', '')}")
                st.write(f"- **Endpoints Found:** {len(ps.get('endpoints', []))}")
                st.write(f"- **Auth Schemes Defined:** {len(ps.get('authentication', []))}")
            
            # Step 2: Analyzer
            status.update(label="Analyzing API details and mapping endpoints...", state="running")
            analysis = analyze_api_docs(
                url=source_url,
                scraped_text=scraped_text,
                use_case=use_case_input,
                language=lang_input
            )
            
            # Step 3: Code Gen
            status.update(label="Building wrapper class SDK & Postman collection...", state="running")
            wrapper_code = generate_wrapper(analysis, lang_input, use_case_input)
            postman_json = generate_postman_collection(analysis)
            sequence_mermaid = generate_sequence_diagram(analysis, lang_input)
            
            status.update(label="Assets Generated Successfully!", state="complete")
        
        # Save results in session state to persist between page elements
        st.session_state["result_ready"] = True
        st.session_state["analysis"] = analysis
        st.session_state["wrapper_code"] = wrapper_code
        st.session_state["postman_json"] = postman_json
        st.session_state["sequence_mermaid"] = sequence_mermaid
        st.session_state["language"] = lang_input

# Display outputs if generation is complete
if st.session_state.get("result_ready"):
    analysis = st.session_state["analysis"]
    wrapper_code = st.session_state["wrapper_code"]
    postman_json = st.session_state["postman_json"]
    sequence_mermaid = st.session_state["sequence_mermaid"]
    language = st.session_state["language"]
    
    st.divider()
    
    # Metadata Overview Cards
    col_meta1, col_meta2, col_meta3 = st.columns(3)
    
    with col_meta1:
        st.markdown(f"""
        <div class="custom-card">
            <h4>🏷️ Target API</h4>
            <h2 style="color: #818cf8; margin-top: 0.5rem;">{analysis.get('api_name', 'Custom API')}</h2>
        </div>
        """, unsafe_allow_html=True)
        
    with col_meta2:
        auth_type = analysis.get("auth_method", {}).get("type", "API Key")
        auth_desc = analysis.get("auth_method", {}).get("description", "")
        st.markdown(f"""
        <div class="custom-card">
            <h4>🔑 Authentication</h4>
            <div style="margin-top: 0.5rem; margin-bottom: 0.2rem;"><span class="badge-auth">{auth_type}</span></div>
            <small style="color: #94a3b8;">{auth_desc}</small>
        </div>
        """, unsafe_allow_html=True)
        
    with col_meta3:
        sdk_name = analysis.get("sdk_recommendation", {}).get("name", "")
        sdk_install = analysis.get("sdk_recommendation", {}).get("install_command", "")
        st.markdown(f"""
        <div class="custom-card">
            <h4>📦 Recommended SDK</h4>
            <code style="background-color: #242c3d; padding: 0.3rem 0.5rem; border-radius: 4px; display: block; margin-top: 0.5rem;">{sdk_install}</code>
        </div>
        """, unsafe_allow_html=True)

    # Tabs for developer utility exports
    tab_code, tab_endpoints, tab_postman, tab_sequence = st.tabs([
        "💻 Client Wrapper", 
        "🗺️ Endpoint Mapping", 
        "📬 Postman Collection", 
        "📊 Sequence Diagram"
    ])
    
    with tab_code:
        st.markdown("### Client Wrapper Class")
        st.markdown(f"Generated clean client code implementing requested endpoints in `{language}`.")
        
        # SDK Summary Panel
        st.markdown("#### 📊 SDK Summary Panel")
        from generators.base import BaseSDKGenerator
        base_gen = BaseSDKGenerator()
        class_name = base_gen.clean_class_name(analysis.get("api_name", "API"))
        
        primary_eps = [e for e in analysis.get("endpoints", []) if e.get("category") == "Primary"]
        supporting_eps = [e for e in analysis.get("endpoints", []) if e.get("category") == "Supporting"]
        num_methods = len(primary_eps) + len(supporting_eps)
        auth_type = analysis.get("auth_method", {}).get("type", "API Key")
        
        sum_col1, sum_col2, sum_col3 = st.columns(3)
        with sum_col1:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 1rem; border-radius: 8px; border: 1px solid #334155; margin-bottom: 1rem;">
                <small style="color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem;">Client Class Name</small>
                <div style="font-size: 1.2rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem;">{class_name}</div>
            </div>
            """, unsafe_allow_html=True)
        with sum_col2:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 1rem; border-radius: 8px; border: 1px solid #334155; margin-bottom: 1rem;">
                <small style="color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem;">Generated Methods</small>
                <div style="font-size: 1.2rem; font-weight: 700; color: #34d399; margin-top: 0.25rem;">{num_methods} Methods</div>
            </div>
            """, unsafe_allow_html=True)
        with sum_col3:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 1rem; border-radius: 8px; border: 1px solid #334155; margin-bottom: 1rem;">
                <small style="color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem;">Authentication</small>
                <div style="font-size: 1.2rem; font-weight: 700; color: #a78bfa; margin-top: 0.25rem;">{auth_type}</div>
            </div>
            """, unsafe_allow_html=True)
            
        list_col1, list_col2 = st.columns(2)
        with list_col1:
            st.markdown("##### 🔴 Primary Endpoints Included")
            if primary_eps:
                for ep in primary_eps:
                    st.markdown(f"- `{ep['method']}` `{ep['path']}`")
            else:
                st.info("No primary endpoints detected.")
        with list_col2:
            st.markdown("##### 🔵 Supporting Endpoints Included")
            if supporting_eps:
                for ep in supporting_eps:
                    st.markdown(f"- `{ep['method']}` `{ep['path']}`")
            else:
                st.info("No supporting endpoints detected.")
        st.divider()
        
        # Determine extension
        ext = "py"
        if language.lower() in ["javascript", "typescript"]:
            ext = "js" if language.lower() == "javascript" else "ts"
        elif language.lower() == "go":
            ext = "go"
        elif language.lower() == "java":
            ext = "java"
        elif language.lower() == "c#":
            ext = "cs"
            
        st.code(wrapper_code, language=language.lower())
        
        # Download button for wrapper file
        filename = f"{analysis.get('api_name', 'Client').replace(' ', '').lower()}_client.{ext}"
        b64_code = base64.b64encode(wrapper_code.encode()).decode()
        href_code = f'<a href="data:file/txt;base64,{b64_code}" download="{filename}" class="download-btn">📥 Download client.{ext}</a>'
        st.markdown(href_code, unsafe_allow_html=True)
        
    with tab_endpoints:
        st.markdown("### 🏆 Endpoint Relevance Ranking")
        st.markdown("Endpoints analyzed and intelligently ranked against your use case intent.")
        
        endpoints = analysis.get("endpoints", [])
        
        # Sort endpoints by relevance score descending
        endpoints.sort(key=lambda x: x.get("relevance_score", x.get("relevance", 0) if isinstance(x.get("relevance", 0), int) else 0), reverse=True)
        
        # Calculate Metrics
        total = len(endpoints)
        primary = sum(1 for e in endpoints if e.get("category") == "Primary")
        supporting = sum(1 for e in endpoints if e.get("category") == "Supporting")
        optional = sum(1 for e in endpoints if e.get("category") == "Optional")
        avg_score = sum(e.get("relevance_score", 0) for e in endpoints) / total if total > 0 else 0
        
        # Display Metrics Panel
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Analyzed", total)
        m2.metric("Primary", primary)
        m3.metric("Supporting", supporting)
        m4.metric("Optional", optional)
        m5.metric("Avg Score", f"{avg_score:.1f}")
        
        st.divider()
        
        for ep in endpoints:
            method = ep.get("method", "GET").upper()
            path = ep.get("path", "/")
            desc = ep.get("description", "")
            score = ep.get("relevance_score", 0)
            category = ep.get("category", "Unknown")
            
            # Fallback for old relevance field if using cached or non-updated LLM response
            if category == "Unknown" and "relevance" in ep:
                reasoning = ep.get("relevance", "")
            else:
                reasoning = ep.get("reasoning", "")
                
            deps = ep.get("dependencies", [])
            
            method_class = f"method-{method.lower()}"
            
            # Badge color based on category
            cat_color = "#94a3b8"
            if category == "Primary": cat_color = "#ef4444"
            elif category == "Supporting": cat_color = "#3b82f6"
            elif category == "Optional": cat_color = "#10b981"
            elif category == "Irrelevant": cat_color = "#64748b"
            
            st.markdown(f"""
            <div style="background-color: #161b22; border-left: 4px solid {cat_color}; padding: 1rem; border-radius: 0 8px 8px 0; margin-bottom: 0.8rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="badge-method {method_class}">{method}</span>
                        <strong style="font-size: 1.1rem; color: #f8fafc; font-family: monospace;">{path}</strong>
                    </div>
                    <div>
                        <span style="background-color: #242c3d; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; border: 1px solid {cat_color}; color: {cat_color};">
                            {category} | Score: {score}
                        </span>
                    </div>
                </div>
                <p style="margin: 0.8rem 0 0.4rem 0; color: #cbd5e1; font-weight: 500;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("🔍 Detailed Reasoning & Dependencies"):
                st.markdown(f"**Reasoning:** {reasoning}")
                if deps:
                    st.markdown("**Dependencies:**")
                    for d in deps:
                        st.markdown(f"- `{d}`")
                else:
                    st.markdown("**Dependencies:** None")
            
    with tab_postman:
        st.markdown("### Postman Collection JSON")
        st.markdown("Import this JSON directly into Postman to test requests interactively.")
        
        st.code(postman_json, language="json")
        
        # Download Postman Collection
        filename_postman = f"{analysis.get('api_name', 'API').replace(' ', '').lower()}_postman_collection.json"
        b64_postman = base64.b64encode(postman_json.encode()).decode()
        href_postman = f'<a href="data:file/txt;base64,{b64_postman}" download="{filename_postman}" class="download-btn">📥 Download Postman Collection JSON</a>'
        st.markdown(href_postman, unsafe_allow_html=True)
        
    with tab_sequence:
        st.markdown("### Sequence Diagram")
        st.markdown("Execution flow of the developer's request mapping through the client wrapper:")
        
        # Direct Mermaid support
        st.markdown(f"```mermaid\n{sequence_mermaid}\n```")
        
        st.markdown("---")
        st.markdown("#### Raw Diagram Markup")
        st.code(sequence_mermaid, language="mermaid")
