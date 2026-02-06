import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # PyMuPDF

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER (Logo + Title) ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo", "logo.jpg", "logo.png", "logo.jpeg"]
    for name in possible_names:
        if os.path.exists(name):
            st.image(name, width=130)
            break
    else:
        st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. MEDIA SCRAPER (Anti-Lazy-Load Version) ---
@st.cache_resource(ttl=3600) 
def get_website_media():
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/capabilities/", # Factory images here
        "https://hcmakers.com/products/",
        "https://hcmakers.com/quality/"
    ]
    
    # 1. HARDCODED SAFETY NET (Guaranteed URLs)
    # These override the scraper to ensure key questions never fail.
    safe_images = {
        "PLANT/FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "AERIAL VIEW": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
        "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
        "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
        "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
        "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
        "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png"
    }

    media_library = "\n--- OFFICIAL IMAGE LINKS ---\n"
    for k, v in safe_images.items():
        media_library += f"IMAGE: {k} | URL: {v}\n"

    # 2. LIVE SCRAPING
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            resp = requests.get(url, headers=headers)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Find Images (Checking data-src for WordPress lazy load)
            images = soup.find_all('img')
            for img in images:
                # Priority: data-src -> src
                src = img.get('data-src') or img.get('src')
                
                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    
                    # Filter junk
                    if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'spacer', 'facebook']):
                        continue
                    
                    alt = img.get('alt', 'Image')
                    # Only keep decent looking product/facility links
                    if "uploads" in src: 
                        media_library += f"IMAGE: {alt} | URL: {src}\n"
        except: continue
            
    return media_library

# --- 2. TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/capabilities/"
    ]
    txt = ""
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:4000]
        except: continue
    return txt

# --- 3. DOC HUNTER ---
@st.cache_resource(ttl=3600)
def process_live_documents():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    doc_previews = "\n--- PDF DOCUMENT PREVIEWS ---\n"
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 6
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            pdf_bytes = None
            filename_label = "Doc"
            
            try:
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    filename_label = href.split("/")[-1]
                elif href.endswith('.zip'):
                    z_data = requests.get(href, headers=headers).content
                    with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                        for f in z.namelist():
                            if f.endswith('.pdf'):
                                pdf_bytes = z.read(f)
                                filename_label = f
                                break
            except: continue

            if pdf_bytes:
                local_name = f"doc_{count}.pdf"
                with open(local_name, "wb") as f: f.write(pdf_bytes)
                
                # Upload to AI
                remote = genai.upload_file(path=local_name, display_name=filename_label)
                ai_files.append(remote)
                
                # Make Preview Image
                try:
                    doc = fitz.open(local_name)
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=100) # Lower dpi for speed
                    img_filename = f"preview_{count}.png"
                    pix.save(img_filename)
                    doc_previews += f"DOCUMENT PREVIEW: {filename_label} | FILENAME: {img_filename}\n"
                except: pass
                
                count += 1
        
        # Wait for Files
        ready_files = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    ready_files.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return ready_files, doc_previews

    except: return [], ""

# --- INITIAL LOAD ---
with st.spinner("Downloading Website Images, Text & Catalogs..."):
    # Scrapes Images, Text, and Documents in parallel logic
    media_library_text = get_website_media()
    site_text = get_website_text()
    live_docs, doc_images_text = process_live_documents()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. **IMAGE LINKS (Below):** A list of verified image URLs. 
    2. **DOCUMENT PREVIEWS:** Local png files for sell sheets.
    3. **PDF TEXT:** Read the attached files for data.
    
    RULES:
    1. **SHOWING THE PLANT/FACTORY:** If asked for an image of the plant/factory, use the URL listed under 'PLANT/FACTORY' in the OFFICIAL IMAGE LINKS. 
       - Syntax: `![The Plant](INSERT_URL_HERE)`
    
    2. **SHOWING CHEESE:** Use the specific URL from the OFFICIAL IMAGE LINKS.
    
    3. **SHOWING DOCS:** Use the 'FILENAME' from Document Previews list (e.g. `![Preview](preview_0.png)`).
    
    4. **ACCURACY:** Do not guess URLs. Only use the ones listed below.
    
    5. **LANGUAGE:** English or Spanish.
    
    IMAGE & MEDIA LIBRARY:
    {media_library_text}
    
    DOCUMENT PREVIEW LIBRARY:
    {doc_images_text}
    
    WEBSITE TEXT:
    {site_text}
    """
    
    payload = [system_prompt] + live_docs + [question]
    
    try:
        response = model.generate_content(payload)
        return response.text
    except Exception as e:
        return "Thinking..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about our products... / Pregunta...")
    submit = st.form_submit_button("Ask Agent")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding image..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})