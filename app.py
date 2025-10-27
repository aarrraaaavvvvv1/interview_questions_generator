#!/usr/bin/env python3
"""
Business Leadership Interview Questions Generator
Production-ready Flask app with RAG, Firecrawl, real-time streaming
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        logger.info("✅ Generator initialized")
    
    def _send_progress(self, message, data=None):
        if self.progress_callback:
            self.progress_callback(message, data or {})
        logger.info(f"📡 {message}")
    
    def search_current_content(self, topic, max_urls=2, timeout=10):
        """RAG: Retrieve current business content"""
        current_year = datetime.now().year
        current_context = []
        
        # Business-focused sources
        try_urls = [
            f"https://hbr.org/search?term={topic.replace(' ', '+')}",
            f"https://www.mckinsey.com/search?q={topic.replace(' ', '+')}",
        ]
        
        for url in try_urls[:max_urls]:
            try:
                content = self._scrape_with_firecrawl(url, timeout=timeout)
                if content and len(content) > 500:
                    current_context.append(content[:1500])
                    logger.info(f"✅ Scraped: {url[:50]}...")
                    if len(current_context) >= 1:
                        break
            except Exception as e:
                logger.warning(f"⚠️ Skip {url[:40]}")
                continue
        
        if current_context:
            combined = "\n\n".join(current_context)
            logger.info(f"✅ Web context: {len(combined)} chars")
            return combined
        
        logger.warning("⚠️ No web context, using LLM knowledge")
        return None
    
    def _scrape_with_firecrawl(self, url, timeout=10):
        """Firecrawl HTTP API"""
        if not self.firecrawl_key:
            return None
        
        try:
            response = requests.post(
                FIRECRAWL_API,
                headers={'Authorization': f'Bearer {self.firecrawl_key}'},
                json={'url': url, 'formats': ['markdown'], 'onlyMainContent': True},
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('markdown'):
                    content = data['markdown']
                    if len(content) > 200:
                        return content
        except Exception as e:
            logger.warning(f"Firecrawl error: {str(e)[:50]}")
        
        return None
    
    def generate_question(self, topic, difficulty, question_type, web_context=None, max_retries=2):
        """Generate ONE business leadership question"""
        current_year = datetime.now().year
        
        difficulty_context = {
            "Beginner": "foundational concepts",
            "Intermediate": "mid-level management",
            "Advanced": "C-suite strategic thinking for 15-18+ years experience"
        }
        
        context_text = ""
        if web_context:
            context_text = f"\n\nCurrent {current_year} business context:\n{web_context[:1000]}\n"
        
        if question_type == "theory":
            focus = f"""Generate a THEORETICAL question about {topic}.
- Focus on: Concepts, frameworks, best practices
- For business leaders with {difficulty_context[difficulty]}
- Business/management focused, not overly technical"""
        else:
            focus = f"""Generate a PRACTICAL, ANALYTICAL question about {topic}.
- Business scenario requiring strategic thinking
- For experienced leaders (15-18+ years)
- Include specific business context"""
        
        prompt = f"""{focus}{context_text}

**DIFFICULTY:** {difficulty}

Format EXACTLY:
Q: [40-70 words, business-appropriate question]

A: [120-180 words, complete professional answer ending with punctuation]

Generate now:"""
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text if hasattr(response, 'text') else ""
                
                if not text or len(text) < 100:
                    time.sleep(1)
                    continue
                
                q_match = re.search(r'Q:\s*(.+?)(?=\n\s*A:)', text, re.DOTALL | re.IGNORECASE)
                a_match = re.search(r'A:\s*(.+?)(?=\n\n|$)', text, re.DOTALL | re.IGNORECASE)
                
                if q_match and a_match:
                    question = ' '.join(re.sub(r'\*\*', '', q_match.group(1)).split())
                    answer = ' '.join(re.sub(r'\*\*', '', a_match.group(1)).split())
                    
                    if len(question) < 30 or len(answer) < 80:
                        continue
                    
                    if not answer.strip().endswith(('.', '!', '?')):
                        if len(answer) > 100:
                            answer += "."
                        else:
                            continue
                    
                    return {'question': question, 'answer': answer, 'type': question_type}
                
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Generate error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return None
    
    def generate_all(self, topic, total_questions, difficulty_levels, balance_ratio=0.5):
        """Generate questions with custom settings"""
        start_time = time.time()
        
        self._send_progress("🚀 Starting generation...", {'stage': 'start', 'progress': 0})
        
        # Get web context (RAG)
        web_context = None
        if self.firecrawl_key:
            self._send_progress("🔍 Fetching current content...", {'stage': 'web_search', 'progress': 0})
            web_context = self.search_current_content(topic, max_urls=2)
        
        if web_context:
            self._send_progress("✅ Using current insights", {'stage': 'web_found'})
        else:
            self._send_progress("Using LLM knowledge", {'stage': 'web_not_found'})
        
        # Calculate distribution
        questions_per_level = total_questions // len(difficulty_levels)
        remainder = total_questions % len(difficulty_levels)
        
        all_q = {}
        total_generated = 0
        
        for idx, difficulty in enumerate(difficulty_levels):
            level_count = questions_per_level + (1 if idx < remainder else 0)
            theory_count = int(level_count * balance_ratio)
            practical_count = level_count - theory_count
            
            self._send_progress(f"📊 {difficulty} level...", 
                              {'stage': 'level_start', 'difficulty': difficulty, 
                               'progress': int((total_generated / total_questions) * 100)})
            
            questions = []
            
            # Theory questions
            for i in range(theory_count):
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Generating {difficulty} (Theory)...", 
                                  {'stage': 'generating', 'progress': progress})
                
                q = self.generate_question(topic, difficulty, 'theory', web_context, max_retries=2)
                
                if q:
                    questions.append(q)
                    total_generated += 1
                    self._send_progress(f"✅ {difficulty} Theory", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': q, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.3)
            
            # Practical questions
            for i in range(practical_count):
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Generating {difficulty} (Practical)...", 
                                  {'stage': 'generating', 'progress': progress})
                
                q = self.generate_question(topic, difficulty, 'practical', web_context, max_retries=2)
                
                if q:
                    questions.append(q)
                    total_generated += 1
                    self._send_progress(f"✅ {difficulty} Practical", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': q, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.3)
            
            all_q[difficulty] = questions
            self._send_progress(f"✅ {difficulty} complete", {'stage': 'level_complete'})
        
        total_time = time.time() - start_time
        total = sum(len(q) for q in all_q.values())
        
        self._send_progress(f"🎉 Complete! {total} questions in {total_time:.1f}s", 
                          {'stage': 'final', 'total': total, 'time_elapsed': round(total_time, 1), 'progress': 100})
        
        return all_q, total_time
    
    def create_pdf(self, topic, context, questions, difficulty_levels):
        """Create professional PDF"""
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
        
        if total_questions < 1 or total_questions > 100:
            return jsonify({'error': 'Questions: 1-100'}), 400
        
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
        context = data.get('context', '')
        questions = data.get('questions', {})
        difficulty_levels = data.get('difficulty_levels', ['Beginner', 'Intermediate', 'Advanced'])
        api_key = data.get('api_key', '') or os.getenv('GEMINI_API_KEY')
        
        gen = BusinessInterviewGenerator(api_key)
        filename, pdf_time = gen.create_pdf(topic, context, questions, difficulty_levels)
        
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
