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

# --- HEADER (Logo + Title) ---
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

# --- 1. LIVE DATA ENGINE (Text + Documents) ---
@st.cache_resource(ttl=3600) 
def get_live_intelligence():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # A. Scrape Website Text
    target_pages = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/"
    ]
    
    web_text = "WEBSITE DATA:\n"
    
    for url in target_pages:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.content, 'html.parser')
            # Extract Main Content
            clean = soup.get_text(" ", strip=True)[:4000]
            web_text += f"\n--- SOURCE: {url} ---\n{clean}\n"
        except: continue

    # B. Auto-Download PDF Sell Sheets (From Zip)
    pdf_files = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Hunt for the Zip File
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_resp = requests.get(zip_url, headers=headers, timeout=15)
            with zipfile.ZipFile(io.BytesIO(z_resp.content)) as z:
                count = 0
                for fname in z.namelist():
                    # We only want PDFs that look like specs or sheets
                    if fname.lower().endswith(".pdf") and count < 8:
                        with open(f"temp_{count}.pdf", "wb") as f: f.write(z.read(fname))
                        pdf_files.append(genai.upload_file(f"temp_{count}.pdf", display_name=fname))
                        count += 1
                        
    except Exception as e:
        print(f"Error fetching PDFs: {e}")
    
    return web_text, pdf_files

# --- INITIAL LOAD ---
with st.spinner("Accessing Live Database & Documents..."):
    # This grabs live info from the web
    website_knowledge, live_docs = get_live_intelligence()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_text_response(question):
    
    # We enforce verified data here to prevent hallucinations
    verified_specs = """
    VERIFIED NUTRITION SPECS (PRIORITY):
    - **Oaxaca Cheese (All Sizes):** 80 Calories per 1oz (28g) serving.
    - **Queso Fresco (Natural):** 5g Protein per 1oz (28g) serving. 70 Calories.
    - **Cotija:** 100 Calories per 1oz. 6g Protein.
    - **Panela:** 80 Calories. 6g Protein.
    """
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    SOURCES:
    1. **ATTACHED PDFs:** Visual sell sheets found on the live website. 
    2. **WEBSITE TEXT:** Live contact info and company details.
    
    RULES:
    1. **NO IMAGES:** Do not show images. Do not provide image links.
       - If asked for an image, reply: *"I am a text-based automated assistant. You can view product photos on our Products page."*
    
    2. **DATA ACCURACY (CRITICAL):**
       - Use the 'VERIFIED NUTRITION SPECS' list above for Oaxaca/Fresco.
       - For other products, READ the attached PDF tables carefully.
       - Do not guess numbers.
    
    3. **CONTACTS:** 
       - Sales: Sandy Goldberg (847-258-0375)
       - Plant: 815-443-2100 (Kent, IL)
       - HQ: Chicago, IL
    
    4. **LANG:** English or Spanish.
    
    {verified_specs}
    
    WEBSITE CONTEXT:
    {website_knowledge}
    """
    
    payload = [system_prompt] + live_docs + [question]
    try:
        # Wait for file processing loop
        for f in live_docs:
             while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
        
        return model.generate_content(payload).text
    except:
        return "I am re-analyzing the documents. Please ask again in 5 seconds."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about products, nutrition specs, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing Live Data..."):
            response_text = get_text_response(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})