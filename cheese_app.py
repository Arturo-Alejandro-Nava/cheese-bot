import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time

# --- CONFIGURATION ---
# Use the secure key from Streamlit Secrets
API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER WITH LOGO ---
# The code looks for 'logo.jpg' (which is likely what your file is named)
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", width=500)
elif os.path.exists("logo.jpeg"):
    st.image("logo.jpeg", width=500)
else:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

# --- 1. LIVE TEXT SCRAPER (Reads the Website) ---
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
    combined_text = ""
    # Header for the bot's knowledge
    combined_text += "WEBSITE LINKS FOR NAVIGATION:\n"
    combined_text += "\n".join(urls) + "\n\n"
    
    for url in urls:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                # Extract text clean and stripped
                text = soup.get_text(separator=' ', strip=True)
                combined_text += f"\n--- SOURCE: {url} ---\n{text}\n"
        except:
            continue
    return combined_text

# --- 2. LIVE PDF HUNTER (Downloads Catalogs & Sell Sheets) ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    resource_url = "https://hcmakers.com/resources/"
    pdf_objects = []
    
    try:
        resp = requests.get(resource_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Find all PDF links on the resources page
        links = soup.find_all('a', href=True)
        pdf_urls = [link['href'] for link in links if link['href'].endswith('.pdf')]
        pdf_urls = list(set(pdf_urls)) # Remove duplicates
        
        # Process the top 3 PDFs found (Catalogs/Sell Sheets)
        for i, pdf_url in enumerate(pdf_urls[:3]): 
            try:
                pdf_data = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}).content
                temp_filename = f"temp_sheet_{i}.pdf"
                
                with open(temp_filename, "wb") as f:
                    f.write(pdf_data)
                    
                # Upload to Google for Vision processing
                remote_file = genai.upload_file(path=temp_filename, display_name=f"SellSheet_{i}")
                
                # Wait for file to process
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
# Displays a loading message while it goes to hcmakers.com
with st.spinner("Conectando con la base de datos de Nuestro Queso... (Syncing Live Data)"):
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
    
    # STRICT GROUNDING PROMPT
    # This instructs the bot to be Bilingual + Restricted to Company Data ONLY
    system_prompt = f"""
    You are the official Senior AI Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    YOUR KNOWLEDGE BASE:
    1. LIVE PDFS (Attached): I have attached the visual sell sheets and catalogs found on the website. Use these for spec sheets, pack sizes, and nutritional info.
    2. LIVE WEBSITE TEXT (Below): Use this for general info, contact emails, and quality standards.
    
    STRICT RULES (SECURITY & BEHAVIOR):
    1. **NO EXTERNAL KNOWLEDGE:** You must ONLY answer using facts present in the provided Website Text or PDF Files. Do NOT google outside info.
    2. **REFUSAL:** If the user asks something completely unrelated (e.g., "What is the capital of Spain?"), respectfully reply: "I can only answer questions related to Nuestro Queso products and services."
    3. **LANGUAGE DETECTION:** You are strictly bilingual. 
       - If the user writes in English -> Reply in English.
       - If the user writes in Spanish -> Reply in Spanish (Professional business Spanish).
    4. **NAVIGATION:** If a user asks for a specific product section, look at the URLs in the text and give them the link.
    5. **TONE:** Professional, proud (mention "World Class", "Gold Medals"), and helpful.
    
    WEBSITE TEXT CONTEXT:
    {web_text_data}
    """
    
    # We send: System Rules + The Downloaded PDF files + The User's Question
    content_package = [system_prompt] + live_pdf_files + [question]
    
    try:
        response = model.generate_content(content_package)
        return response.text
    except Exception as e:
        return "System is recalibrating (Google API refresh). Please ask again in 10 seconds."

# --- DISPLAY ---
# 1. Show conversation history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 2. Chat Input
user_input = st.chat_input("Ask about products... / Pregunta sobre nuestros productos...")

if user_input:
    # Show User message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Generate and Show AI message
    with st.chat_message("assistant"):
        with st.spinner("Consulting knowledge base / Consultando..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})