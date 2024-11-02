import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF for extracting text from PDFs
import tempfile
import requests
from random import randint
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
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
genai.configure(api_key=api_key)
model_name = "gemini-1.5-flash"

# Session States
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []

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

# AI Content Generation
def generate_content(prompt):
    try:
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"

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
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        sample_pdf = genai.upload_file(pdf_path)
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
st.title("AI Teacher Chatbot Interface")
st.write("An AI-powered teacher that generates notes, answers questions, and creates quizzes.")

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

# Chatbot Interface for Authenticated
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
        num_pages = st.slider("Number of pages to use from the PDF:", min_value=1, max_value=20, value=5)

        if st.button("Generate Notes"):
            prompt = f"Generate detailed notes on {selected_topic} using up to {num_pages} pages."
            if comments:
                prompt += f" Additional instructions: {comments}"

            with st.spinner("Generating notes..."):
                notes = generate_content_with_file(prompt, pdf_path)
            st.session_state.chat_history.append({"role": "AI", "content": notes})
            save_message(st.session_state.user_id, "AI", notes)
            with st.expander("Generated Notes", expanded=True):
                st.text_area(notes, height=500)
            

    elif option == "Ask Doubt":
        question = st.text_input("Enter your question:")
        if st.button("Get Answer"):
            answer = generate_content(f"Answer this question: {question}")
            st.write(answer)
            st.session_state.chat_history.append({"role": "AI", "content": answer})
            save_message(st.session_state.user_id, "AI", answer)

    elif option == "Take Quiz":
        subject = st.text_input("Enter the subject for the quiz:")
        
        if st.button("Generate Quiz"):
            st.session_state.quiz = generate_quiz(subject)
            st.session_state.user_answers = [None] * len(st.session_state.quiz)

        if st.session_state.quiz:
            for i, q in enumerate(st.session_state.quiz):
                st.write(f"Q{i+1}: {q['question']}")
                st.session_state.user_answers[i] = st.radio(
                    f"Choose an answer for Question {i+1}:",
                    options=q["choices"],
                    key=f"q{i}"
                )

        if st.button("Submit Quiz") and st.session_state.quiz:
            correct, total = evaluate_quiz(st.session_state.user_answers, st.session_state.quiz)
            st.write(f"You scored {correct} out of {total}!")
            quiz_score_message = f"Quiz score: {correct}/{total}"
            st.session_state.chat_history.append({"role": "AI", "content": quiz_score_message})
            save_message(st.session_state.user_id, "AI", quiz_score_message)
