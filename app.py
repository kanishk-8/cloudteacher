import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as gena
from google import genai
from dotenv import load_dotenv
import fitz  # PyMuPDF for extracting text from PDFs
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
# Load environment variables
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

def markdown_to_pdf(notes_text):
    html_content = markdown2.markdown(notes_text)
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph(line, styles["BodyText"]) for line in html_content.splitlines() if line.strip()]
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# Firebase Initialization
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

# Google Generative AI Configuration
api_key = st.secrets["GEMINI_API_KEY"]
gena.configure(api_key=api_key)
model_name = "gemini-1.5-flash"

# Session States
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
# PDF Text Extraction
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
    model=gena.GenerativeModel(model_name=model_name)
    prompt=f"Generate a {quiz_type} quiz on the {topic} of {number} questions, dont put in the answers"
    response = model.generate_content(prompt)
    return response.text if response else "No quiz generated."
# AI Content Generation
def generate_content(prompt):
    try:
        client = genai.Client(api_key=api_key)
        MODEL_ID = "gemini-2.0-flash-exp"
        response = client.models.generate_content(
    model=MODEL_ID,contents=prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"
def eval_quiz(questions, answers):
    model = gena.GenerativeModel(model_name="gemini-1.5-flash")
    prompt=f"Are the answers attached correct for the questions: {questions}, generate a structured response with total score (each question has 1 mark), answer given, correct answer and explanation of the answer"
    sample_pdf = gena.upload_file(answers)
    response = model.generate_content([prompt, sample_pdf])
    return response
# Firebase Login
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

# Firebase Signup
def firebase_signup(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return user
    except Exception as e:
        return str(e)

# Notes Generation
def generate_notes(topic, pdf_context):
    prompt = f"Generate detailed notes on {topic} using the following context: {pdf_context}"
    return generate_content(prompt)
def generate_content_with_file(prompt, pdf_path):
    try:
        model = gena.GenerativeModel(model_name="gemini-1.5-flash")
        sample_pdf = gena.upload_file(pdf_path)
        response = model.generate_content([prompt, sample_pdf])
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"


# Quiz Creation and Evaluation
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

# Load and Save Chat History
def load_chat_history(user_id):
    try:
        chat_doc = db.collection("chat_context").document(user_id).get().to_dict()
        return chat_doc.get("context", []) if chat_doc else []
    except Exception as e:
        st.error(f"Error loading chat history: {str(e)}")
        return []

def save_message(user_id, role, content):
    try:
        # If the document doesn't exist, create it with an empty context array
        db.collection("chat_context").document(user_id).set({
            "context": firestore.ArrayUnion([{"role": role, "content": content}])
        }, merge=True)
    except Exception as e:
        st.error(f"Error saving message: {str(e)}")

# Streamlit Interface
st.set_page_config(layout="wide")
if "temp_file_path" not in st.session_state:
    st.session_state["temp_file_path"] = None
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None
# Sidebar and User Authentication
if "user_id" in st.session_state:
    with st.sidebar:
        st.title("Chat History")
        chat_context = load_chat_history(st.session_state.user_id)
        
        # Display chat history and save to session state
        if chat_context:
            st.session_state.chat_history = chat_context
        for i, message in enumerate(st.session_state.chat_history):
            short_heading = f"{message['role']}: {message['content'][:30]}..."
            with st.expander(short_heading):
                st.write(message['content'])

        user = auth.get_user(st.session_state.user_id)
        

        # Clear History Button
        if st.button("Clear History"):
            try:
                db.collection("chat_context").document(st.session_state.user_id).set({"context": []})
                st.session_state.chat_history.clear()
                st.success("Chat history cleared!")
            except Exception as e:
                st.error(f"Error clearing history: {str(e)}")

        # Logout Button
        if st.button("Logout"):
            st.session_state.clear()
            if "temp_pdf_path" in st.session_state:
                os.remove(st.session_state.temp_pdf_path)
                del st.session_state.temp_pdf_path
            st.rerun()

# Main Content
st.title("CDEF TA")
st.write("An AI-powered teaching Assitant that generates notes, answers questions, and creates quizzes.")

# Authentication Interface
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

# Chatbot Interface for Authenticate
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
            answer = generate_content(f"Answer this doubt based on Cloud computing: {question}, answer the doubt to the best of your knowledge do not ask for more context. If the asked doubt is not related to cloud computing output- I can only answer questions related to cloud, dew, edge, fog computing.")
            st.write(answer)
            st.session_state.chat_history.append({"role": "AI", "content": answer})
            save_message(st.session_state.user_id, "AI", answer)

    # Quiz generation
    elif option == "Take Quiz":
        # Step 1: Select unit, topic, and quiz type
        selected_unit = st.selectbox("Select Unit", list(units.keys()))
        topics = units[selected_unit] if selected_unit != "Select Unit" else ["Select a Unit first"]
        selected_topic = st.selectbox("Select Topic", topics)
        quiz_type = st.radio("Choose Quiz Type", ("Objective", "Subjective"))
        num_pages = st.slider("Number of questions:", min_value=5, max_value=20, value=5)

        # Step 2: Generate Quiz
        if st.button("Generate Quiz"):
            with st.spinner("Generating quiz questions..."):
                questions = generate_quiz_questions(selected_unit, selected_topic, quiz_type, num_pages)
                st.session_state["generated_questions"] = questions  # Save questions to session state
                st.session_state["quiz_generated"] = True  # Mark quiz as generated
                st.session_state["evaluation_result"] = None  # Reset any previous evaluation result

        # Step 3: Display generated questions if the quiz has been generated
        if st.session_state.get("quiz_generated", False):
            st.write("### Quiz Questions")
            st.markdown(st.session_state["generated_questions"], unsafe_allow_html=True)  # Display stored questions

            # Step 4: Upload answer file section
            st.write("### Submit Your Answers")
            file_type = st.radio("Upload answer as:", ["Image", "PDF"], key="file_type")
            uploaded_file = st.file_uploader(
                f"Upload {file_type} file for your answers",
                type=["png", "jpg", "jpeg", "pdf"],
                key="uploader_all"
            )

            # Step 5: Save the uploaded file to a temporary location
            if uploaded_file:
                st.session_state["uploaded_file_buffer"] = uploaded_file.getbuffer()
                st.session_state["suffix"] = ".pdf" if file_type == "PDF" else ".jpg"
                st.session_state["temp_file_path"] = None  # Reset temp file path for new submission

                # Write uploaded file to temp file if buffer exists
                if st.session_state["uploaded_file_buffer"]:
                    if st.session_state["temp_file_path"] is None:
                        suffix = st.session_state["suffix"]
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        temp_file.write(st.session_state["uploaded_file_buffer"])
                        temp_file.flush()
                        st.session_state["temp_file_path"] = temp_file.name

            # Step 6: Evaluate the quiz only if temp file path exists
            if st.session_state.get("temp_file_path"):
                if st.button("Evaluate Quiz"):
                    with st.spinner("Evaluating..."):
                        response = eval_quiz(st.session_state["generated_questions"], st.session_state["temp_file_path"])
                        st.session_state["evaluation_result"] = response.text  # Save evaluation result

        # Step 7: Display evaluation result if available
        if st.session_state.get("evaluation_result"):
            st.write("### Evaluation Result")
            st.markdown(st.session_state["evaluation_result"], unsafe_allow_html=True)