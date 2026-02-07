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
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible = ["logo.jpg", "logo.png", "logo.jpeg"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. CORE FACT SHEET (Verified Hard Data) ---
# This ensures it never gets the core nutrition/contact numbers wrong, even if PDFs blur.
CORE_FACTS = """
CRITICAL DATABASE (Highest Priority):
1. **CONTACTS:**
   - VP of Sales (Sandy Goldberg): 847-258-0375
   - Senior Marketing Director (Arturo Nava): 847-502-0934
   - HR (Sofia Santiago): 815-443-4508
   - Plant Address: 752 N. Kent Road, Kent, IL 61044.
   - HQ Address: 150 South Wacker Drive, Chicago, IL.

2. **NUTRITION BASELINE (per 1oz):**
   - **Oaxaca:** 80 Cal, 7g Protein, 6g Fat, 130mg Sodium.
   - **Queso Fresco:** 80 Cal, 5g Protein, 6g Fat, 190mg Sodium.
   - **Panela:** 80 Cal, 6g Protein, 6g Fat, 220mg Sodium.
   - **Cotija:** 100 Cal, 6g Protein, 8g Fat, 380mg Sodium (Salty).
   - **Quesadilla:** 110 Cal, 7g Protein, 9g Fat (High Melt).
   - **Crema:** ~45 Cal per serving (varies by type).

3. **CAPABILITIES:**
   - Plant Size: 75,000 sq ft (Expansion in progress).
   - Certification: SQF Level 3.
   - Private Label: Yes, available for retailers/brands.
   - Pallet Configs: Flexible (6, 12, 24 count cases).
"""

# --- 2. LIVE UNIVERSAL SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_knowledge():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. SCRAPE TEXT from ALL key pages
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory/Logistics info
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/", # Trends/Articles
        "https://hcmakers.com/we-care-2/" # Community info
    ]
    
    combined_text = "LIVE WEBSITE CONTENT:\n"
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            # Extract main text
            text = soup.get_text(" ", strip=True)
            # Remove repetitive menu headers to clean data
            if len(text) > 500:
                combined_text += f"\n=== PAGE: {url} ===\n{text[:6000]}\n"
        except: continue
        
    return combined_text

# --- 3. MASSIVE DOCUMENT LOADER ---
@st.cache_resource(ttl=3600)
def process_live_files():
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    file_list_txt = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # 1. HUNT FOR THE ZIP (Contains Sell Sheets)
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_data = requests.get(zip_url, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                count = 0
                for fname in z.namelist():
                    # We accept more files now (Limit 10) to get variety
                    if fname.lower().endswith(".pdf") and count < 10:
                        # Prioritize files with "Sell Sheet" or cheese names
                        if any(x in fname.lower() for x in ["sheet", "fresco", "panela", "oaxaca", "cotija", "quesadilla", "crema"]):
                            with open(f"temp_{count}.pdf", "wb") as f: 
                                f.write(z.read(fname))
                            ai_files.append(genai.upload_file(f"temp_{count}.pdf", display_name=fname))
                            file_list_txt.append(fname)
                            count += 1
    except: pass
    
    return ai_files, file_list_txt

# --- LOAD DATA ---
with st.spinner("Extracting Website Knowledge & Processing Documents..."):
    website_data = get_website_knowledge()
    pdf_docs, doc_names = process_live_files()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    # 1. Build Memory (Passed previous questions)
    chat_memory = "CONVERSATION HISTORY:\n"
    for msg in st.session_state.chat_history:
        chat_memory += f"{msg['role'].upper()}: {msg['content']}\n"

    # 2. Build Document Context
    doc_context = "\n".join(doc_names)

    # 3. Master Prompt
    system_prompt = f"""
    You are the Senior Product Expert for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE SOURCES:
    1. **CORE FACTS (Below):** These are verified numbers for contacts & nutrition. PRIORITIZE THIS.
    2. **ATTACHED DOCUMENTS:** {len(pdf_docs)} Sell Sheets loaded. Read tables for melting specs, pack sizes, UPCs.
    3. **WEBSITE TEXT:** Live content about Capabilities, Logistics, and Quality.
    4. **CHAT HISTORY:** Remember what the user just asked (e.g. if they say "The 10oz one", look at the previous product mentioned).
    
    BEHAVIOR RULES:
    1. **NO IMAGES:** Provide high-quality text answers. Be descriptive.
    2. **CALCULATIONS:** If user asks for "Total Calories" in a block, Multiply (Cal/oz * Block Size).
    3. **LINKS:** Share specific URLs if useful (e.g. "You can read about our Quality here: https://hcmakers.com/quality").
    4. **SCOPE:** Answer questions on Products, Logistics, Manufacturing, Quality, and Company Info.
    5. **LANGUAGE:** English or Spanish.
    
    CORE FACTS (VERIFIED):
    {CORE_FACTS}
    
    LIVE WEBSITE DATA:
    {website_data}
    
    {chat_memory}
    """
    
    payload = [system_prompt] + pdf_docs + [question]
    
    try:
        # Wait for file readiness (Reliability)
        for f in pdf_docs:
             while f.state.name == "PROCESSING": time.sleep(0.5); f = genai.get_file(f.name)
        
        return model.generate_content(payload).text
    except: return "I am analyzing the full document library. Please ask again in 10 seconds."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about Products, Factory, Logistics, or Specs... / Preguntar...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User Msg
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI Msg
    with st.chat_message("assistant"):
        with st.spinner("Analyzing Global Data..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})