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
    st.error("No API Key found in Secrets. Please add GOOGLE_API_KEY to Streamlit settings.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER & LOGO FIX ---
# We check all possible logo names. 
# Ensure your file on GitHub is named either 'logo.png', 'logo.jpg', or 'logo.jpeg'
col1, col2 = st.columns([1, 4])
with col2:
    st.title("Hispanic Cheese Makers")

with col1:
    logo_found = False
    possible_names = ["logo.png", "logo.jpg", "logo.jpeg", "logo"]
    for name in possible_names:
        if os.path.exists(name):
            st.image(name, width=150)
            logo_found = True
            break
    if not logo_found:
        st.write("🧀")

# --- 1. DEEP DOCUMENT HUNTER (THE BRAIN UPGRADE) ---
@st.cache_resource(ttl=3600)
def get_knowledge_assets():
    target_url = "https://hcmakers.com/resources/"
    valid_files = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        # Get page content
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Find every link ending in .zip or .pdf
        links = soup.find_all('a', href=True)
        
        count = 0
        limit = 8 # We allow up to 8 files to ensure we catch "Fresco" info
        
        for link in links:
            if count >= limit: break
            
            href = link['href']
            
            # DOWNLOADER LOGIC
            if href.endswith('.pdf') or href.endswith('.zip'):
                try:
                    # Download the file content
                    file_data = requests.get(href, headers=headers).content
                    
                    if href.endswith('.pdf'):
                        # Process Direct PDF
                        fname = f"web_doc_{count}.pdf"
                        with open(fname, "wb") as f: f.write(file_data)
                        
                        remote_file = genai.upload_file(path=fname, display_name=f"PDF_{count}")
                        valid_files.append(remote_file)
                        count += 1
                        
                    elif href.endswith('.zip'):
                        # Unzip and extract PDFs inside
                        with zipfile.ZipFile(io.BytesIO(file_data)) as z:
                            for zipped_name in z.namelist():
                                if zipped_name.lower().endswith(".pdf") and "sell" in zipped_name.lower():
                                    # Found a Sell Sheet inside a Zip
                                    with z.open(zipped_name) as source, open(f"unzipped_{count}.pdf", "wb") as target:
                                        target.write(source.read())
                                    
                                    remote_file = genai.upload_file(path=f"unzipped_{count}.pdf", display_name=f"Sheet_{zipped_name}")
                                    valid_files.append(remote_file)
                                    count += 1
                                    if count >= limit: break
                except:
                    continue
        
        # WAIT FOR PROCESSING
        # Google needs a second to "read" the files we just uploaded
        active_files = []
        for file_ref in valid_files:
            attempts = 0
            while file_ref.state.name == "PROCESSING" and attempts < 10:
                time.sleep(1)
                file_ref = genai.get_file(file_ref.name)
                attempts += 1
            if file_ref.state.name == "ACTIVE":
                active_files.append(file_ref)
                
        return active_files

    except Exception as e:
        return []

# --- 2. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600)
def get_website_text():
    urls = ["https://hcmakers.com/products/", "https://hcmakers.com/quality/", "https://hcmakers.com/contact-us/"]
    txt = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:3000] # Grab main text
        except: continue
    return txt

# --- INITIAL LOAD ---
with st.spinner("Accessing Database, Downloading Catalogs & Analyzing Specs..."):
    # This might take 15 seconds, but it grabs the REAL data
    live_files = get_knowledge_assets()
    live_text = get_website_text()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # THE AGGRESSIVE "NO-EXCUSES" PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers".
    
    SOURCE MATERIAL:
    1. I have attached the OFFICIAL SELL SHEETS (PDFs). Look at them VISUALLY. They contain the Nutrition Facts Tables.
    2. I have scraped the website text below.
    
    CRITICAL RULES:
    1. **READ THE TABLES:** If asked for "Grams of Protein", LOOK AT THE IMAGE OF THE NUTRITION TABLE in the PDF. The row says "Protein". Read the number.
    2. **DO NOT BE LAZY:** Do not say "I don't know." Do not ask the user "Which specific pack size" unless the nutrition is totally different. Usually, 1oz serving has the same protein regardless of pack size.
    3. **FIND THE MATCH:** If user asks for "Fresco", look for the PDF titled "Fresco" or the Sell Sheet image containing "Fresco".
    4. **ANSWER DIRECTLY:** Say: "According to the Fresco Sell Sheet, it contains [X]g of Protein."
    5. **LANGUAGE:** English or Spanish.
    
    WEBSITE CONTEXT:
    {live_text}
    """
    
    try:
        content_payload = [system_prompt] + live_files + [question]
        response = model.generate_content(content_payload)
        return response.text
    except:
        return "I am re-reading the document. Please ask one more time."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about specifications, nutrition, or products...")
    submit = st.form_submit_button("Ask Sales Rep")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Checking Sell Sheets..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})