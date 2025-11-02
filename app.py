import streamlit as st
import os
from dotenv import load_dotenv
from modules.gemini_handler import GeminiHandler
from modules.question_generator import QuestionGenerator
from modules.pdf_generator import PDFGenerator
from modules.web_scraper import WebScraper
from modules.rag_handler import RAGHandler

load_dotenv()

st.set_page_config(
    page_title="Interview Questions Generator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        border-left: 4px solid #1f77b4;
        color: #0d3b66;
    }
    .tips-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        border-left: 4px solid #ff9800;
        color: #333333;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 0.5rem;
        color: #721c24;
    }
    </style>
""", unsafe_allow_html=True)

if "questions_generated" not in st.session_state:
    st.session_state.questions_generated = False
    st.session_state.questions_data = None

def main():
    st.markdown('<div class="main-header">🎯 Interview Questions Generator</div>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        data_source = st.radio(
            "Select Data Source",
            options=["Gemini Only", "Web Scraping + Gemini", "RAG + Gemini"],
            help="Choose how to enhance question generation with external data"
        )
        
        web_scraper_enabled = data_source == "Web Scraping + Gemini"
        rag_enabled = data_source == "RAG + Gemini"
        
        st.divider()
        st.subheader("API Configuration")
        
        api_key = st.text_input(
            "Gemini API Key",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="Get your API key from https://aistudio.google.com/app/apikey"
        )
        
        st.markdown("[Get your Gemini API Key here](https://aistudio.google.com/app/apikey) 🔑")
        
        if not api_key and not os.getenv("GEMINI_API_KEY"):
            st.warning("⚠️ Please provide a Gemini API Key")
        
        model_name = st.selectbox(
            "Select Gemini Model",
            options=[
                "models/gemini-2.5-flash",
                "models/gemini-2.5-pro",
                "models/gemini-2.5-flash-lite"
            ],
            help="Choose the Gemini model version (Flash is fastest & cheapest)"
        )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Question Generation Parameters")
        
        topic = st.text_input(
            "Interview Topic",
            placeholder="e.g., Python for Data Science",
            help="The main topic for which to generate interview questions"
        )
        
        context_input = st.text_area(
            "Sub-topics (one per line)",
            placeholder="e.g., NumPy\nPandas\nMatplotlib\nScikit-learn",
            help="Enter sub-topics related to your main topic"
        )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            num_questions = st.number_input(
                "Number of Questions",
                min_value=1,
                max_value=50,
                value=10,
                help="Total number of questions to generate"
            )
        
        with col_b:
            generic_percentage = st.slider(
                "Generic Questions %",
                min_value=0,
                max_value=100,
                value=60,
                step=5,
                help="Percentage of generic/theoretical questions vs practical questions"
            )
        
        practical_percentage = 100 - generic_percentage
        
        st.info(f"📊 Distribution: {generic_percentage}% Generic | {practical_percentage}% Practical Questions")
    
    with col2:
        st.subheader("📋 Quick Settings")
        
        difficulty_level = st.select_slider(
            "Difficulty Level",
            options=["Beginner", "Intermediate", "Advanced", "Expert"],
            value="Intermediate"
        )
        
        question_type = st.multiselect(
            "Question Types",
            options=[
                "Multiple Choice",
                "Short Answer",
                "Long Answer",
                "Code-based",
                "Scenario-based",
                "Debugging"
            ],
            default=["Short Answer", "Long Answer"],
            help="Select types of questions to include"
        )
        
        include_answers = st.checkbox(
            "Include Detailed Answers",
            value=True,
            help="Generate detailed answers for each question"
        )
    
    st.divider()
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        generate_button = st.button(
            "🚀 Generate Questions",
            use_container_width=True,
            type="primary"
        )
    
    if generate_button:
        if not topic:
            st.error("❌ Please enter a topic")
        elif not api_key and not os.getenv("GEMINI_API_KEY"):
            st.error("❌ Please provide a Gemini API Key")
        elif not question_type:
            st.error("❌ Please select at least one question type")
        else:
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("🔄 Initializing...")
                progress_bar.progress(10)
                
                gemini_handler = GeminiHandler(api_key or os.getenv("GEMINI_API_KEY"), model_name)
                question_generator = QuestionGenerator(gemini_handler)
                
                status_text.text("📝 Processing sub-topics...")
                progress_bar.progress(20)
                
                context = [c.strip() for c in context_input.split("\n") if c.strip()] if context_input else []
                
                enhanced_context = ""
                if web_scraper_enabled:
                    status_text.text("🌐 Fetching current data from web...")
                    progress_bar.progress(40)
                    scraper = WebScraper()
                    enhanced_context = scraper.scrape_topic(topic, context)
                    progress_bar.progress(60)
                elif rag_enabled:
                    status_text.text("📚 Retrieving context from knowledge base...")
                    progress_bar.progress(40)
                    rag = RAGHandler()
                    enhanced_context = rag.retrieve_context(topic, context)
                    progress_bar.progress(60)
                
                status_text.text("🤖 Generating questions with Gemini...")
                progress_bar.progress(70)
                
                questions_data = question_generator.generate_questions(
                    topic=topic,
                    context=context,
                    num_questions=num_questions,
                    generic_percentage=generic_percentage,
                    difficulty_level=difficulty_level,
                    question_types=question_type,
                    include_answers=include_answers,
                    enhanced_context=enhanced_context
                )
                
                progress_bar.progress(90)
                status_text.text("✅ Processing results...")
                progress_bar.progress(100)
                
                st.session_state.questions_generated = True
                st.session_state.questions_data = questions_data
                
                status_text.empty()
                progress_bar.empty()
                st.success("✅ Questions generated successfully!")
                    
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Error generating questions: {str(e)}")
    
    if st.session_state.questions_generated and st.session_state.questions_data:
        st.divider()
        st.subheader("📚 Generated Questions Preview")
        
        questions_data = st.session_state.questions_data
        
        for i, q_obj in enumerate(questions_data["questions"], 1):
            with st.expander(f"Question {i}: {q_obj['question'][:60]}...", expanded=False):
                st.write(f"**Type:** {q_obj.get('type', 'N/A')}")
                st.write(f"**Difficulty:** {q_obj.get('difficulty', 'N/A')}")
                st.write(f"**Category:** {q_obj.get('category', 'Generic' if q_obj.get('is_generic') else 'Practical')}")
                
                if include_answers and "answer" in q_obj:
                    st.markdown("**Answer:**")
                    st.write(q_obj["answer"])
        
        st.divider()
        
        st.subheader("📄 Export to PDF")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pdf_filename = st.text_input(
                "PDF Filename",
                value=f"Interview_Questions_{topic.replace(' ', '_')}",
                help="Name for your PDF file (without .pdf extension)"
            )
        
        with col2:
            include_metadata = st.checkbox(
                "Include Metadata",
                value=True,
                help="Include generation date, parameters, and metadata in PDF"
            )
        
        if st.button("📥 Generate PDF", use_container_width=True, type="secondary"):
            try:
                with st.spinner("📄 Creating PDF... Please wait"):
                    pdf_generator = PDFGenerator()
                    pdf_path = pdf_generator.generate_pdf(
                        questions_data=questions_data,
                        filename=pdf_filename,
                        include_metadata=include_metadata,
                        topic=topic,
                        difficulty=difficulty_level,
                        generic_percentage=generic_percentage
                    )
                    
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="⬇️ Download PDF",
                            data=pdf_file,
                            file_name=f"{pdf_filename}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    
                    st.success(f"✅ PDF created successfully!")
                    
            except Exception as e:
                st.error(f"❌ Error generating PDF: {str(e)}")
        
        st.divider()
        st.subheader("📊 Generation Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        generic_count = sum(1 for q in questions_data["questions"] if q.get("is_generic"))
        practical_count = len(questions_data["questions"]) - generic_count
        
        with col1:
            st.metric("Total Questions", len(questions_data["questions"]))
        with col2:
            st.metric("Generic Questions", generic_count)
        with col3:
            st.metric("Practical Questions", practical_count)
        with col4:
            st.metric("Generation Time", f"{questions_data.get('generation_time', 'N/A')}s")
    
    st.divider()
    st.markdown("""
    <div class="tips-box">
    <strong>💡 Tips:</strong><br/>
    - Provide specific sub-topics for more relevant questions<br/>
    - Adjust the generic/practical ratio based on your interview focus<br/>
    - Enable web scraping or RAG for more current and contextual questions<br/>
    - Review questions before sharing with candidates<br/>
    - Use ChromaDB for RAG to maintain up-to-date knowledge base
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
