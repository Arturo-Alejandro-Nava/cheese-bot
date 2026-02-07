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
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LIVE DATA ENGINE ---
@st.cache_resource(ttl=3600) 
def get_live_intelligence():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Text Scraper
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/about-us/"]
    web_text = "WEBSITE DATA:\n"
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n--- SOURCE: {url} ---\n{soup.get_text(' ', strip=True)[:4000]}\n"
        except: continue

    # PDF Auto-Download
    pdf_files = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        zip_link = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                count = 0
                for fname in z.namelist():
                    if fname.lower().endswith(".pdf") and count < 8:
                        with open(f"temp_{count}.pdf", "wb") as f: f.write(z.read(fname))
                        pdf_files.append(genai.upload_file(f"temp_{count}.pdf", display_name=fname))
                        count += 1
    except: pass
    
    return web_text, pdf_files

with st.spinner("Updating Knowledge Base..."):
    web_txt, live_docs = get_live_intelligence()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_text_response(question):
    
    # HARDCODED CORRECT VALUES (The "Truth Source")
    # This prevents the AI from guessing wrong if it misreads the PDF.
    verified_specs = """
    CORRECT NUTRITION FACTS (1oz / 28g Serving):
    - **Queso Fresco (Natural):** 90 Calories | 5g Protein.
    - **Oaxaca:** 80 Calories | 6g Protein.
    - **Cotija:** 100 Calories | 6g Protein.
    - **Panela:** 80 Calories | 6g Protein.
    - **Requesón:** 45 Calories | 3g Protein.
    - **Quesadilla:** 100 Calories | 7g Protein.
    """
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE SOURCES:
    1. **VERIFIED FACTS:** Use the list below for Calories/Protein. These override the PDFs.
    2. **DOCUMENTS:** Attached Sell Sheets.
    3. **WEBSITE TEXT:** Contact info.
    
    RULES:
    1. **TEXT ONLY:** Do NOT provide images or image links. 
       - If asked, say: "Please visit hcmakers.com/products to see our gallery."
    
    2. **ACCURACY:**
       - Use this list for Nutrition numbers:
       {verified_specs}
    
    3. **CONTACTS:**
       - Sales: Sandy Goldberg (847-258-0375)
       - Plant: 815-443-2100 (Kent, IL)
    
    4. **LANG:** English or Spanish.
    
    WEBSITE CONTEXT:
    {web_txt}
    """
    
    payload = [system_prompt] + live_docs + [question]
    try:
        # File wait loop
        for f in live_docs:
             while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
        return model.generate_content(payload).text
    except:
        return "Checking specifications... ask again."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"): st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response_text = get_text_response(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})