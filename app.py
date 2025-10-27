#!/usr/bin/env python3
"""
Business Leadership Interview Questions Generator
FINAL OPTIMIZED: Concise prompts, quota fallback, syntax fixed
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

update_queues = {}

class BusinessInterviewGenerator:
    """Optimized generator with quota handling"""
    
    def __init__(self, gemini_key, progress_callback=None):
        self.gemini_key = gemini_key
        self.progress_callback = progress_callback
        genai.configure(api_key=gemini_key)
        
        # Fast, lightweight models
        models_to_try = ["gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro"]
        self.model = None
        
        for model_name in models_to_try:
            try:
                test_model = genai.GenerativeModel(model_name)
                logger.info(f"✅ Using model: {model_name}")
                self.model = test_model
                break
            except Exception as e:
                logger.warning(f"⚠️ {model_name} failed")
                continue
        
        if not self.model:
            raise Exception("No Gemini models available")
    
    def _send_progress(self, message, data=None):
        if self.progress_callback:
            self.progress_callback(message, data or {})
        logger.info(f"📡 {message}")
    
    def generate_question(self, topic, difficulty, question_type, max_retries=2):
        """Generate ONE concise question with quota detection"""
        
        # ULTRA-CONCISE PROMPTS (saves tokens)
        if question_type == "theory":
            prompt = f"""Topic: {topic}
Difficulty: {difficulty}
Type: Theory (concepts, principles)

Generate 1 CONCISE question & answer:
Q: [30-50 words]
A: [100-120 words, professional, complete]"""
        else:
            prompt = f"""Topic: {topic}
Difficulty: {difficulty}
Type: Practical (business scenario)

Generate 1 CONCISE scenario question & answer:
Q: [30-50 words with context]
A: [100-120 words, actionable, complete]"""
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text if hasattr(response, 'text') else ""
                
                if not text or len(text) < 50:
                    time.sleep(1)
                    continue
                
                # Parse Q&A
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
                    elif in_q and line:
                        q_text += " " + line
                    elif in_a and line:
                        a_text += " " + line
                
                q_text = ' '.join(q_text.split())
                a_text = ' '.join(a_text.split())
                
                if len(q_text) < 20 or len(a_text) < 50:
                    time.sleep(1)
                    continue
                
                if not a_text[-1] in '.!?':
                    a_text += "."
                
                # Type validation
                if question_type == "theory":
                    if any(word in q_text.lower() for word in ["your", "you are", "how would"]):
                        time.sleep(1)
                        continue
                else:
                    if not any(word in q_text.lower() for word in ["your", "company", "you", "scenario"]):
                        time.sleep(1)
                        continue
                
                logger.info(f"✅ Generated {difficulty} {question_type}")
                return {'question': q_text, 'answer': a_text, 'type': question_type}
                
            except Exception as e:
                error_msg = str(e)
                
                # QUOTA DETECTION
                if "429" in error_msg or "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                    logger.error(f"❌ QUOTA EXCEEDED")
                    return {'error': 'quota_exceeded', 'message': 'API quota limit reached. Please use a new API key.'}
                
                logger.error(f"Error: {error_msg[:100]}")
                time.sleep(1)
        
        return None
    
    def generate_all(self, topic, total_questions, difficulty_levels, balance_ratio=0.5):
        """Generate questions with quota fallback"""
        start_time = time.time()
        
        self._send_progress("🚀 Starting...", {'stage': 'start', 'progress': 0})
        
        questions_per_level = total_questions // len(difficulty_levels)
        remainder = total_questions % len(difficulty_levels)
        
        all_q = {}
        total_generated = 0
        quota_exceeded = False
        
        for idx, difficulty in enumerate(difficulty_levels):
            if quota_exceeded:
                break
                
            level_count = questions_per_level + (1 if idx < remainder else 0)
            theory_count = int(level_count * balance_ratio)
            practical_count = level_count - theory_count
            
            self._send_progress(f"📊 {difficulty}...", 
                              {'stage': 'level_start', 'difficulty': difficulty, 
                               'progress': int((total_generated / total_questions) * 100)})
            
            questions = []
            
            # Theory
            for i in range(theory_count):
                if quota_exceeded:
                    break
                    
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Theory Q{total_generated + 1}...", 
                                  {'stage': 'generating', 'progress': progress})
                
                result = self.generate_question(topic, difficulty, 'theory')
                
                if result and 'error' in result:
                    if result['error'] == 'quota_exceeded':
                        quota_exceeded = True
                        self._send_progress("❌ API Quota Exceeded - Please use a new API key", 
                                          {'stage': 'quota_error', 'error': 'quota_exceeded'})
                        break
                elif result:
                    questions.append(result)
                    total_generated += 1
                    self._send_progress(f"✅ Theory complete", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': result, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.2)
            
            # Practical
            for i in range(practical_count):
                if quota_exceeded:
                    break
                    
                progress = int((total_generated / total_questions) * 100)
                self._send_progress(f"Practical Q{total_generated + 1}...", 
                                  {'stage': 'generating', 'progress': progress})
                
                result = self.generate_question(topic, difficulty, 'practical')
                
                if result and 'error' in result:
                    if result['error'] == 'quota_exceeded':
                        quota_exceeded = True
                        self._send_progress("❌ API Quota Exceeded - Please use a new API key", 
                                          {'stage': 'quota_error', 'error': 'quota_exceeded'})
                        break
                elif result:
                    questions.append(result)
                    total_generated += 1
                    self._send_progress(f"✅ Practical complete", 
                                      {'stage': 'question_complete', 'difficulty': difficulty,
                                       'question': result, 'progress': int((total_generated / total_questions) * 100)})
                
                time.sleep(0.2)
            
            all_q[difficulty] = questions
            
            if not quota_exceeded:
                self._send_progress(f"✅ {difficulty} done", {'stage': 'level_complete'})
        
        total_time = time.time() - start_time
        total = sum(len(q) for q in all_q.values())
        
        if quota_exceeded:
            self._send_progress(f"⚠️ Stopped at {total} questions - API quota limit reached. Use a new key.", 
                              {'stage': 'quota_final', 'total': total, 'time_elapsed': round(total_time, 1), 
                               'progress': 100, 'error': 'quota_exceeded'})
        else:
            self._send_progress(f"🎉 Complete! {total} questions in {total_time:.1f}s", 
                              {'stage': 'final', 'total': total, 'time_elapsed': round(total_time, 1), 'progress': 100})
        
        return all_q, total_time
    
    def create_pdf(self, topic, questions, difficulty_levels):
        """Create PDF"""
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
            return filename
        except Exception as e:
            logger.error(f"PDF error: {e}")
            return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_stream', methods=['POST'])
def generate_stream():
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()
        gemini_key = data.get('api_key', '').strip() or os.getenv('GEMINI_API_KEY')
        total_questions = int(data.get('total_questions', 10))
        difficulty_levels = data.get('difficulty_levels', ['Beginner', 'Intermediate', 'Advanced'])
        balance_ratio = float(data.get('balance_ratio', 0.5))
        
        if not topic or not gemini_key:
            return jsonify({'error': 'Topic and API key required'}), 400
        
        if total_questions > 50:
            return jsonify({'error': 'Maximum 50 questions'}), 400
        
        import uuid
        stream_id = str(uuid.uuid4())
        update_queues[stream_id] = queue.Queue()
        
        def generate_in_background():
            try:
                def progress_callback(message, data):
                    update_queues[stream_id].put({'message': message, 'data': data})
                
                gen = BusinessInterviewGenerator(gemini_key, progress_callback)
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
                logger.error(f"Error: {e}")
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
                update = q.get(timeout=45)
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
        filename = gen.create_pdf(topic, questions, difficulty_levels)
        
        if not filename:
            return jsonify({'error': 'PDF creation failed'}), 500
        
        path = os.path.join(os.getcwd(), filename)
        return send_file(path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"PDF error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info("🚀 Business Leadership Interview Generator (Optimized)")
    app.run(host='0.0.0.0', port=port, debug=False)
