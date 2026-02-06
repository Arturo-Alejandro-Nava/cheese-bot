import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # This is PyMuPDF (The PDF-to-Image tool)

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("Secrets Error: Please add GOOGLE_API_KEY to Streamlit.")
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

# --- 1. MEDIA SCRAPER (Web Images) ---
@st.cache_resource(ttl=3600) 
def get_website_media():
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/contact-us/"
    ]
    media_text = "\n--- WEBSITE IMAGE LIBRARY (Use these URLs to show products) ---\n"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            resp = requests.get(url, headers=headers)
            soup = BeautifulSoup(resp.content, 'html.parser')
            images = soup.find_all('img', src=True)
            for img in images:
                src = img['src']
                if src.startswith('/'): src = "https://hcmakers.com" + src
                if any(x in src.lower() for x in ['product', 'cheese', 'fresco', 'panela', 'oaxaca']):
                    alt = img.get('alt', 'Cheese Image')
                    media_text += f"PRODUCT IMAGE: {alt} | LINK: {src}\n"
        except: continue
    return media_text

# --- 2. DEEP DOC & IMAGE GENERATOR (The PDF-to-Picture Engine) ---
@st.cache_resource(ttl=3600)
def process_documents():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Files for AI to read
    ai_files = []
    # Dictionary of Image Filenames to show the user
    pdf_previews_text = "\n--- DOWNLOADABLE DOCUMENT PREVIEWS (Images generated from PDFs) ---\n"
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 6
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            # Logic to handle PDFs inside Zips or direct Links
            pdf_bytes = None
            display_name = "Doc"
            
            try:
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    display_name = f"PDF_{count}"
                elif href.endswith('.zip'):
                    z_data = requests.get(href, headers=headers).content
                    with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                        for f in z.namelist():
                            if f.endswith('.pdf'):
                                pdf_bytes = z.read(f)
                                display_name = f
                                break # Just grab first one per zip
            except: continue

            if pdf_bytes:
                # 1. Save PDF locally for Gemini
                pdf_name = f"temp_doc_{count}.pdf"
                with open(pdf_name, "wb") as f: f.write(pdf_bytes)
                
                # 2. Upload to Gemini (The Brain)
                remote = genai.upload_file(path=pdf_name, display_name=display_name)
                ai_files.append(remote)
                
                # 3. GENERATE IMAGE SNAPSHOT (The "Eye")
                # This turns Page 1 of the PDF into a PNG Image
                try:
                    doc = fitz.open(pdf_name)
                    page = doc.load_page(0)  # Grab Page 1
                    pix = page.get_pixmap(dpi=150) # Take a screenshot
                    img_name = f"preview_doc_{count}.png"
                    pix.save(img_name)
                    
                    # Add to the text context so AI knows this image exists
                    pdf_previews_text += f"VISUAL DOCUMENT: {display_name} | IMAGE_FILENAME: {img_name}\n"
                except Exception as e:
                    print(f"Image gen failed: {e}")

                count += 1
                
        # Wait for Google processing
        final_files = []
        for f in ai_files:
            while f.state.name == "PROCESSING":
                time.sleep(1)
                f = genai.get_file(f.name)
            final_files.append(f)
            
        return final_files, pdf_previews_text

    except: return [], ""

# --- INITIAL LOAD ---
with st.spinner("Downloading Sell Sheets & Generating Preview Images..."):
    # This takes 20s but builds the image database
    web_images_text = get_website_media()
    files_for_ai, pdf_images_text = process_documents()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS AVAILABLE:
    1. **WEBSITE IMAGES:** URL links to images found on the website.
    2. **DOCUMENT PREVIEWS:** Local PNG images that show the first page of the Sell Sheets (Nutrition/Specs).
    
    RULES:
    1. **SHOWING IMAGES:** If the user asks to see a product or document, YOU MUST display the image.
       - Use this format: `![Description](FILENAME_OR_URL)`
       - If they want to see the Sell Sheet/Specs/Nutrition visual, use the `IMAGE_FILENAME` from the 'DOCUMENT PREVIEWS' list below.
       - If they want to see the Cheese product photo, use the 'URL' from the 'WEBSITE IMAGE LIBRARY'.
    
    2. **DATA ACCURACY:** Read the text inside the attached PDFs for specific numbers.
    3. **LANGUAGE:** English or Spanish.
    4. **SCOPE:** Strictly restricted to company info.
    
    {web_images_text}
    
    {pdf_images_text}
    """
    
    package = [system_prompt] + files_for_ai + [question]
    
    try:
        response = model.generate_content(package)
        return response.text
    except:
        return "Checking database..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, specs, or ask to SEE the documents...")
    submit = st.form_submit_button("Ask Sales Rep")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding visual proof..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})