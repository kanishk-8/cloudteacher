import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google import genai
from dotenv import load_dotenv
import fitz  
import tempfile
import requests
from random import randint
import os
import streamlit.components.v1 as components
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import markdown2
import io
load_dotenv()

units = {
    "Unit I": [
        "Introduction to Cloud Computing",
        "Definition, Characteristics, Components",
        "Cloud Service provider",
        "Software As a Service (SAAS)",
        "Platform As a Service (PAAS)",
        "Infrastructure as a Service (IAAS)",
        "Load balancing and Resource optimization",
        "Comparison among Cloud computing platforms: Amazon EC2, Google App Engine, Microsoft Azure, Meghraj"
    ],
    "Unit II": [
        "Introduction to Cloud Technologies",
        "Study of Hypervisors",
        "SOAP and REST",
        "Webservices and Mashups",
        "Virtual machine technology",
        "Virtualization applications in enterprises",
        "Pitfalls of virtualization",
        "Multi-entity support",
        "Multi-schema approach",
        "Multi-tenancy using cloud data stores"
    ],
    "Unit III": [
        "Cloud security fundamentals",
        "Vulnerability assessment tool for cloud",
        "Privacy and Security in cloud",
        "Cloud computing security architecture",
        "Issues in cloud computing",
        "Intercloud environments",
        "QoS Issues in Cloud",
        "Streaming in Cloud",
        "Quality of Service (QoS) monitoring",
        "Inter Cloud issues"
    ],
    "Unit IV": [
        "MICEF Computing (Mist, IOT, Cloud, Edge and FOG Computing)",
        "Dew Computing: Concept and Application",
        "Case Study: MiCEF Computing Programs using CloudSim and iFogSim"
    ]
}

def export_notes_to_pdf(notes, filename="notes.pdf"):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    text = c.beginText(40, height - 40)
    text.setFont("Helvetica", 12)
    text.setLeading(14)
    
    for line in notes.splitlines():
        text.textLine(line)
    
    c.drawText(text)
    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

def markdown_to_pdf(notes_text):
    html_content = markdown2.markdown(notes_text)
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph(line, styles["BodyText"]) for line in html_content.splitlines() if line.strip()]
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

if not firebase_admin._apps:
    firebase_credentials = {
        "type": st.secrets["firebase_credentials"]["type"],
        "project_id": st.secrets["firebase_credentials"]["project_id"],
        "private_key_id": st.secrets["firebase_credentials"]["private_key_id"],
        "private_key": st.secrets["firebase_credentials"]["private_key"],
        "client_email": st.secrets["firebase_credentials"]["client_email"],
        "client_id": st.secrets["firebase_credentials"]["client_id"],
        "auth_uri": st.secrets["firebase_credentials"]["auth_uri"],
        "token_uri": st.secrets["firebase_credentials"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase_credentials"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase_credentials"]["client_x509_cert_url"]
    }
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
model_name = "gemini-1.5-flash"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []
if "temp_file_path" not in st.session_state:
    st.session_state["temp_file_path"] = None
if "uploaded_file_buffer" not in st.session_state:
    st.session_state["uploaded_file_buffer"] = None

def extract_pdf_text(pdf_path):
    try:
        text_content = ""
        with fitz.open(pdf_path) as pdf:
            for page_num in range(pdf.page_count):
                page = pdf[page_num]
                text_content += page.get_text() + "\n"
        return text_content
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"
def generate_quiz_questions(unit, topic, quiz_type,number):
    model=genai.GenerativeModel(model_name=model_name)
    prompt=f"Generate a {quiz_type} quiz on the {topic} of {number} questions, dont put in the answers"
    response = model.generate_content(prompt)
    return response.text if response else "No quiz generated."

def generate_content(prompt):
    try:
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"
def eval_quiz(questions, answers):
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    prompt=f"Are the answers attached correct for the questions: {questions}, give a score where each question is for one mark and then give feedback for each question also"
    sample_pdf = genai.upload_file(answers)
    response = model.generate_content([prompt, sample_pdf])
    return response

def firebase_login(email, password):
    try:
        api_key = st.secrets["FIREBASE_WEB_API_KEY"]
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        response = requests.post(url, json=payload)
        data = response.json()

        if response.status_code == 200:
            user_id = data['localId']
            st.session_state.user_id = user_id
            return user_id
        else:
            return None
    except Exception as e:
        st.error(f"Error during login: {str(e)}")
        return None

def firebase_signup(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return user
    except Exception as e:
        return str(e)

def generate_notes(topic, pdf_context):
    prompt = f"Generate detailed notes on {topic} using the following context: {pdf_context}"
    return generate_content(prompt)
def generate_content_with_file(prompt, pdf_path):
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        sample_pdf = genai.upload_file(pdf_path)
        response = model.generate_content([prompt, sample_pdf])
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"


def generate_quiz(subject):
    quiz_content = generate_content(f"Create a quiz for {subject} with answer choices and an answer key.")
    questions = [
        {
            "question": f"Sample Question {i+1} for {subject}?",
            "choices": ["Option A", "Option B", "Option C", "Option D"],
            "answer": randint(0, 3)
        }
        for i in range(3)
    ]
    return questions

def evaluate_quiz(user_answers, quiz):
    correct = sum(1 for i, answer in enumerate(user_answers) if answer == quiz[i]["answer"])
    return correct, len(quiz)

def load_chat_history(user_id):
    try:
        chat_doc = db.collection("chat_context").document(user_id).get().to_dict()
        return chat_doc.get("context", []) if chat_doc else []
    except Exception as e:
        st.error(f"Error loading chat history: {str(e)}")
        return []

def save_message(user_id, role, content):
    try:
        db.collection("chat_context").document(user_id).set({
            "context": firestore.ArrayUnion([{"role": role, "content": content}])
        }, merge=True)
    except Exception as e:
        st.error(f"Error saving message: {str(e)}")

st.set_page_config(layout="wide")
if "temp_file_path" not in st.session_state:
    st.session_state["temp_file_path"] = None
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None

if "user_id" in st.session_state:
    with st.sidebar:
        st.title("Chat History")
        chat_context = load_chat_history(st.session_state.user_id)
        
        if chat_context:
            st.session_state.chat_history = chat_context
        for i, message in enumerate(st.session_state.chat_history):
            short_heading = f"{message['role']}: {message['content'][:30]}..."
            with st.expander(short_heading):
                st.write(message['content'])

        user = auth.get_user(st.session_state.user_id)
        

        if st.button("Clear History"):
            try:
                db.collection("chat_context").document(st.session_state.user_id).set({"context": []})
                st.session_state.chat_history.clear()
                st.success("Chat history cleared!")
            except Exception as e:
                st.error(f"Error clearing history: {str(e)}")

        if st.button("Logout"):
            st.session_state.clear()
            if "temp_pdf_path" in st.session_state:
                os.remove(st.session_state.temp_pdf_path)
                del st.session_state.temp_pdf_path
            st.rerun()

st.title("CDEF TA")
st.write("An AI-powered teaching Assitant that generates notes, answers questions, and creates quizzes.")

if "user_id" not in st.session_state:
    st.subheader("Welcome! Please Login or Sign Up")
    auth_choice = st.selectbox("Choose an action", ["Login", "Sign Up"])

    if auth_choice == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_id = firebase_login(email, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.chat_history = load_chat_history(user_id)
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Login failed. Check your credentials.")

    elif auth_choice == "Sign Up":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Sign Up"):
            signup_result = firebase_signup(email, password)
            if isinstance(signup_result, str):
                st.error(f"Sign Up failed: {signup_result}")
            else:
                st.success("Account created successfully! Please log in.")

if "user_id" in st.session_state:
    option = st.selectbox("Choose an option:", ["Generate Notes", "Ask Doubt", "Take Quiz"])
    if option == "Generate Notes":
        selected_unit = st.selectbox("Select Unit", list(units.keys()))
        if selected_unit != "Select Unit":
            topics = units[selected_unit]
        else:
            topics = ["Select a Unit first"]
        selected_topic = st.selectbox("Select Topic", topics)
        pdf_file = st.file_uploader("Upload PDF for context (optional)")
        default_pdf_path = "./req/Master_Intro. to cloud computing 1.pdf"
        if pdf_file:
            if "temp_pdf_path" not in st.session_state:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                temp_file.write(pdf_file.getbuffer())
                st.session_state.temp_pdf_path = temp_file.name
            pdf_path = st.session_state.temp_pdf_path
        else:
            pdf_path = default_pdf_path

        comments = st.text_area("Additional comments or instructions (optional):")
        num_pages = st.slider("Number of words:", min_value=50, max_value=5000, value=5)

        if st.button("Generate Notes"):
            prompt = f"Generate detailed notes on {selected_topic} of approximately {num_pages} words. Use the attached pdf as knowledge base, if anything irrelevant is given in the prompt return irrelevant, if the pdf is related to the topic but the topic is not in the pdf, generate from your knowledge, dont write exactly as written in the pdf, rephrase, change or modify to avoid copyright"
            if comments:
                prompt += f" Additional instructions: {comments}"

            with st.spinner("Generating notes..."):
                notes = generate_content_with_file(prompt, pdf_path)
            st.session_state.chat_history.append({"role": "AI", "content": notes})
            save_message(st.session_state.user_id, "AI", notes)
            with st.expander("Generated Notes", expanded=True):
                st.markdown(notes, unsafe_allow_html=True)

            pdf_data = markdown_to_pdf(notes)
            st.download_button("Download as PDF", pdf_data, file_name="notes.pdf", mime="application/pdf")

    elif option == "Ask Doubt":
        question = st.text_input("Enter your question:")
        if st.button("Get Answer"):
            answer = generate_content(f"Answer this question: {question}, the question should be based around cloud computing, if it is not then respond-I can only answer questions related to Cloud, Dew, Edge, Fog computing")
            st.write(answer)
            st.session_state.chat_history.append({"role": "AI", "content": answer})
            save_message(st.session_state.user_id, "AI", answer)

    elif option == "Take Quiz":
        selected_unit = st.selectbox("Select Unit", list(units.keys()))
        topics = units[selected_unit] if selected_unit != "Select Unit" else ["Select a Unit first"]
        selected_topic = st.selectbox("Select Topic", topics)
        quiz_type = st.radio("Choose Quiz Type", ("Objective", "Subjective"))
        num_pages = st.slider("Number of questions:", min_value=5, max_value=20, value=5)

        if st.button("Generate Quiz"):
            with st.spinner("Generating quiz questions..."):
                questions = generate_quiz_questions(selected_unit, selected_topic, quiz_type, num_pages)
                with st.expander("Questions", expanded=True):
                    st.markdown(questions, unsafe_allow_html=True)
                
                with st.form(key="upload_form"):
                    file_type = st.radio("Upload answer as:", ["Image", "PDF"], key="file_type")
                    uploaded_file = st.file_uploader(
                        f"Upload {file_type} file for all questions",
                        type=["png", "jpg", "jpeg", "pdf"],
                        key="uploader_all"
                    )
                    submit_upload = st.form_submit_button("Submit File")

                if submit_upload and uploaded_file:
                    st.session_state["uploaded_file_buffer"] = uploaded_file.getbuffer()
                    suffix = ".pdf" if file_type == "PDF" else ".jpg"

                if st.session_state["uploaded_file_buffer"] and st.session_state["temp_file_path"] is None:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    temp_file.write(st.session_state["uploaded_file_buffer"])
                    temp_file.flush()  
                    st.session_state["temp_file_path"] = temp_file.name

                if st.session_state["temp_file_path"]:
                    response = eval_quiz(questions, st.session_state["temp_file_path"])
                    with st.expander("Evaluation", expanded=True):
                        st.markdown(response, unsafe_allow_html=True)