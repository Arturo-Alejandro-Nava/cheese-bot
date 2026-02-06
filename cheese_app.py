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
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER ---
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

# --- 1. GUARANTEED IMAGE BANK (THE FIX) ---
# These are the real, tested URLs. The AI must use THESE.
SAFE_IMAGES = {
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg", 
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OAXACA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_quarter_5lb.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Cryovac_5lb.png"
}

# --- 2. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/capabilities/"
    ]
    txt = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:4000]
        except: continue
    return txt

# --- 3. PDF/DOC HUNTER ---
@st.cache_resource(ttl=3600)
def process_documents():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    
    # We create a specific text block that tells the AI exactly what image corresponds to what PDF
    doc_image_map = "\n--- PDF VISUAL PREVIEWS (Use these filenames) ---\n"
    
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
                
                # Upload to AI Brain
                remote = genai.upload_file(path=local_name, display_name=filename_label)
                ai_files.append(remote)
                
                # Make Preview Image
                try:
                    doc = fitz.open(local_name)
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=150)
                    img_name = f"preview_{count}.png"
                    pix.save(img_name)
                    doc_image_map += f"DOCUMENT: {filename_label} -> IMAGE_FILE: {img_name}\n"
                except: pass
                
                count += 1
        
        # Wait for Files
        active_files = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    active_files.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active_files, doc_image_map

    except: return [], ""

# --- INITIAL LOAD ---
with st.spinner("Syncing Assets..."):
    web_text = get_website_text()
    files_for_ai, pdf_images_text = process_documents()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    
    # 4. CONSTRUCT THE MASTER IMAGE LIST FOR THE AI
    image_instruction = "--- MASTER IMAGE LIST (Use THESE URLs ONLY) ---\n"
    for name, url in SAFE_IMAGES.items():
        image_instruction += f"ITEM: {name} | URL: {url}\n"
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. MASTER IMAGE LIST (Below): Guaranteed working URLs.
    2. DOCUMENT PREVIEWS (Below): Local png files for Sell Sheets.
    3. PDF ATTACHMENTS: Read these for nutrition/numbers.
    4. WEBSITE TEXT: General info.
    
    RULES:
    1. **PLANT / FACTORY IMAGES**: If asked for the "Plant", "Factory", "Facility", or "Building":
       - YOU MUST use the URL listed next to 'PLANT' or 'FACTORY' in the MASTER IMAGE LIST below.
       - Syntax: `![The Plant]({SAFE_IMAGES['PLANT']})`
       - DO NOT GUESS A URL. If it's not in the list, show no image.
    
    2. **CHEESE IMAGES**: If asked for "Oaxaca" or "Fresco", use the matching URL from the Master List.
    
    3. **SELL SHEETS**: If asked for the Sell Sheet document, use the `preview_x.png` filename from the Document Previews list.
    
    4. **ACCURACY**: Read the PDF tables for specific numbers.
    5. **LANGUAGE**: English or Spanish.
    
    {image_instruction}
    
    {pdf_images_text}
    
    {web_text}
    """
    
    payload = [system_prompt] + files_for_ai + [question]
    
    try:
        response = model.generate_content(payload)
        return response.text
    except Exception as e:
        return "Searching visual database..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, products, or see the plant...")
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