# AI Interview Question Generator (v2.0)
This project is an advanced AI agent that generates comprehensive and currently relevant interview questions. It takes a topic and a detailed curriculum as input, uses a web-connected Large Language Model (Perplexity AI) to research and formulate questions, and outputs a professional, multi-level PDF document ready for use in technical interviews.

## Features
- Curriculum-Based: Questions are tailored specifically to the provided syllabus, ensuring high relevance.

- Always Up-to-Date: Leverages Perplexity's online models to ensure questions and answers reflect the latest industry standards.

- Multi-Level: Automatically generates 11 questions each for Beginner, Intermediate, and Expert levels in a single run.

- Sourced and Verifiable: Each question is accompanied by URL sources used by the AI, providing credibility and further reading.

- Professional PDF Output: Generates a clean, well-formatted PDF, perfect for sharing and printing.

## How to Run
1. Clone the repository.

2. Install the required libraries:

```pip install -r requirements.txt```

3. Get a Perplexity API Key:

- Visit Perplexity AI for developers to get your free API key.

4. Run the Streamlit application:

```streamlit run app.py```

5. Open your browser to the provided local URL, enter your API key in the sidebar, fill in the topic and curriculum, and click "Generate Interview PDF".
