import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time

# --- CONFIGURATION ---
API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER (Logo + Title) ---
# 1. Try to show the logo
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", width=600)
elif os.path.exists("logo.jpeg"):
    st.image("logo.jpeg", width=600)

# 2. Show the Text Title (Always)
st.title("Hispanic Cheese Makers-Nuestro Queso")

# --- 1. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/resources/",
        "https://hcmakers.com/category-knowledge/",
        "https://hcmakers.com/about-us/"
    ]
    combined_text = "WEBSITE NAVIGATION LINKS:\n" + "\n".join(urls) + "\n\n"
    
    for url in urls:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
                combined_text += f"\n--- SOURCE: {url} ---\n{text}\n"
        except:
            continue
    return combined_text

# --- 2. LIVE PDF HUNTER ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    resource_url = "https://hcmakers.com/resources/"
    pdf_objects = []
    
    try:
        resp = requests.get(resource_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        links = soup.find_all('a', href=True)
        pdf_urls = [link['href'] for link in links if link['href'].endswith('.pdf')]
        pdf_urls = list(set(pdf_urls))
        
        # Scrape top 3 Sell Sheets/Catalogs
        for i, pdf_url in enumerate(pdf_urls[:3]): 
            try:
                pdf_data = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}).content
                temp_filename = f"temp_sheet_{i}.pdf"
                
                with open(temp_filename, "wb") as f:
                    f.write(pdf_data)
                    
                remote_file = genai.upload_file(path=temp_filename, display_name=f"SellSheet_{i}")
                while remote_file.state.name == "PROCESSING":
                    time.sleep(1)
                    remote_file = genai.get_file(remote_file.name)
                
                if remote_file.state.name == "ACTIVE":
                    pdf_objects.append(remote_file)
            except:
                continue
            
    except Exception as e:
        print(f"PDF Error: {e}")
        
    return pdf_objects

# --- INITIAL LOAD ---
with st.spinner("Syncing Live Data (Website + Documents)..."):
    try:
        web_text_data = get_website_text()
        live_pdf_files = process_live_pdfs()
    except:
        web_text_data = "Error syncing. Retrying."
        live_pdf_files = []

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    
    # COMMERCIAL SYSTEM PROMPT (Strict + Bilingual)
    system_prompt = f"""
    You are the official Senior AI Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    KNOWLEDGE BASE:
    1. OFFICIAL DOCUMENTS: Attached PDF Sell Sheets (visual info).
    2. WEBSITE TEXT: Live content scraped below.
    
    RULES:
    1. **NO EXTERNAL INFO:** You must ONLY answer using facts present in the provided Text or PDF Files.
    2. **REFUSAL:** If asked about topics outside of the company/products, reply: "I can only answer questions related to Nuestro Queso."
    3. **LANGUAGE:** Detect user language. If Spanish -> Answer Spanish. If English -> Answer English.
    4. **ACCURACY:** Be precise about certifications (SQF Level 3), awards (Gold Medals), and contact info.
    
    WEBSITE CONTEXT:
    {web_text_data}
    """
    
    content_package = [system_prompt] + live_pdf_files + [question]
    
    try:
        response = model.generate_content(content_package)
        return response.text
    except Exception as e:
        return "System refreshing. Please ask again in 5 seconds."

# --- DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Ask about our cheese... / Pregunta sobre nuestros quesos...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})