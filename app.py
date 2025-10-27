#!/usr/bin/env python3
"""
Business Leadership Interview Questions Generator - FIXED & WORKING
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.colors import HexColor
import os
import logging
import re
import time
import json
import queue
import threading
import requests
from datetime import datetime

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'business-leadership-2025'

FIRECRAWL_API = "https://api.firecrawl.dev/v0/scrape"
update_queues = {}

class BusinessInterviewGenerator:
    """Generator for business leadership questions"""
    
    def __init__(self, gemini_key, firecrawl_key=None, progress_callback=None):
        self.gemini_key = gemini_key
        self.firecrawl_key = firecrawl_key or os.getenv('FIRECRAWL_API_KEY')
        self.progress_callback = progress_callback
        genai.configure(api_key=gemini_key)
        
        # Try models in order - use the one that works
        models_to_try = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro"]
        self.model = None
        
        for model_name in models_to_try:
            try:
                test_model = genai.GenerativeModel(model_name)
                logger.info(f"✅ Using model: {model_name}")
                self.model = test_model
                break
            except Exception as e:
                logger.warning(f"⚠️ {model_name} failed: {str(e)[:50]}")
                continue
        
        if not self.model:
            logger.error("❌ No available models!")
            raise Exception("No Gemini models available")
    
    def _send_progress(self, message, data=None):
        if self.progress_callback:
            self.progress_callback(message, data or {})
        logger.info(f"📡 {message}")
    
    def generate_question(self, topic, difficulty, question_type, web_context=None, max_retries=2):
        """Generate ONE business leadership question"""
        current_year = datetime.now().year
        
        if question_type == "theory":
            focus = f"""Generate ONE business theory question about {topic}."""
        else:
            focus = f"""Generate ONE practical business scenario about {topic}."""
        
        prompt = f"""{focus}

Difficulty: {difficulty}

IMPORTANT: Your response MUST follow this exact format:

Q: [40-70 word question here]

A: [120-180 word answer here]

Now generate:"""
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt+1}/{max_retries}")
                response = self.model.generate_content(prompt)
                text = response.text if hasattr(response, 'text') else ""
                
                logger.debug(f"Raw response: {text[:200]}")
                
                if not text or len(text) < 50:
                    logger.warning(f"Response too short")
                    time.sleep(1)
                    continue
                
                # FLEXIBLE PARSING - handle any format
                lines = text.split('\n')
                q_text = ""
                a_text = ""
                in_q = False
                in_a = False
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('Q:'):
                        in_q = True
                        in_a = False
                        q_text = line.replace('Q:', '').strip()
                    elif line.startswith('A:'):
                        in_a = True
                        in_q = False
                        a_text = line.replace('A:', '').strip()
                    elif in_q and line and not line.startswith('A:'):
                        q_text += " " + line
                    elif in_a and line and not line.startswith('Q:'):
                        a_text += " " + line
                
                # Clean up
                q_text = ' '.join(q_text.split())
                a_text = ' '.join(a_text.split())
                
                logger.debug(f"Parsed Q: {q_text[:100]}")
                logger.debug(f"Parsed A: {a_text[:100]}")
                
                # Validate
                if len(q_text) < 20:
                    logger.warning("Question too short")
                    time.sleep(1)
                    continue
                
                if len(a_text) < 50:
                    logger.warning("Answer too short")
                    time.sleep(1)
                    continue
                
                # Ensure answer ends with punctuation
                if not a_text[-1] in '.!?':
                    a_text += "."
                
                logger.info(f"✅ Generated {difficulty} {question_type}")
                return {'question': q_text, 'answer': a_text, 'type': question_type}
                
            except Exception as e:
                logger.error(f"Error attempt {attempt+1}: {str(e)[:100]}")
                time.sleep(1)
        
        logger.error(f"❌ Failed to generate {difficulty} {question_type}")
        return None
    
    def generate_all(self, topic, total_questions, difficulty_levels, balance_ratio=0.5):
        """Generate questions"""
        start_time = time.time()
        
        self._send_progress("🚀 Starting...", {'stage': 'start', 'progress': 0})
        
        # Calculate distribution
        questions_per_level = total_questions // len(difficulty_levels)
        remainder = total_questions % len(difficulty_levels)
        
        all_q = {}
        total_generated = 0
        
        for idx, difficulty in enumerate(difficulty_levels):
            level_count = questions_per_level + (1 if idx < remainder else 0)
            theory_count = int(level_count * balance_ratio)
            practical_count = level_count - theory_count
            
            self._send_progress(f"📊 {difficulty}...", 
                              {'stage': 'level_start', 'difficulty': difficulty, 
                               'progress': int((total_generated / total_questions) * 100)})
            
            questions = []
            
            # Generate theory
            for i in range(theory_count):
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Generating {difficulty} (Theory)...", 
                                  {'stage': 'generating', 'progress': progress})
                
                q = self.generate_question(topic, difficulty, 'theory', max_retries=2)
                
                if q:
                    questions.append(q)
                    total_generated += 1
                    self._send_progress(f"✅ {difficulty} Theory", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': q, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.5)
            
            # Generate practical
            for i in range(practical_count):
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Generating {difficulty} (Practical)...", 
                                  {'stage': 'generating', 'progress': progress})
                
                q = self.generate_question(topic, difficulty, 'practical', max_retries=2)
                
                if q:
                    questions.append(q)
                    total_generated += 1
                    self._send_progress(f"✅ {difficulty} Practical", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': q, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.5)
            
            all_q[difficulty] = questions
            self._send_progress(f"✅ {difficulty} done", {'stage': 'level_complete'})
        
        total_time = time.time() - start_time
        total = sum(len(q) for q in all_q.values())
        
        self._send_progress(f"🎉 Done! {total} questions in {total_time:.1f}s", 
                          {'stage': 'final', 'total': total, 'time_elapsed': round(total_time, 1), 'progress': 100})
        
        return all_q, total_time
    
    def create_pdf(self, topic, context, questions, difficulty_levels):
        """Create PDF"""
        pdf_start = time.time()
        
        filename = f"{topic.replace(' ', '_')[:50]}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        path = os.path.join(os.getcwd(), filename)
        
        try:
            doc = SimpleDocTemplate(path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('Title', parent=styles['Title'], 
                                        fontSize=24, textColor=HexColor('#2E86AB'), alignment=1)
            story.append(Paragraph(f"Leadership Interview: {topic}", title_style))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            for diff in difficulty_levels:
                if diff in questions and questions[diff]:
                    h_style = ParagraphStyle('Header', parent=styles['Heading1'], 
                                           fontSize=16, textColor=HexColor('#F24236'))
                    story.append(Paragraph(f"{diff} Level", h_style))
                    
                    for i, q in enumerate(questions[diff], 1):
                        q_type = q.get('type', 'general')
                        type_label = "🎓 Theory" if q_type == 'theory' else "💼 Practical"
                        
                        story.append(Paragraph(f"<b>Q{i} {type_label}:</b> {q['question']}", styles['Normal']))
                        story.append(Paragraph(f"<b>A:</b> {q['answer']}", styles['Normal']))
                        story.append(Spacer(1, 12))
            
            doc.build(story)
            
            pdf_time = time.time() - pdf_start
            logger.info(f"✅ PDF created in {pdf_time:.2f}s")
            
            return filename, pdf_time
        except Exception as e:
            logger.error(f"PDF error: {e}")
            return None, 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_stream', methods=['POST'])
def generate_stream():
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()
        gemini_key = data.get('api_key', '').strip() or os.getenv('GEMINI_API_KEY')
        firecrawl_key = data.get('firecrawl_key', '').strip() or os.getenv('FIRECRAWL_API_KEY')
        total_questions = int(data.get('total_questions', 20))
        difficulty_levels = data.get('difficulty_levels', ['Beginner', 'Intermediate', 'Advanced'])
        balance_ratio = float(data.get('balance_ratio', 0.5))
        
        if not topic or not gemini_key:
            return jsonify({'error': 'Topic and API key required'}), 400
        
        import uuid
        stream_id = str(uuid.uuid4())
        update_queues[stream_id] = queue.Queue()
        
        def generate_in_background():
            try:
                def progress_callback(message, data):
                    update_queues[stream_id].put({'message': message, 'data': data})
                
                gen = BusinessInterviewGenerator(gemini_key, firecrawl_key, progress_callback)
                all_q, gen_time = gen.generate_all(topic, total_questions, difficulty_levels, balance_ratio)
                
                update_queues[stream_id].put({
                    'message': 'COMPLETE',
                    'data': {
                        'stage': 'complete',
                        'questions': all_q,
                        'total': sum(len(q) for q in all_q.values()),
                        'generation_time': gen_time,
                        'difficulty_levels': difficulty_levels
                    }
                })
                
            except Exception as e:
                logger.error(f"Generation error: {e}")
                update_queues[stream_id].put({
                    'message': f'ERROR: {str(e)}',
                    'data': {'stage': 'error', 'error': str(e)}
                })
        
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()
        
        return jsonify({'success': True, 'stream_id': stream_id})
        
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream/<stream_id>')
def stream_updates(stream_id):
    def generate_events():
        if stream_id not in update_queues:
            yield f"data: {json.dumps({'error': 'Invalid stream'})}\n\n"
            return
        
        q = update_queues[stream_id]
        
        while True:
            try:
                update = q.get(timeout=30)
                yield f"data: {json.dumps(update)}\n\n"
                
                if update.get('message') in ['COMPLETE'] or update.get('message', '').startswith('ERROR'):
                    if stream_id in update_queues:
                        del update_queues[stream_id]
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'message': 'ping'})}\n\n"
    
    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    try:
        data = request.get_json()
        topic = data.get('topic', '')
        questions = data.get('questions', {})
        difficulty_levels = data.get('difficulty_levels', ['Beginner', 'Intermediate', 'Advanced'])
        api_key = data.get('api_key', '') or os.getenv('GEMINI_API_KEY')
        
        gen = BusinessInterviewGenerator(api_key)
        filename, pdf_time = gen.create_pdf(topic, '', questions, difficulty_levels)
        
        if not filename:
            return jsonify({'error': 'PDF failed'}), 500
        
        path = os.path.join(os.getcwd(), filename)
        return send_file(path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"PDF error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info("🔥 Business Leadership Interview Generator")
    logger.info(f"   Port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
