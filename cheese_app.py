import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import glob

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

# --- HEADER (Branding) ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LIVE WEBSITE SCRAPER (Auto-Updates) ---
# This goes to the internet every hour to get the latest Text/Contacts
@st.cache_resource(ttl=3600) 
def get_live_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory Info
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",   # Latest Phone #s
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    
    combined_text = "--- LIVE WEBSITE CONTENT (Most Current Info) ---\n"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            # Get text and clean it
            text = soup.get_text(" ", strip=True)[:4000]
            combined_text += f"\nPAGE: {url}\nTEXT: {text}\n"
        except:
            continue
            
    return combined_text

# --- 2. LOCAL MANUAL PDF LOADER (Deep Spec Logic) ---
# This looks for PDFs you manually uploaded to GitHub
@st.cache_resource
def load_manual_pdfs():
    # Find all .pdf files in the folder
    pdf_files = glob.glob("*.pdf")
    active_knowledge_docs = []
    filenames = []

    if not pdf_files:
        return [], "No PDF documents found. Please upload Sell Sheets to GitHub."

    for pdf in pdf_files:
        try:
            # Upload to Gemini Brain
            remote_file = genai.upload_file(path=pdf, display_name=pdf)
            
            # Wait for Google to process the visual tables
            while remote_file.state.name == "PROCESSING":
                time.sleep(1)
                remote_file = genai.get_file(remote_file.name)
            
            if remote_file.state.name == "ACTIVE":
                active_knowledge_docs.append(remote_file)
                filenames.append(pdf)
        except:
            continue
            
    return active_knowledge_docs, ", ".join(filenames)

# --- INITIAL LOAD ---
with st.spinner("Syncing Live Website Text & Loading Manual Documents..."):
    # 1. Scrape the Web (Fast)
    live_web_text = get_live_website_text()
    
    # 2. Load the Manual PDFs (Accurate)
    ai_pdf_files, pdf_names = load_manual_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE SOURCE PRIORITY:
    1. **MANUAL PDF DOCUMENTS (Attached):** I have attached {len(ai_pdf_files)} PDF Sell Sheets ({pdf_names}). 
       - USE THESE FOR NUMBERS. 
       - If user asks about Protein, Fat, Calories, or Ingredients, READ THE TABLE inside the PDF.
       - *Example:* If Oaxaca spec sheet says "80 Calories", answer "80 Calories".
       
    2. **LIVE WEBSITE TEXT (Below):** Use this for current Contact Info, Address, and Marketing descriptions.
    
    BEHAVIOR:
    - **TEXT ONLY:** Do not try to show images. Be descriptive.
    - **ACCURACY:** Do not guess. If it's not in the PDF or Website, say "I don't have that specific spec on hand."
    - **LANGUAGE:** Respond in the language of the user (English/Spanish).
    
    LIVE WEBSITE DATA:
    {live_web_text}
    """
    
    # Send User Q + Prompt + The PDF Files to the Brain
    payload = [system_prompt] + ai_pdf_files + [question]
    
    try:
        return model.generate_content(payload).text
    except Exception as e:
        return "I am reviewing the documents. Please ask again in a moment."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about specs, nutrition, or company info...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User Msg
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI Msg
    with st.chat_message("assistant"):
        with st.spinner("Consulting Website & Documents..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})