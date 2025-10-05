import streamlit as st
from typing import List, Dict
from dataclasses import dataclass
import json
import os
from fpdf import FPDF
from perplexity import Perplexity
import time

# --- Data Structure ---
@dataclass
class Question:
    """Holds a single interview question with its details and sources."""
    question: str
    answer: str
    difficulty: str
    sources: List[str]

# --- Core AI Logic ---
class InterviewGenerator:
    """Uses Perplexity API to generate interview questions based on a curriculum."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Perplexity API key is required.")
        self.client = Perplexity(api_key=api_key)

    def generate_interview_questions(self, topic: str, curriculum: str) -> List[Question]:
        """
        Generates a structured list of interview questions for all difficulty levels.
        """
        # This is the master prompt that instructs the AI. It's the "brain" of our agent.
        prompt = f"""
        You are an expert technical interviewer and curriculum analyst. Your task is to generate a comprehensive set of interview questions based on the provided topic and curriculum.

        **Topic:**
        {topic}

        **Curriculum:**
        {curriculum}

        **Your Instructions:**
        1.  **Analyze the Curriculum:** Carefully review the curriculum to identify the most important concepts, technologies, and skills.
        2.  **Generate Questions:** Create exactly 11 questions for EACH of the following difficulty levels: "Beginner", "Intermediate", and "Expert". This means a total of 33 questions.
        3.  **Ensure Relevance:** Every question must be directly related to the provided curriculum.
        4.  **Research for Currency:** For each question, perform a quick, up-to-date search to ensure the answer reflects the latest industry standards and best practices.
        5.  **Provide Detailed Answers:** Each answer should be comprehensive, clear, and sufficient for an interviewer to validate a candidate's response.
        6.  **Cite Your Sources:** For EACH question, you MUST provide 1 to 3 direct URL sources that you used to verify the answer's accuracy and relevance.
        7.  **Strict JSON Output:** Your final output must be a single, valid JSON object and nothing else. Do not include any introductory text, apologies, or explanations outside of the JSON structure.

        **JSON Output Format:**
        {{
          "questions": [
            {{
              "difficulty": "Beginner",
              "question": "The first beginner-level question text...",
              "answer": "A detailed answer for the first question.",
              "sources": ["https://source-url-1.com", "https://source-url-2.com"]
            }},
            // ...10 more beginner questions...
            {{
              "difficulty": "Intermediate",
              "question": "The first intermediate-level question text...",
              "answer": "A detailed answer for the intermediate question.",
              "sources": ["https://source-url-3.com"]
            }}
            // ...10 more intermediate questions...
            {{
              "difficulty": "Expert",
              "question": "The first expert-level question text...",
              "answer": "A detailed answer for the expert question.",
              "sources": ["https://source-url-4.com", "https://source-url-5.com"]
            }}
            // ...10 more expert questions...
          ]
        }}
        """

        try:
            st.info("Sending request to Perplexity AI... This may take a minute or two.")
            response = self.client.chat.completions.create(
                model="llama-3-sonar-large-32k-online", # A powerful model with web access
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            content = response.choices[0].message.content
            
            # Clean and parse the JSON response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No valid JSON object found in the AI's response.")
            
            json_str = content[json_start:json_end]
            data = json.loads(json_str)
            
            # Convert JSON data to Question objects
            questions = [
                Question(
                    question=q["question"],
                    answer=q["answer"],
                    difficulty=q["difficulty"],
                    sources=q.get("sources", []) # Use .get for safety
                )
                for q in data["questions"]
            ]
            return questions

        except Exception as e:
            st.error(f"An error occurred while generating questions: {e}")
            st.error(f"Raw AI Response Content:\n{content}") # Show raw content for debugging
            return []

# --- PDF Generation ---
def generate_pdf(questions: List[Question], topic: str) -> str:
    """Creates a professional PDF from the list of questions."""
    
    class PDF(FPDF):
        def __init__(self, topic_name):
            super().__init__()
            self.topic_name = topic_name
            self.set_auto_page_break(auto=True, margin=15)

        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, f'Interview Questions: {self.topic_name}', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        def chapter_title(self, title):
            self.set_font('Arial', 'B', 16)
            self.set_fill_color(230, 230, 230)
            self.cell(0, 12, title, 0, 1, 'L', fill=True)
            self.ln(8)

        def question_entry(self, num, question_obj):
            # Question
            self.set_font('Arial', 'B', 12)
            self.multi_cell(0, 7, f"Q{num}: {question_obj.question}")
            self.ln(2)
            
            # Answer
            self.set_font('Arial', '', 11)
            self.multi_cell(0, 6, f"A: {question_obj.answer}")
            self.ln(2)

            # Sources
            if question_obj.sources:
                self.set_font('Arial', 'I', 9)
                self.set_text_color(0, 0, 255)
                for source in question_obj.sources:
                    self.multi_cell(0, 5, f"Source: {source}", link=source)
                self.set_text_color(0, 0, 0) # Reset color
            self.ln(8)

    pdf = PDF(topic)
    pdf.add_page()
    
    # Group questions by difficulty
    questions_by_difficulty = {
        "Beginner": [],
        "Intermediate": [],
        "Expert": []
    }
    for q in questions:
        if q.difficulty in questions_by_difficulty:
            questions_by_difficulty[q.difficulty].append(q)

    # Add content to PDF
    for difficulty, qs in questions_by_difficulty.items():
        if qs:
            pdf.chapter_title(f"{difficulty} Level Questions")
            for i, question_obj in enumerate(qs, 1):
                pdf.question_entry(i, question_obj)

    pdf_output_path = "interview_questions.pdf"
    pdf.output(pdf_output_path)
    return pdf_output_path

# --- Streamlit UI ---
def main():
    st.set_page_config(page_title="AI Interview Generator", layout="centered")

    st.title("🤖 AI Interview Question Generator")
    st.markdown("This agent uses a web-connected AI to generate relevant, up-to-date interview questions based on your specific curriculum.")

    with st.sidebar:
        st.header("⚙️ Configuration")
        # --- IMPORTANT ---
        # Add a placeholder for the Perplexity API key.
        # Replace "YOUR_PPLX_API_KEY_HERE" with your actual key.
        # You can get a key from: https://docs.perplexity.ai/
        pplx_api_key = st.text_input("Enter your Perplexity API Key", type="password", value=os.environ.get("PPLX_API_KEY", ""))

        st.info("This project is a demonstration of using a research-based AI to create high-quality, relevant interview materials.")

    topic = st.text_input("**1. Enter the Interview Topic**", placeholder="e.g., Data Science, Python Backend Development")
    curriculum = st.text_area("**2. Paste the Curriculum or Syllabus**", placeholder="Paste the detailed course outline, topics, and technologies here...", height=250)

    if st.button("Generate Interview PDF", use_container_width=True):
        if not pplx_api_key:
            st.error("Please enter your Perplexity API Key in the sidebar to continue.")
        elif not topic or not curriculum:
            st.warning("Please provide both a topic and a curriculum.")
        else:
            try:
                with st.spinner("Analyzing curriculum and generating 33 interview questions... This is a complex task and may take a few minutes. Please wait."):
                    generator = InterviewGenerator(api_key=pplx_api_key)
                    questions = generator.generate_interview_questions(topic, curriculum)
                
                if questions:
                    st.success(f"Successfully generated {len(questions)} questions!")
                    with st.spinner("Creating your professional PDF..."):
                        pdf_file_path = generate_pdf(questions, topic)

                    with open(pdf_file_path, "rb") as pdf_file:
                        st.download_button(
                            label="📥 Download Interview PDF",
                            data=pdf_file,
                            file_name=f"{topic.replace(' ', '_')}_Interview_Questions.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                else:
                    st.error("The AI failed to generate questions. Please check the logs or try a different input.")

            except Exception as e:
                st.error(f"A critical error occurred: {e}")

if __name__ == "__main__":
    main()
