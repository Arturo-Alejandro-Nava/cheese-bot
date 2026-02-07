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

# --- 1. THE DEEP SCANNER (Live Website Only) ---
@st.cache_resource(ttl=3600) 
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. SCRAPE TEXT
    # We grab contact info and about info from HTML
    urls = ["https://hcmakers.com/contact-us/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/"]
    web_text = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n--- SOURCE: {u} ---\n{soup.get_text(' ', strip=True)[:4000]}\n"
        except: continue
        
    # 2. AUTO-DOWNLOAD & EXTRACT PDFS
    pdf_files = []
    file_inventory = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # FIND THE ZIP FILE
        # hcmakers puts all sell sheets in one big zip on this page
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_data = requests.get(zip_url, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                # We want to upload as many SELL SHEETS as possible so it has accurate numbers
                limit = 15 
                count = 0
                for fname in z.namelist():
                    lower_name = fname.lower()
                    if lower_name.endswith(".pdf"):
                        # Save temp
                        with open(f"temp_{count}.pdf", "wb") as f:
                            f.write(z.read(fname))
                        
                        # Upload to Google Brain
                        remote = genai.upload_file(path=f"temp_{count}.pdf", display_name=fname)
                        pdf_files.append(remote)
                        file_inventory.append(fname)
                        count += 1
                        if count >= limit: break
    except Exception as e:
        web_text += f"\n[System Error loading Documents: {e}]\n"

    # Wait for processing
    final_pdfs = []
    for p in pdf_files:
        retry = 0
        while p.state.name == "PROCESSING" and retry < 10:
            time.sleep(1)
            p = genai.get_file(p.name)
            retry += 1
        if p.state.name == "ACTIVE": final_pdfs.append(p)

    return web_text, final_pdfs, file_inventory

# --- LOAD DATA ---
with st.spinner("Downloading full catalog from hcmakers.com..."):
    # This ensures we have the REAL PDF documents, not just text
    site_text, knowledge_docs, doc_names = get_live_data()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response(question):
    # We pass the list of filenames to the AI so it knows where to look
    doc_list = "\n".join(doc_names)
    
    # 3. MASTER PROMPT
    system_prompt = f"""
    You are the Official Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    CRITICAL DATABASE:
    1. **ATTACHED DOCUMENTS:** I have attached {len(knowledge_docs)} official Sell Sheets from the website.
       - filenames: {doc_list}
    2. **WEBSITE TEXT:** Live contact info below.
    
    INSTRUCTIONS FOR ACCURACY:
    1. **READ THE TABLES:** If asked for nutrition (Calories, Protein, Fat), you MUST find the PDF named like the cheese (e.g. 'Oaxaca' or 'Fresco').
    2. **LOOK AT THE IMAGE:** Read the "Nutrition Facts" panel inside the file.
    3. **BE PRECISE:** Do not round numbers. If it says 80 calories, say 80. If 110, say 110.
    4. **NO HALLUCINATIONS:** If you can't find the exact product in the PDF list, state that. Don't guess.
    
    LANG: English or Spanish.
    
    WEBSITE CONTEXT:
    {site_text}
    """
    
    payload = [system_prompt] + knowledge_docs + [question]
    try:
        return model.generate_content(payload).text
    except: return "Consulting documents..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, specs, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI
    with st.chat_message("assistant"):
        with st.spinner("Analyzing PDF Sell Sheets..."):
            response_text = get_response(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})