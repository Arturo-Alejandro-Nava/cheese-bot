import streamlit as st
import google.generativeai as genai
import os
import requests
from bs4 import BeautifulSoup
import time
import io
import fitz  # PyMuPDF
import re
import glob # Helper to scan filenames

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. LOCAL IMAGE LOADER ---
def show_local_image(filename):
    if os.path.exists(filename):
        st.image(filename, width=500)
    else:
        # Retry with fuzzy matching logic if exact name isn't found
        all_files = os.listdir('.')
        for f in all_files:
            if filename.lower() in f.lower() and f.endswith(('.png', '.jpg', '.jpeg')):
                st.image(f, width=500)
                return

# --- 2. ASSET DISCOVERY (The Magic Logic) ---
@st.cache_resource(ttl=3600)
def inventory_assets():
    # A. List all local images (The 59 files you uploaded)
    image_files = glob.glob("*.jpg") + glob.glob("*.png") + glob.glob("*.jpeg") + glob.glob("*.webp")
    # Clean list (remove logo)
    image_files = [f for f in image_files if "logo" not in f]
    
    img_list_str = "AVAILABLE IMAGES:\n"
    for img in image_files:
        img_list_str += f"- {img}\n"

    # B. Text Knowledge
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/quality/"]
    web_text = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            web_text += s.get_text(" ", strip=True)[:3000] + "\n"
        except: pass

    # C. PDF Downloader
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        for i, link in enumerate(list(set(links))[:5]):
            try:
                data = requests.get(link).content
                path = f"doc_{i}.pdf"
                with open(path, "wb") as f: f.write(data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
        
        # Wait for processing
        active_pdfs = []
        for p in pdf_docs:
            for _ in range(10):
                if p.state.name == "ACTIVE": active_pdfs.append(p); break
                time.sleep(1)
                p = genai.get_file(p.name)
    except: active_pdfs = []

    return web_text, img_list_str, active_pdfs

# --- INITIAL LOAD ---
with st.spinner("Indexing 50+ Images & Syncing Data..."):
    web_txt, img_inventory, pdf_files = inventory_assets()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Verified contacts to prevent hallucinations
    contacts = """
    CONTACTS:
    - VP Sales (Sandy Goldberg): 847-258-0375
    - Marketing Dir (Arturo Nava): 847-502-0934
    - Office: 224-366-4320
    - Plant: 815-443-2100 (Kent, IL)
    """
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS AVAILABLE:
    {img_inventory}
    
    RULES:
    1. **IMAGES**: You have a list of 'AVAILABLE IMAGES' filenames.
       - If user asks for "Plant", look for 'PLANT', 'Factory', or '7777' filenames.
       - If user asks for "Fries", look for 'CheeseFries' or similar.
       - If user asks for "Office", look for 'display.jpg' or 'building'.
       - **OUTPUT:** `<<<IMG: exact_filename.jpg>>>`
    
    2. **DATA**: Use PDFs for numbers/specs.
    3. **LANGUAGE**: English or Spanish.
    4. **ACCURACY**: Use the provided CONTACTS list for phone numbers.
    
    {contacts}
    {web_txt}
    """
    
    payload = [system_prompt] + pdf_files + [question]
    try: return model.generate_content(payload).text
    except: return "Retrieving..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "img_file" in message:
            show_local_image(message["img_file"])
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Searching Asset Library..."):
            raw = get_answer(user_input)
            
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            img_file = None
            if match:
                img_file = match.group(1).strip()
                show_local_image(img_file)
            
            st.markdown(clean)
            
            msg = {"role": "assistant", "content": clean}
            if img_file: msg["img_file"] = img_file
            st.session_state.chat_history.append(msg)