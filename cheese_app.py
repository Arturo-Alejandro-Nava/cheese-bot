import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import re

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
    possible = ["logo.jpg", "logo.png", "logo.jpeg"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE "PROXY" IMAGE DOWNLOADER ---
# This is the secret. It downloads the live website image to the server memory 
# and displays it. This bypasses the "Broken Image" security block.
def show_live_image(url):
    try:
        # Pretend to be a real browser so hcmakers.com doesn't block us
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            st.image(io.BytesIO(r.content), width=500)
        else:
            # Fallback if really strict blocking is active
            st.markdown(f"**Image Link:** [Click to view]({url})")
    except:
        st.markdown(f"**Image Link:** [Click to view]({url})")

# --- 2. LIVE ASSET HUNTER (Text + Images + PDFs) ---
@st.cache_resource(ttl=3600)
def live_site_scan():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. THE URLS TO SCAN
    pages = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory photos here
        "https://hcmakers.com/contact-us/",   # Office/Map here
        "https://hcmakers.com/quality/"
    ]

    # 2. IMAGE HUNTING
    image_catalog = "--- AVAILABLE LIVE WEBSITE IMAGES ---\n"
    web_text = "--- WEBSITE TEXT ---\n"
    
    seen_images = []
    
    for url in pages:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # A. Grab Text
            clean = soup.get_text(" ", strip=True)[:3000]
            web_text += f"\nPAGE: {url}\n{clean}\n"
            
            # B. Grab Images
            for img in soup.find_all('img'):
                src = img.get('data-src') or img.get('src')
                alt = img.get('alt', 'image').replace("\n", "")
                if not src: continue
                if src.startswith("/"): src = "https://hcmakers.com" + src
                
                # Deduplicate & Filter Junk
                if src in seen_images: continue
                if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'spacer', 'blank', 'facebook']): continue
                
                # Make the "AI Description" basically just the filename + alt text
                # This helps it find 'oaxaca-bites.png' even if Alt tag is empty
                fname = src.split("/")[-1]
                
                image_catalog += f"FILE: {fname} | ALT: {alt} | URL: {src}\n"
                seen_images.append(src)
        except: continue

    # 3. PDF HUNTING (Inside the Zip)
    doc_text = "--- DOCUMENTS FOUND ---\n"
    live_pdfs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Look for the big zip file
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_url:
            z_resp = requests.get(zip_url, headers=headers)
            with zipfile.ZipFile(io.BytesIO(z_resp.content)) as z:
                idx = 0
                for filename in z.namelist():
                    if filename.lower().endswith(".pdf") and idx < 5:
                        doc_text += f"- {filename}\n"
                        # Prepare for AI
                        with open(f"temp_{idx}.pdf", "wb") as f: f.write(z.read(filename))
                        live_pdfs.append(genai.upload_file(f"temp_{idx}.pdf", display_name=filename))
                        idx += 1
    except: pass
    
    return web_text, image_catalog, doc_text, live_pdfs

# --- INITIAL LOAD ---
with st.spinner("Scanning live website & unzipping catalogs..."):
    # This grabs EVERYTHING fresh from the web
    web_txt, img_lib, doc_list, pdf_files = live_site_scan()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    RESOURCES:
    {img_lib}
    {doc_list}
    
    RULES:
    1. **FINDING IMAGES:** If the user asks for an image, look at the 'AVAILABLE LIVE WEBSITE IMAGES' list.
       - Use "Fuzzy Search" on the 'FILE' name.
       - If asking for "Bites", look for 'OaxacaBites'.
       - If asking for "Office", look for 'display.jpg' or similar corporate image.
       - If asking for "Plant", look for '7777-1' or 'PLANT'.
       - **OUTPUT:** Start response with `<<<IMG: URL_HERE>>>`.
    
    2. **CONTACT INFO:**
       - Sales (Sandy): 847-258-0375
       - Marketing (Arturo): 847-502-0934
       - Office: 224-366-4320
       
    3. **DATA:** Use PDFs (attached) for nutrition specs.
    
    WEBSITE CONTEXT:
    {web_txt}
    """
    
    payload = [system_prompt] + pdf_files + [question]
    try:
        # We try-wait loop for active files
        for f in pdf_files:
             while f.state.name == "PROCESSING": time.sleep(1); f=genai.get_file(f.name)
        return model.generate_content(payload).text
    except: return "Retrieving data..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_url" in message:
            show_live_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing live data..."):
            raw = get_answer(user_input)
            
            # Detect tag
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            st.markdown(clean)
            
            url = None
            if match:
                url = match.group(1).strip()
                show_live_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_url"] = url
            st.session_state.chat_history.append(msg)