# ⚡ Smart DevTool

Smart DevTool is an automated API client integration and spec evolution pipeline. It transforms raw API specifications, documentation URLs, Postman Collections, or unstructured request/response payloads into ready-to-use client SDK wrappers, Postman Collections, modular frontend networking layers, and API evolution reports.

---

## 🛠️ Installation & Setup

### Prerequisites
* Python 3.9 or higher installed.
* An active Gemini API Key.

### 1. Environment Setup
Clone this repository and create a virtual environment:
```powershell
# Create virtual environment
python -m venv .venv

# Activate on Windows:
.venv\Scripts\activate

# Activate on macOS/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies
Install all package requirements:
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🏃 How to Use

### Launching the Dashboard
Start the local Streamlit dashboard:
```powershell
streamlit run app.py
```
Open your browser and navigate to `http://localhost:8501` (or the port specified in the terminal).

### 1. Workflow: API Integration Builder
Use this workflow to consume an external API in your applications:
1. **Choose Source**: Enter an API Documentation URL (to scrape) or upload an API Specification file (OpenAPI/Swagger/Postman JSON).
2. **Describe Use Case**: Type a plain-English description of your goal (e.g. *"Charge a credit card and list customers"*).
3. **Select Language & Stack**: Choose your language (Python, JavaScript, Java, C#) and target framework.
4. **Generate Client**: Click **Generate SDK & REST** to instantly create:
   * A type-safe, commented **Client SDK Wrapper class**.
   * Standalone **REST integration script snippets** for quick copy-pasting.
   * A structured **Postman Collection** JSON file.
   * A **Mermaid sequence diagram** illustrating the API request lifecycle.
5. **Generate Frontend Client**: Alternatively, click **Analyze Frontend Integration** to output a full, modular frontend client package (centralized Axios client, modular services, request/response models, and environment settings) inside a downloadable `.zip` file.

### 2. Workflow: API Evolution Analyzer
Use this workflow to compare two versions of an API and analyze the downstream impact:
1. **Select Input Method**: Choose to either upload spec files or paste raw HTTP payloads/documentation directly.
2. **Provide Contents (V1 & V2)**: Supply the previous version of the API contract (V1) and the updated version (V2).
3. **Analyze Evolution**: Click **Compare Specs & Analyze Evolution** to generate a complete breaking-change report detailing compatibility scores, warnings, safe additions, and a step-by-step developer migration guide.
4. **Export Reports**: Download the final evolution report as a formatted **JSON**, **Markdown**, or print-ready **PDF**.

---

## 💡 Key Features

* **High-Fidelity Spec Normalization**: Supports OpenAPI 3.x, Swagger 2.0, Postman Collections, raw Markdown/Text documentations, and sample JSON request/response payloads.
* **LLM-Powered Semantic Ranking**: Automatically filters and prioritizes critical endpoints from large specifications based on the user's specific use case.
* **Centralized Frontend Client Generation**: Builds complete Axios/Fetch API client packages including interceptors, automated retry configurations, request/response classes, and service wrappers.
* **Automated Evolution Diff Engine**: Programmatically detects path changes, method updates, parameter additions/removals, type changes, validation constraints, and authentication scheme updates.
* **AI-Augmented Impact Assessment**: Uses Gemini to analyze each specification change and explain its exact impact on frontend components and SDK callers.

---

## 📐 System Architecture

![Uploading image.png…]()


---

## 📁 Repository Directory Structure

```
.
├── .gitignore                  # Git configuration file to exclude local files and environments
├── README.md                   # Project documentation and developer setup guide
├── app.py                      # Streamlit dashboard and UI orchestration layer
├── spec_parser.py              # Ingests and normalizes OpenAPI, Swagger, Postman, and raw text API inputs
├── analyzer.py                 # Handles LLM-powered route ranking and frontend blueprint planning
├── generator.py                # Generates SDK wrappers, REST scripts, Postman Collections, and sequence diagrams
├── frontend_generator.py       # Builds Axios/Fetch client files, service files, models, and configurations
├── diff_engine.py              # Compares API contracts and compiles Markdown/PDF breaking-change reports
├── parser.py                   # Utilities for scraping web documentation and extracting file texts
├── requirements.txt            # Python dependencies configuration file
├── generators/                 # Submodule containing language-specific class generators and validators
└── scratch/                    # Test suites folder
    ├── test_diff_engine.py     # Automated test suite validating comparison classifications and reports
    ├── test_target_stacks.py   # Automated test suite validating stack configuration compatibility
    └── test_extended_parser.py # Automated test suite validating Postman and unstructured text parsing
```
