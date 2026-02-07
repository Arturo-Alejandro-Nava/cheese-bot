import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ No API Key found. Add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers - Nuestro Queso", 
    page_icon="🧀"
)

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    # Check for logo file
    for logo in ["logo.jpg", "logo.png", "logo.jpeg"]:
        if os.path.exists(logo):
            st.image(logo, width=130)
            break
    else:
        st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers - Nuestro Queso")

st.markdown("---")

# --- LIVE DATA LOADER ---
@st.cache_resource(ttl=3600, show_spinner=False)
def load_knowledge_base():
    """
    Loads data from the live website and PDF catalog.
    Returns: (website_text, pdf_files, file_names)
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    status = st.status("🔄 Connecting to live database...", expanded=True)
    
    # STEP 1: Scrape website text
    status.write("📡 Reading website pages...")
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/capabilities/"
    ]
    
    web_text = "=== LIVE WEBSITE DATA ===\n"
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(" ", strip=True)[:3000]
            web_text += f"\n[{url}]\n{text}\n"
        except:
            continue
    
    # STEP 2: Download and process PDFs
    status.write("📥 Downloading product spec sheets...")
    pdf_files = []
    file_names = []
    
    try:
        # Find the resources page with ZIP file
        response = requests.get("https://hcmakers.com/resources/", headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Locate ZIP file
        zip_url = None
        for link in soup.find_all('a', href=True):
            if link['href'].endswith('.zip'):
                zip_url = link['href']
                break
        
        if zip_url:
            status.write(f"📦 Extracting catalog from {zip_url.split('/')[-1]}...")
            
            # Download ZIP
            zip_data = requests.get(zip_url, headers=headers, timeout=20).content
            
            # Extract specific PDFs (limit to 4 to prevent memory issues)
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                # Filter for key product sheets
                all_pdfs = [f for f in zf.namelist() if f.lower().endswith('.pdf')]
                
                # Prioritize sheets with these keywords
                keywords = ['fresco', 'oaxaca', 'panela', 'cotija', 'quesadilla']
                priority_pdfs = [
                    pdf for pdf in all_pdfs 
                    if any(kw in pdf.lower() for kw in keywords)
                ]
                
                # Process up to 4 PDFs
                for i, filename in enumerate(priority_pdfs[:4]):
                    status.write(f"📄 Processing: {filename}...")
                    
                    # Extract PDF
                    pdf_data = zf.read(filename)
                    temp_path = f"temp_{i}.pdf"
                    
                    with open(temp_path, "wb") as f:
                        f.write(pdf_data)
                    
                    # Upload to Gemini
                    uploaded = genai.upload_file(path=temp_path, display_name=filename)
                    
                    # Wait for processing (critical!)
                    retry_count = 0
                    while uploaded.state.name == "PROCESSING" and retry_count < 15:
                        time.sleep(1)
                        uploaded = genai.get_file(uploaded.name)
                        retry_count += 1
                    
                    # Only add if successful
                    if uploaded.state.name == "ACTIVE":
                        pdf_files.append(uploaded)
                        file_names.append(filename)
                        status.write(f"✅ Loaded: {filename}")
                    else:
                        status.write(f"⚠️ Skipped: {filename} (timeout)")
        
        else:
            status.write("⚠️ No ZIP file found on resources page")
    
    except Exception as e:
        status.write(f"⚠️ PDF loading error: {str(e)[:100]}")
    
    status.update(
        label=f"✅ Ready! Loaded {len(pdf_files)} spec sheets", 
        state="complete", 
        expanded=False
    )
    
    return web_text, pdf_files, file_names

# --- INITIALIZE KNOWLEDGE BASE ---
website_knowledge, live_pdfs, pdf_names = load_knowledge_base()

# --- CHAT HISTORY ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- CHAT FUNCTION ---
def get_ai_response(user_question):
    """
    Sends question to Gemini with full context
    """
    # Build file list for AI awareness
    available_docs = "\n".join([f"- {name}" for name in pdf_names])
    
    # Create system prompt
    system_prompt = f"""You are a product specialist for Hispanic Cheese Makers (Nuestro Queso).

AVAILABLE RESOURCES:
{len(live_pdfs)} Product Specification PDFs:
{available_docs}

INSTRUCTIONS:
1. **For nutrition questions** (calories, protein, fat):
   - Look at the Nutrition Facts table in the relevant PDF
   - State exact numbers from the table
   - Do NOT estimate or guess

2. **For contact/location questions**:
   - Use the website data below
   - Key contacts: VP Sales (Sandy Goldberg): 847-258-0375
                   Marketing (Arturo Nava): 847-502-0934

3. **For images**:
   - Do not attempt to display images
   - Provide detailed text descriptions instead

4. **Language**: 
   - Respond in English or Spanish based on user's language

WEBSITE CONTEXT:
{website_knowledge}
"""
    
    # Build message payload
    messages = [system_prompt] + live_pdfs + [user_question]
    
    try:
        response = model.generate_content(messages)
        return response.text
    except Exception as e:
        return f"⚠️ Processing error. Please try rephrasing your question.\n\nError: {str(e)[:100]}"

# --- DISPLAY CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Ask about products, nutrition, or contact info... (Pregunta aquí)"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("🧀 Analyzing spec sheets..."):
            response = get_ai_response(prompt)
            st.markdown(response)
    
    # Add assistant message
    st.session_state.messages.append({"role": "assistant", "content": response})

# --- FOOTER ---
st.markdown("---")
st.caption("💡 Powered by live data from hcmakers.com")