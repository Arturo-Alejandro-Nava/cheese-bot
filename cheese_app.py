import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import re  # <--- THIS WAS MISSING. I added it back.

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
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE AUTOMATIC UNZIPPER ---
@st.cache_resource(ttl=3600)
def auto_fetch_knowledge():
    status_text = st.empty() 
    status_text.text("🔍 Scanning website for documents...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    processed_files = []
    found_filenames = []
    
    # 1. TEXT SCRAPING
    web_text = "WEBSITE DATA:\n"
    for url in ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += soup.get_text(" ", strip=True)[:2000] + "\n"
        except: pass

    # 2. FILE HUNTING (ZIP Extraction)
    target_url = "https://hcmakers.com/resources/"
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Find links
        links = soup.find_all('a', href=True)
        zip_url = None
        
        # Prefer the ZIP file
        for link in links:
            if link['href'].endswith('.zip'):
                zip_url = link['href']
                break
        
        if zip_url:
            status_text.text("📦 Downloading Product Catalog...")
            z_resp = requests.get(zip_url, headers=headers)
            
            with zipfile.ZipFile(io.BytesIO(z_resp.content)) as z:
                file_count = 0
                for filename in z.namelist():
                    is_useful = filename.lower().endswith(".pdf") and any(x in filename.lower() for x in ["sheet", "fresco", "panela", "oaxaca", "cotija", "brochure", "spec"])
                    
                    if is_useful and file_count < 6: 
                        pdf_data = z.read(filename)
                        temp_name = f"extracted_{file_count}.pdf"
                        with open(temp_name, "wb") as f: f.write(pdf_data)
                        
                        remote = genai.upload_file(path=temp_name, display_name=filename)
                        processed_files.append(remote)
                        found_filenames.append(filename)
                        file_count += 1
            status_text.text(f"✅ Loaded {file_count} documents.")
        else:
            status_text.text("⚠️ Using website text only (No ZIP found).")

    except Exception as e:
        status_text.text("⚠️ Live Doc Error. Using backup mode.")
        
    time.sleep(1)
    status_text.empty() 
    return web_text, processed_files, found_filenames

# --- INITIAL LOAD ---
with st.spinner("Syncing Live Database..."):
    web_data, knowledge_docs, doc_names = auto_fetch_knowledge()

# --- 2. IMAGE LOADER ---
def get_image_response(raw_text):
    match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
    if match:
        filename = match.group(1).strip()
        
        # 1. HARDCODED WEB URLS (First Priority)
        # Use HTML injection to force browser to load these
        WEB_URLS = {
            "plant": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
            "factory": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
            "aerial": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
            "office": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
            "fries": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
            "bites": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
            "fresco": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
            "oaxaca": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png"
        }
        
        for key, url in WEB_URLS.items():
            if key in filename.lower():
                # HTML Hack to bypass Hotlink Protection
                st.markdown(f'''
                    <div style="border:1px solid #e6e6e6; border-radius:8px; padding:10px; width:fit-content;">
                        <img src="{url}" width="500" style="border-radius:5px;">
                    </div>
                ''', unsafe_allow_html=True)
                return
        
        # 2. LOCAL FILE FALLBACK (If you uploaded manual images)
        if os.path.exists(filename): st.image(filename, width=500)
        elif os.path.exists(filename + ".jpg"): st.image(filename + ".jpg", width=500)
        elif os.path.exists(filename + ".png"): st.image(filename + ".png", width=500)

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    doc_list_str = "\n".join(doc_names)
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    SOURCES:
    1. **PDFS (Unzipped from Website):** I have attached {len(knowledge_docs)} sell sheets. 
       - READ THE TABLES inside them for nutrition numbers. Do not guess.
    2. **WEBSITE TEXT:** Contact info and location.
    
    RULES:
    1. **ANSWER DATA:** If asked about Protein, Fat, or Pack Sizes, look at the PDF table. Read the number directly.
       - DO NOT ASK FOR CLARIFICATION. Just use the data from the first matching product found.
    
    2. **IMAGES:** 
       - If asked for Plant/Factory -> `<<<IMG: plant>>>`
       - If asked for Office -> `<<<IMG: office>>>`
       - If asked for Bites -> `<<<IMG: bites>>>`
       - If asked for Fries -> `<<<IMG: fries>>>`
       
    3. **LANG:** English or Spanish.
    
    WEBSITE CONTEXT:
    {web_data}
    """
    
    payload = [system_prompt] + knowledge_docs + [question]
    try: return model.generate_content(payload).text
    except: return "Extracting PDF data... ask again in 10 seconds."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_tag" in message:
            get_image_response(message["img_tag"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing Catalog..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            st.markdown(clean)
            
            img_tag = None
            if "<<<IMG:" in raw:
                img_tag = raw 
                get_image_response(raw)

            msg = {"role": "assistant", "content": clean}
            if img_tag: msg["img_tag"] = img_tag
            st.session_state.chat_history.append(msg)