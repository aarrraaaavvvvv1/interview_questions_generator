import streamlit as st
from typing import List
from dataclasses import dataclass
import json
import os
import requests
from urllib.parse import urlparse
from fpdf import FPDF
from openai import OpenAI
from typing import Optional
import time

@dataclass
class Question:
    question: str
    answer: str
    difficulty: str
    topic: str
    reference: str = ""  # Keep this for internal tracking

# API Configuration for different providers
API_CONFIGS = {
    "Groq - llama3-70b-8192": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama3-70b-8192",
        "api_key_prefix": "groq"
    },
    "OpenAI - GPT-4": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "api_key_prefix": "openai"
    },
    "OpenAI - GPT-3.5 Turbo": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "api_key_prefix": "openai"
    },
    "Groq - Deepseek-R1-70B": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "deepseek-r1-distill-llama-70b",
        "api_key_prefix": "groq"
    }
}

# Reference cache to avoid redundant API calls
reference_cache = {}

def is_valid_url(url):
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def validate_url(url, timeout=3):
    """Check if URL is accessible"""
    if not is_valid_url(url):
        return False
    
    try:
        # Just check the head to save time
        response = requests.head(url, timeout=timeout)
        return response.status_code < 400
    except:
        return False

def search_reference(query, topic):
    """Find relevant references using search APIs, prioritizing scholarly sources before Wikipedia"""
    cache_key = f"{topic}:{query[:50]}"

    # Check cache first
    if cache_key in reference_cache:
        return reference_cache[cache_key]

    # Try different search methods in priority order
    reference = ""

    # Method 1: Crossref for academic articles (skipping Semantic Scholar)
    try:
        crossref_params = {
            "query": f"{topic} {query}",
            "rows": 1,
            "sort": "relevance"
        }
        crossref_response = requests.get("https://api.crossref.org/works", params=crossref_params, timeout=5)

        if crossref_response.status_code == 200:
            results = crossref_response.json().get("message", {}).get("items", [])
            for item in results:
                if "URL" in item:
                    reference = item["URL"]
                    if validate_url(reference):
                        reference_cache[cache_key] = reference
                        return reference
    except Exception as e:
        print(f"Crossref API error: {str(e)}")

    # Method 2: Stack Overflow for technical questions
    if any(tech_term in topic.lower() for tech_term in ["programming", "code", "development", "software", "web", "data", "python", "javascript"]):
        try:
            so_url = f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q={topic}+{query}&site=stackoverflow"
            so_response = requests.get(so_url, timeout=5)

            if so_response.status_code == 200:
                items = so_response.json().get("items", [])
                if items:
                    reference = items[0].get("link")
                    if reference and validate_url(reference):
                        reference_cache[cache_key] = reference
                        return reference
        except Exception as e:
            print(f"Stack Overflow API error: {str(e)}")

    # Method 3 (Fallback): Wikipedia API (only if no other sources worked)
    try:
        wiki_query = f"{topic} {' '.join(query.split()[:5])}"
        wiki_response = requests.get(
            f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={wiki_query}&format=json"
        )

        if wiki_response.status_code == 200:
            results = wiki_response.json().get("query", {}).get("search", [])
            if results:
                title = results[0]["title"].replace(" ", "_")
                wiki_url = f"https://en.wikipedia.org/wiki/{title}"
                if validate_url(wiki_url):
                    reference_cache[cache_key] = wiki_url
                    return wiki_url
    except Exception as e:
        print(f"Wikipedia API error: {str(e)}")

    # Return empty if no reference found
    reference_cache[cache_key] = ""
    return ""


class InterviewGenerator:
    """Multi-model interview generator with consolidated references section"""
    
    def __init__(self, api_key: str, api_config: dict):
        self.api_key = api_key
        self.api_config = api_config
        
    def generate_interview(self, topic: str, difficulty: str, num_questions: int = 5) -> List[Question]:
        """Generate interview questions using selected model and search for a main reference"""
        prompt = f"""
        You are an expert in {topic}. Generate {num_questions} based on {difficulty}-level interview questions.
        Focus strictly on {topic} concepts without deviating into subfields.
        For example, if the topic is Data Science, stay within data science concepts 
        without focusing specifically on machine learning, statistics, or other subfields. 
        And whenever the same topic is given by user give different questions each and every time 
        based on the difficulty level.
        
        DO NOT INCLUDE ANY REFERENCES OR SOURCES IN YOUR ANSWERS. I will find references separately.
        
        The response MUST be valid JSON in exactly this format, with no additional text:
        {{
            "topic": "{topic}",
            "questions": [
                {{
                    "question": "detailed question text",
                    "answer": "detailed answer explanation"
                }}
            ]
        }}

        Requirements:
        1. All questions must be specifically about {topic} at {difficulty} level
        2. Questions should cover {difficulty} level based concepts in {topic}
        3. Do not focus on specific subfields or subtopics
        4. Provide detailed, informative answers
        5. Generate exactly {num_questions} questions
        6. Ensure questions are appropriate for {difficulty} level interviews
        7. DO NOT include any references, sources, or URLs in your response
        """
        
        try:
            # Initialize client with appropriate base URL
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_config["base_url"]
            )
            
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are a {difficulty}-level interview expert in {topic}. "
                                 f"Focus only on general {topic} concepts without deviating into specific subfields."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.api_config["model"],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean the response to ensure valid JSON
            content = content.replace('\n', ' ').replace('\r', '')
            
            # Remove any non-JSON text before or after the JSON object
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                content = content[start_idx:end_idx]
            
            # Parse the JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                print(f"Content causing error: {content}")
                raise
            
            # Just find one main reference for the topic
            with st.status(f"Finding main reference for {topic}...", expanded=False):
                main_reference = search_reference(topic, topic)
            
            # Convert to Question objects
            questions = []
            for idx, q in enumerate(data["questions"]):
                questions.append(Question(
                    question=q["question"],
                    answer=q["answer"],
                    difficulty=difficulty,
                    topic=topic,
                    reference="" # Individual references not needed in final output
                ))
            
            # Add one more question that contains the reference
            if main_reference:
                questions.append(Question(
                    question="References",
                    answer=f"For more information about {topic}, please refer to the following resource.",
                    difficulty=difficulty,
                    topic=topic,
                    reference=main_reference
                ))
            
            return questions
                
        except Exception as e:
            print(f"Error generating interview: {str(e)}")
            # Return a single fallback question
            return [Question(
                question=f"Please explain a key concept in {topic}",
                answer="This is a placeholder answer. Please try regenerating the questions.",
                difficulty=difficulty,
                topic=topic,
                reference=""
            )]

# Create PDF function
def generate_pdf(questions: List[Question]):
    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            self.is_first_page = True
            self.topic = questions[0].topic if questions else "Interview Questions"
            self.set_auto_page_break(auto=True, margin=15)
            
        def header(self):
            if not self.is_first_page:
                # Set text color to black for header
                self.set_text_color(0, 0, 0)
                self.set_font('Arial', 'B', 14)
                self.cell(0, 10, 'Interview Questions', 0, 1, 'C')
                self.ln(5)
                
        def footer(self):
            if not self.is_first_page:
                # Set text color to black for footer
                self.set_text_color(0, 0, 0)
                self.set_y(-25)

        def create_cover_page(self):
            # Background
            self.set_fill_color(0, 47, 255)
            self.rect(0, 0, 210, 297, 'F')
            
            # Company name
            self.set_text_color(255, 255, 255)
            self.set_font('Arial', 'B', 35)
            self.set_xy(20, 30)
            self.cell(0, 20, "accredian", 0, 1, 'C')
            
            # Tagline
            self.set_font('Arial', '', 18)
            self.set_xy(20, 45)
            self.cell(0, 10, "credentials that matter", 0, 1, 'C')
            
            # Title
            self.ln(60)
            self.set_font('Arial', 'B', 40)
            self.cell(0, 20, "Interview Questions", 0, 1, 'C')
            
            # topic
            self.ln(5)
            self.set_font('Arial', '', 35)
            self.cell(0, 15, self.topic, 0, 1, 'C')
            
            self.is_first_page = False

    # Initialize PDF
    pdf = PDF()
    
    # Add cover page
    pdf.add_page()
    pdf.create_cover_page()
    
    # Add content pages
    pdf.add_page()
    # Reset text color to black for content
    pdf.set_text_color(0, 0, 0)
    
    # Separate regular questions from the reference question
    regular_questions = [q for q in questions if q.question != "References"]
    reference_question = next((q for q in questions if q.question == "References"), None)
    
    # Content - Regular questions
    for i, question in enumerate(regular_questions, 1):
        # Question
        pdf.set_font('Arial', 'B', 13)
        pdf.multi_cell(0, 10, f"Question {i}:", 0)
        
        pdf.set_font('Arial', '', 12)
        pdf.multi_cell(0, 10, question.question)
        pdf.ln(5)
        
        # Answer
        # Set text color to red for the word "Answer:"
        pdf.set_text_color(255, 0, 0)  # RGB for red (255, 0, 0)

        # Set font to Arial, bold, size 13 for the label "Answer:"
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(0, 10, "Answer:", 0, 1)

        # Set text color to black for the content (default)
        pdf.set_text_color(0, 0, 0)  # RGB for black (0, 0, 0)

        # Set font to Arial, normal, size 12 for the content
        pdf.set_font('Arial', '', 12)
        
        # Handle code blocks in answer
        if "```" in question.answer:
            parts = question.answer.split("```")
            
            # Write text before first code block
            if parts[0].strip():
                pdf.multi_cell(0, 10, parts[0].strip())
                pdf.ln(5)
            
            # Process code blocks
            for j in range(1, len(parts), 2):
                if j < len(parts):
                    code = parts[j].strip()
                    
                    # Set gray background for code
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font('Courier', '', 10)
                    
                    # Split code into lines and write each line
                    code_lines = code.split('\n')
                    for line in code_lines:
                        pdf.multi_cell(0, 7, line.rstrip(), fill=True)
                    
                    pdf.ln(5)
                    
                    # Reset for normal text
                    pdf.set_font('Arial', '', 12)
                    
                    # Write text after code block
                    if j + 1 < len(parts) and parts[j + 1].strip():
                        pdf.multi_cell(0, 10, parts[j + 1].strip())
                        pdf.ln(5)
        else:
            pdf.multi_cell(0, 10, question.answer)
        
        # Add spacing between questions
        pdf.ln(10)
        
        # Add separator line between questions
        if i < len(regular_questions):
            pdf.set_draw_color(200, 200, 200)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(10)
    
    # Modify the reference section in the generate_pdf function:
    if reference_question and reference_question.reference:
        pdf.ln(10)
        pdf.set_draw_color(0, 0, 0)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(15)
        
        # References header - Modern Web Style
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, "Further Reading", 0, 1, 'L')
        pdf.ln(5)
        
        # Topic heading
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"{questions[0].topic} Fundamentals", 0, 1, 'L')
        
        # Reference link
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(0, 0, 255)  # Blue for references
        pdf.cell(0, 10, f"[View Article]({reference_question.reference})", 0, 1, 'L', link=reference_question.reference)

        # Save the PDF
        pdf_output = "/tmp/interview_questions.pdf"
        pdf.output(pdf_output)
        return pdf_output

# Streamlit UI
def main():
    st.set_page_config(page_title="Interview Question Generator", layout="wide")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        # Add app info
        st.info("""
        **About this app**
        
        Generate interview questions with detailed answers. 
        Each set comes with verified references and can be downloaded as a professionally formatted PDF.
        """)
        # Model selection
        selected_model = st.selectbox(
            "Select Model",
            options=list(API_CONFIGS.keys()),
            index=0
        )
        
        # API key based on selected model
        api_key_prefix = API_CONFIGS[selected_model]["api_key_prefix"]
        api_key_label = f"Enter {api_key_prefix.capitalize()} API Key:"
        api_key = st.text_input(api_key_label, type="password")
        
        # Other config options
        topic = st.text_input("Enter topic (e.g., Data Science)")
        difficulty = st.selectbox("Select Difficulty", ["Beginner", "Intermediate", "Expert"])
        num_questions = st.text_input("Number of Questions", value="5")
        # Convert to integer safely
        try:
            num_questions = int(num_questions)
        except ValueError:
            num_questions = 5  # Default value if input is invalid
        
        with st.expander("Advanced Options"):
            use_cache = st.checkbox("Use reference cache", value=True, 
                                   help="Reuse previously found references for similar questions")
            clear_cache = st.button("Clear Reference Cache")
            if clear_cache:
                reference_cache.clear()
                st.success("Reference cache cleared!")
        
        generate_btn = st.button("Generate Questions")
    
    st.markdown("## 🎓 Interview Questions Generator")
    model_info = f"Using: {selected_model}"
    st.write(f"Generate topic-specific interview questions with detailed answers and a single reference section. {model_info}")
    
    if not api_key:
        st.warning(f"⚠️ Please enter your {api_key_prefix.capitalize()} API Key to proceed.")
        return
    
    if generate_btn:
        with st.spinner(f"Generating {num_questions} {difficulty}-level questions for {topic} using {selected_model}..."):
            try:
                api_config = API_CONFIGS[selected_model]
                generator = InterviewGenerator(api_key, api_config)
                
                # If cache is disabled, clear it before generating
                if not use_cache:
                    reference_cache.clear()
                
                questions = generator.generate_interview(topic, difficulty, int(num_questions))
                
                if questions:
                    # Filter out the reference question for display
                    display_questions = [q for q in questions if q.question != "References"]
                    reference_question = next((q for q in questions if q.question == "References"), None)
                    
                    # Display questions without references
                    for i, q in enumerate(display_questions, 1):
                        with st.expander(f"Question {i}"):
                            st.write(f"**Q:** {q.question}")
                            st.write(f"**A:** {q.answer}")
                    
                    # Display reference section if available
                    # Display reference section if available
                    if reference_question and reference_question.reference:
                        st.write("---")
                        st.write("### 📚 Further Reading")
                        st.write(f"**{topic} **")
                        st.markdown(f"({reference_question.reference})")
                        
                        # Count reference sources for analytics
                        domain = urlparse(reference_question.reference).netloc
                        reference_source = "Wikipedia" if "wikipedia" in domain else \
                                        "Stack Overflow" if "stackoverflow" in domain else \
                                        "Crossref" if ("crossref" in domain or "doi.org" in domain) else \
                                        "Documentation" if any(doc in domain for doc in ["docs.", "documentation", "developer."]) else \
                                        "Other"
                        
                        st.write(f"Source type: {reference_source}")
                    
                    # Generate and offer PDF download
                    pdf_file = generate_pdf(questions)
                    with open(pdf_file, "rb") as file:
                        st.download_button(
                            "📥 Download PDF",
                            file,
                            file_name="interview_questions.pdf",
                            mime="application/pdf"
                        )
                        
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.error("Please try again with different parameters.")
    
if __name__ == "__main__":
    main()