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
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. PROXY IMAGE RENDERER (THE FIX) ---
def render_image(url):
    """
    Downloads the image on the Python server to bypass Hotlink/CORS blocks.
    Then displays the raw data.
    """
    if not url: return

    # Headers make us look like a real Chrome user visiting their site
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://hcmakers.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    try:
        # Download the bytes
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            # Display bytes directly
            st.image(io.BytesIO(r.content), width=500)
        else:
            # Last resort link
            st.markdown(f"**Image:** [View Link]({url})")
    except:
        st.markdown(f"**Image:** [View Link]({url})")

# --- 2. PRIORITY IMAGE LIST (Guaranteed correct images) ---
PRIORITY_MAP = {
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA SHRED": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. SCRAPER & PDF LOADER ---
@st.cache_resource(ttl=3600)
def load_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Scrape Text
    web_text = "WEBSITE DATA:\n"
    img_catalog = "ADDITIONAL IMAGES:\n"
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {u}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            # Scrape Extra Images
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    name = src.split("/")[-1]
                    img_catalog += f"FILE: {name} | URL: {src}\n"
        except: pass

    # Download PDFs
    docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Check ZIP
        zip_link = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                i = 0
                for fn in z.namelist():
                    if fn.lower().endswith(".pdf") and i < 6:
                        with open(f"temp_{i}.pdf", "wb") as f: f.write(z.read(fn))
                        docs.append(genai.upload_file(f"temp_{i}.pdf", display_name=fn))
                        i+=1
    except: pass

    return web_text, img_catalog, docs

# --- LOAD ---
with st.spinner("Connecting..."):
    text_data, scrap_img, pdf_assets = load_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # We prioritize the hardcoded list first
    priority_list = "\n".join([f"- KEY: {k} | URL: {v}" for k, v in PRIORITY_MAP.items()])

    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS:
    {priority_list}
    
    {scrap_img}
    
    RULES:
    1. **IMAGES:** 
       - Check 'ASSETS' list. Match user request (e.g. "Bites") to the KEY or FILE.
       - OUTPUT: `<<<IMG: URL_HERE>>>`
    
    2. **PLANT vs OFFICE:** 
       - "Office" = 'display.jpg'
       - "Plant/Factory" = '7777-1.jpg' or 'PLANT_138.jpg'
       
    3. **DATA:** Use PDFs.
    4. **LANG:** English/Spanish.
    
    WEBSITE CONTEXT:
    {text_data}
    """
    
    payload = [system_prompt] + pdf_assets + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_src" in message:
            render_image(message["img_src"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_image(url) # Render on server side

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_src"] = url
            st.session_state.chat_history.append(msg)