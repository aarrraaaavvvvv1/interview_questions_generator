from typing import List, Dict
import json
import os
from dataclasses import dataclass
from groq import Groq
import getpass

@dataclass
class Question:
    question: str
    answer: str
    difficulty: str
    topic: str

class InterviewGenerator:
    """Simplified interview generator that makes a single API call"""
    
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama3-70b-8192"
        
    def generate_interview(self, domain: str, difficulty: str, num_questions: int = 5) -> List[Question]:
        """Generate interview questions with a single API call"""
        prompt = f"""
        You are an expert in {domain}. Generate {num_questions} {difficulty}-level interview questions.
        Focus strictly on {domain} concepts without deviating into subfields.
        For example, if the domain is Data Science, stay within data science concepts 
        without focusing specifically on machine learning, statistics, or other subfields. 
        And whenever the same domain is given by user give different questions each and every time 
        based on the difficulty level.
        
        The response MUST be valid JSON in exactly this format, with no additional text:
        {{
            "domain": "{domain}",
            "questions": [
                {{
                    "question": "detailed question text",
                    "answer": "detailed answer explanation"
                }}
            ]
        }}

        Requirements:
        1. All questions must be specifically about {domain} at {difficulty} level
        2. Questions should cover gdifficulty level based concepts in {domain}
        3. Do not focus on specific subfields or subtopics
        4. Provide detailed, informative answers
        5. Generate exactly {num_questions} questions
        6. Ensure questions are appropriate for {difficulty} level interviews
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are a {difficulty}-level interview expert in {domain}. "
                                 f"Focus only on general {domain} concepts without deviating into specific subfields."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse JSON content
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Look for JSON-like structure
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = content[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    raise
            
            # Convert to Question objects
            questions = []
            for q in data["questions"]:
                questions.append(Question(
                    question=q["question"],
                    answer=q["answer"],
                    difficulty=difficulty,
                    topic=data["domain"]
                ))
            
            return questions
                
        except Exception as e:
            print(f"Error generating interview: {str(e)}")
            # Return a basic question if there's an error
            return [Question(
                question=f"Explain a fundamental concept in {domain}",
                answer="Please provide a comprehensive explanation.",
                difficulty=difficulty,
                topic=domain
            )]

def main():
    # Get API key from environment variable or user input
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\nGroq API Key Setup:")
        print("1. Go to https://console.groq.com to get your API key")
        print("2. Enter your API key below")
        api_key = getpass.getpass("Enter your Groq API key: ")
    
    generator = InterviewGenerator(api_key)
    
    # Get domain and number of questions
    domain = input("\nEnter the domain for interview questions (e.g., 'Data Science', 'Marketing'): ")
    
    # Get difficulty level
    while True:
        difficulty = input("Enter difficulty level (beginner/intermediate/expert): ").lower()
        if difficulty in ['beginner', 'intermediate', 'expert']:
            break
        print("Invalid difficulty. Please choose beginner, intermediate, or expert.")
    
    num_questions = int(input("How many questions would you like to generate? "))
    
    print(f"\nGenerating {num_questions} {difficulty}-level questions for {domain}...")
    questions = generator.generate_interview(domain, difficulty, num_questions)
    
    # Display results
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}")
        print(f"Domain: {question.topic}")
        print(f"Difficulty: {question.difficulty}")
        print(f"Q: {question.question}")
        print(f"A: {question.answer}")
        print("-" * 80)

if __name__ == "__main__":
    main()