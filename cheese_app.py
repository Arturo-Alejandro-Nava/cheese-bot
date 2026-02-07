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
# We use Flash because it handles large files (PDFs) faster/cheaper
model = genai.GenerativeModel('gemini-1.5-flash')

# --- WEBPAGE CONFIG (Restored to Original) ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER / BANNER LOGIC (Restored) ---
col1, col2 = st.columns([1, 4])
with col1:
    # This checks for the logo/banner file you uploaded previously
    possible_logos = ["logo.jpg", "logo.png", "logo.jpeg"]
    found = False
    for p in possible_logos:
        if os.path.exists(p):
            st.image(p, width=130)
            found = True
            break
    if not found: 
        st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. LIVE DATA ENGINE (Website & PDFs Only) ---
# This complies with your request to NOT use hardcoded cheatsheets.
# It MUST download the real files from the internet.
@st.cache_resource(ttl=3600) 
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # PART A: SCRAPE TEXT (For Contacts/Location)
    # We scrape 4 key pages
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/capabilities/"
    ]
    web_text = "WEBSITE DATA CONTENT:\n"
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean_text = soup.get_text(" ", strip=True)[:4000] # Limit per page
            web_text += f"\n--- SOURCE: {url} ---\n{clean_text}\n"
        except: continue
        
    # PART B: SMART FILE DOWNLOADER (For Specs)
    # Strategy: Find the ZIP, open it in memory, extract ONLY critical spec sheets.
    pdf_files = []
    file_list_txt = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Find the Resources ZIP
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_data = requests.get(zip_url, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                # FILTER: Only grab the relevant Sell Sheets to prevent memory crash
                critical_keywords = ["fresco", "oaxaca", "panela", "cotija", "quesadilla", "crema", "sheet"]
                
                count = 0
                for fname in z.namelist():
                    lower_name = fname.lower()
                    
                    # Only process PDFs that match our cheese list
                    if lower_name.endswith(".pdf") and any(k in lower_name for k in critical_keywords):
                        
                        # Stop after 6 files to save Server Memory (prevents crash)
                        if count >= 6: break 
                        
                        # Extract logic
                        with open(f"temp_{count}.pdf", "wb") as f: 
                            f.write(z.read(fname))
                        
                        # Send to AI
                        remote_file = genai.upload_file(path=f"temp_{count}.pdf", display_name=fname)
                        pdf_files.append(remote_file)
                        file_list_txt.append(fname)
                        count += 1
                        
    except Exception as e:
        web_text += f"\n[System Note: Document fetch partial error: {e}]"
    
    # Wait for files to be ready at Google
    ready_files = []
    for f in pdf_files:
        retry = 0
        while f.state.name == "PROCESSING" and retry < 5:
            time.sleep(1)
            f = genai.get_file(f.name)
            retry += 1
        if f.state.name == "ACTIVE":
            ready_files.append(f)
            
    return web_text, ready_files, file_list_txt

# --- LOAD INDICATOR ---
with st.spinner("Connecting to hcmakers.com database & extracting sell sheets..."):
    # This calls the function above
    website_knowledge, live_docs, doc_names = get_live_data()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response_from_site(question):
    
    # Formatting the file list for the prompt
    doc_str = "\n".join(doc_names)
    
    system_prompt = f"""
    You are the Senior Product Specialist for 'Hispanic Cheese Makers-Nuestro Queso'.
    
    DATA SOURCE INSTRUCTIONS:
    1. **USE ATTACHED DOCUMENTS:** I have loaded {len(live_docs)} spec sheets directly from the website zip file. 
       - Filenames: {doc_str}
       - You must READ the tables inside these PDF files to answer Nutrition/Pack size questions.
    
    2. **USE LIVE WEBSITE TEXT:** The context text provided below is from the live website. Use this for contacts/address.
    
    RULES:
    1. **NO HARDCODED GUESSES:** Read the file. If you see the number in the PDF table, state it exactly.
    2. **IMAGES:** Do not try to show images. Describe products in text.
    3. **LANGUAGE:** English or Spanish (match user).
    
    WEBSITE CONTEXT:
    {website_knowledge}
    """
    
    payload = [system_prompt] + live_docs + [question]
    
    try:
        return model.generate_content(payload).text
    except:
        return "I am re-reading the catalog. Please wait 5 seconds and ask again."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about specifications, nutrition, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # 1. User
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 2. Assistant
    with st.chat_message("assistant"):
        with st.spinner("Analyzing downloadable files..."):
            response_text = get_response_from_site(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})