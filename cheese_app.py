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
# We use Flash because it allows high-volume document reading cheaply
model = genai.GenerativeModel('gemini-1.5-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER / BANNER LOGIC ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_logos = ["logo.jpg", "logo.png", "logo.jpeg", "147.png"] # Added your specific file name just in case
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

# --- 1. INTELLIGENCE LOADER (LIVE SITE & PDFS) ---
@st.cache_resource(ttl=3600, show_spinner=False)
def load_live_intelligence():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # STATUS TRACKER FOR UI
    status = st.status("Connecting to Live Database...", expanded=True)
    
    # PART A: TEXT SCRAPING (Fast)
    status.write("📡 Scanning hcmakers.com for contact info...")
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/capabilities/"
    ]
    web_text = "WEBSITE TEXT CONTENT:\n"
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n--- SOURCE: {url} ---\n{soup.get_text(' ', strip=True)[:3000]}\n"
        except: continue
        
    # PART B: PDF DOWNLOADER (The Critical Part)
    pdf_objects = []
    file_names = []
    
    try:
        status.write("📥 Locate & Download Spec Sheets (Live)...")
        r = requests.get("https://hcmakers.com/resources/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_data = requests.get(zip_url, headers=headers, timeout=20).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                # We specifically look for the CORE items to avoid crashing the server memory
                # We prioritize the Sell Sheets because they have the Nutrition Facts tables
                target_files = [f for f in z.namelist() if f.endswith(".pdf") and any(x in f.lower() for x in ['sheet', 'fresco', 'oaxaca', 'panela', 'cotija'])]
                
                # Limit to 5 to prevent "re-reading catalog" timeouts
                for i, fname in enumerate(target_files[:5]):
                    status.write(f"📄 Processing: {fname}...")
                    
                    # Extract to temp
                    with open(f"temp_{i}.pdf", "wb") as f:
                        f.write(z.read(fname))
                    
                    # Upload to Google Brain
                    uploaded_file = genai.upload_file(path=f"temp_{i}.pdf", display_name=fname)
                    
                    # CRITICAL: We wait for the file to be ACTIVE before letting the user chat
                    # This prevents the crash you saw earlier
                    retry = 0
                    while uploaded_file.state.name == "PROCESSING" and retry < 10:
                        time.sleep(1)
                        uploaded_file = genai.get_file(uploaded_file.name)
                        retry += 1
                        
                    if uploaded_file.state.name == "ACTIVE":
                        pdf_objects.append(uploaded_file)
                        file_names.append(fname)
                    else:
                        status.write(f"⚠️ Skipped {fname} (Processing Error)")
                        
    except Exception as e:
        status.write(f"⚠️ Note: Partial Document Error ({e})")
    
    status.update(label="✅ System Ready! Database Synced.", state="complete", expanded=False)
    return web_text, pdf_objects, file_names

# --- LOAD ---
website_data, live_pdfs, pdf_names = load_live_intelligence()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Construct Context from filenames
    files_str = "\n".join(pdf_names)
    
    system_prompt = f"""
    You are the Senior Sales AI for 'Hispanic Cheese Makers-Nuestro Queso'.
    
    RESOURCES AVAILABLE:
    1. **LIVE PDF SHEETS:** {len(live_pdfs)} official docs attached. (Filenames: {files_str})
       - YOU MUST READ THE VISUAL TABLES INSIDE THESE PDFS.
       - Look for "Nutrition Facts" panels in the files to answer protein/fat/calorie questions.
    
    2. **WEBSITE DATA:** Context below. Use for contacts and location.
    
    RULES:
    - **ACCURACY:** If the PDF says "Protein 5g", say "5g". Do not guess. 
    - **NO IMAGES:** Do not generate fake image links. Use text descriptions.
    - **LANG:** English or Spanish (Detect User).
    
    WEBSITE CONTEXT:
    {website_data}
    """
    
    # We combine Prompt + Files + User Question
    payload = [system_prompt] + live_pdfs + [question]
    
    try:
        return model.generate_content(payload).text
    except Exception as e:
        # Fallback if Google API gets overwhelmed
        return "I am currently analyzing the heavy spec sheets. Please try asking again in 10 seconds."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about specs, nutrition, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # 1. User
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 2. Assistant
    with st.chat_message("assistant"):
        with st.spinner("Reading Nutrition Tables from PDF files..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})