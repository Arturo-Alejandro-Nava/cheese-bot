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
    st.error("No API Key found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER (Logo + Exact Title) ---
col1, col2 = st.columns([1, 4])

with col1:
    # Logic to find your logo file whatever you named it
    possible_names = ["logo", "logo.jpg", "logo.png", "logo.jpeg"]
    for name in possible_names:
        if os.path.exists(name):
            st.image(name, width=130)
            break
    else:
        st.write("🧀")

with col2:
    # THE EXACT TITLE YOU REQUESTED
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---") # Divider line

# --- 1. DEEP DOCUMENT HUNTER (Scrapes PDFs & Zips) ---
@st.cache_resource(ttl=3600)
def get_knowledge_assets():
    target_url = "https://hcmakers.com/resources/"
    valid_files = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        count = 0
        limit = 6 
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            # Download Logic for PDFs and Zips
            if href.endswith('.pdf') or href.endswith('.zip'):
                try:
                    file_data = requests.get(href, headers=headers).content
                    
                    if href.endswith('.pdf'):
                        fname = f"doc_{count}.pdf"
                        with open(fname, "wb") as f: f.write(file_data)
                        remote_file = genai.upload_file(path=fname, display_name=f"PDF_{count}")
                        valid_files.append(remote_file)
                        count += 1
                        
                    elif href.endswith('.zip'):
                        # Extract PDFs from inside Zip
                        with zipfile.ZipFile(io.BytesIO(file_data)) as z:
                            for zipped_name in z.namelist():
                                if zipped_name.lower().endswith(".pdf") and count < limit:
                                    with z.open(zipped_name) as source, open(f"unzip_{count}.pdf", "wb") as target:
                                        target.write(source.read())
                                    
                                    remote_file = genai.upload_file(path=f"unzip_{count}.pdf", display_name=f"Sheet_{count}")
                                    valid_files.append(remote_file)
                                    count += 1
                except:
                    continue
        
        # Wait for Google to process files
        active_files = []
        for file_ref in valid_files:
            for _ in range(10): # Try for 10 seconds
                if file_ref.state.name == "ACTIVE":
                    active_files.append(file_ref)
                    break
                time.sleep(1)
                file_ref = genai.get_file(file_ref.name)
                
        return active_files

    except:
        return []

# --- 2. TEXT SCRAPER ---
@st.cache_resource(ttl=3600)
def get_website_text():
    urls = [
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/capabilities/"
    ]
    txt = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:3000]
        except: continue
    return txt

# --- INITIAL LOAD ---
with st.spinner("Downloading Sell Sheets & Syncing Database..."):
    # This grabs the PDFs live so the nutrition facts are available
    live_files = get_knowledge_assets()
    live_text = get_website_text()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # SYSTEM BRAIN
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    SOURCES:
    1. I have attached the OFFICIAL SELL SHEETS (Visual PDFs). 
       - READ THESE IMAGES. They contain the Nutritional Tables and Pack Specs.
    2. WEBSITE TEXT: For general info/contacts.
    
    RULES:
    1. **CHECK VISUALS:** If asked about Protein/Fat/Calories, LOOK AT THE PDF TABLE IMAGE explicitly.
    2. **SPECIFICITY:** Do not ask "Which Fresco?" unless totally necessary. Default to the most common one found in the documents (usually Natural or Round).
    3. **LANGUAGE:** Reply in the user's language (English or Spanish).
    4. **DIRECT ANSWER:** Answer the number immediately. Example: "Fresco contains 5g of Protein per 1oz serving."
    
    WEBSITE CONTEXT:
    {live_text}
    """
    
    # Payload: Prompt + PDFs + Question
    content_payload = [system_prompt] + live_files + [question]
    
    try:
        response = model.generate_content(content_payload)
        return response.text
    except:
        return "Database refreshing. Please ask again."

# --- CHAT UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, specs, or products...")
    submit = st.form_submit_button("Ask Sales Rep")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing PDF Tables..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})