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

# --- HEADER (Branding only) ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LIVE DATA SCRAPER (The Knowledge Brain) ---
@st.cache_resource(ttl=3600)
def get_live_intelligence():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # A. Scrape Website Text
    target_pages = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory info
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",   # Phone/Address
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    
    web_text = "WEBSITE DATA SOURCE:\n"
    
    for url in target_pages:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean = soup.get_text(" ", strip=True)[:4000]
            web_text += f"\n--- SOURCE: {url} ---\n{clean}\n"
        except: continue

    # B. Auto-Download PDF Documents
    # It hunts for the Zip file, extracts sell sheets, and feeds them to the AI
    pdf_files = []
    file_list = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Look for the Catalog Zip
        zip_link = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                count = 0
                for fname in z.namelist():
                    # We prioritize PDFs that look like product sheets
                    if fname.lower().endswith(".pdf") and count < 8:
                        with open(f"temp_{count}.pdf", "wb") as f: f.write(z.read(fname))
                        pdf_files.append(genai.upload_file(f"temp_{count}.pdf", display_name=fname))
                        file_list.append(fname)
                        count += 1
    except: pass
    
    return web_text, pdf_files, file_list

# --- INITIAL LOAD ---
with st.spinner("Connecting to Live Website & Processing Documents..."):
    website_knowledge, live_docs, doc_names = get_live_intelligence()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_text_response(question):
    
    doc_str = "\n".join(doc_names)
    
    system_prompt = f"""
    You are the Official Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE SOURCES:
    1. **LIVE PDF DOCUMENTS:** {len(live_docs)} files loaded (Filenames: {doc_str}). 
       - Read these visual tables for specific Nutrition Facts, Meltability, Pack Sizes, and Ingredients.
    2. **WEBSITE TEXT:** Live content scraped below.
    
    STRICT BEHAVIOR RULES:
    1. **TEXT ONLY:** Do not try to show images. Do not generate fake image links. 
       - If a user asks for an image, politely reply: *"I am a text-based concierge. I can provide detailed descriptions, specs, and nutrition facts, but for photos please verify on our Products page."*
    
    2. **DATA ACCURACY:** 
       - If asked about "Protein" or "Specs", look at the PDF table values. Do not guess. 
       - If the PDF has multiple sizes, list them.
       
    3. **CONTACT INFO:**
       - Sales (Sandy Goldberg): 847-258-0375
       - Marketing (Arturo Nava): 847-502-0934
       - Office: 224-366-4320
       - Plant: 752 N. Kent Road, Kent, IL 61044.
    
    4. **LANGUAGE:** English or Spanish (Detect based on question).
    
    WEBSITE CONTEXT:
    {website_knowledge}
    """
    
    payload = [system_prompt] + live_docs + [question]
    try:
        # Wait for file processing if needed
        for f in live_docs:
             while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
        
        return model.generate_content(payload).text
    except:
        return "I am analyzing the heavy document data. Please ask again in 10 seconds."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about our cheeses, nutrition specs, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing Catalog..."):
            response_text = get_text_response(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})