# app.py

from flask import Flask, request, jsonify
import os
import jwt
from functools import wraps
import requests
import uuid
from datetime import datetime, timedelta
import openai
import anthropic
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

# Configuration
app.config['JWT_SECRET'] = os.environ.get('JWT_SECRET', 'your-secret-key')
app.config['HASURA_ENDPOINT'] = os.environ.get('HASURA_GRAPHQL_ENDPOINT', 'http://localhost:8080/v1/graphql')
app.config['HASURA_ADMIN_SECRET'] = os.environ.get('HASURA_ADMIN_SECRET', 'your-admin-secret')
app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'your-openai-api-key')
app.config['ANTHROPIC_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY', 'your-anthropic-api-key')
app.config['GOOGLE_AI_API_KEY'] = os.environ.get('GOOGLE_AI_API_KEY', 'your-google-ai-api-key')
app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', 587))
app.config['SMTP_USERNAME'] = os.environ.get('SMTP_USERNAME', 'your-email@gmail.com')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD', 'your-email-password')

# Initialize AI clients
openai.api_key = app.config['OPENAI_API_KEY']
anthropic_client = anthropic.Anthropic(api_key=app.config['ANTHROPIC_API_KEY'])
genai.configure(api_key=app.config['GOOGLE_AI_API_KEY'])

# Initialize scheduler
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}
executors = {
    'default': ThreadPoolExecutor(20)
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults)
scheduler.start()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(data['user_id'], *args, **kwargs)
    return decorated

def get_hasura_client():
    headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': app.config['HASURA_ADMIN_SECRET']
    }
    return app.config['HASURA_ENDPOINT'], headers

def execute_hasura_query(query, variables=None):
    endpoint, headers = get_hasura_client()
    response = requests.post(endpoint, json={'query': query, 'variables': variables}, headers=headers)
    response.raise_for_status()
    return response.json()

@app.route('/')
def hello():
    return jsonify({"message": "Welcome to the ADHD 2E Agent System"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Invalid input'}), 400

    query = """
    mutation ($email: String!, $password: String!) {
      insert_users_one(object: {email: $email, password: $password}) {
        id
      }
    }
    """
    variables = {'email': data['email'], 'password': data['password']}
    
    try:
        result = execute_hasura_query(query, variables)
        return jsonify({'message': 'User created successfully', 'user_id': result['data']['insert_users_one']['id']}), 201
    except Exception as e:
        return jsonify({'message': 'Error creating user', 'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    auth = request.json
    if not auth or not auth.get('email') or not auth.get('password'):
        return jsonify({'message': 'Could not verify'}), 401

    query = """
    query ($email: String!, $password: String!) {
      users(where: {email: {_eq: $email}, password: {_eq: $password}}) {
        id
      }
    }
    """
    variables = {'email': auth['email'], 'password': auth['password']}
    
    try:
        result = execute_hasura_query(query, variables)
        if result['data']['users']:
            token = jwt.encode({
                'user_id': result['data']['users'][0]['id'],
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['JWT_SECRET'])
            return jsonify({'token': token})
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'message': 'Error during login', 'error': str(e)}), 500

@app.route('/task', methods=['POST'])
@token_required
def create_task(user_id):
    data = request.json
    if not data or 'content' not in data:
        return jsonify({'message': 'Invalid request'}), 400

    task = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'content': data['content']
    }

    # Process the task through our services
    breakdown = process_task_breakdown(task)
    time_management = process_time_management(task)
    focus_techniques = process_focus_techniques(task)
    learning_strategies = process_learning_strategies(task)
    emotional_regulation = process_emotional_regulation(task)

    # Combine results
    result = {
        'task_id': task['id'],
        'user_id': user_id,
        'content': task['content'],
        'task_breakdown': breakdown,
        'time_management': time_management,
        'focus_techniques': focus_techniques,
        'learning_strategies': learning_strategies,
        'emotional_regulation': emotional_regulation
    }

    # Save the result to the database
    query = """
    mutation ($task: tasks_insert_input!) {
      insert_tasks_one(object: $task) {
        id
      }
    }
    """
    variables = {'task': result}
    
    try:
        execute_hasura_query(query, variables)
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'message': 'Error saving task', 'error': str(e)}), 500

def process_task_breakdown(task):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that breaks down tasks for people with ADHD."},
            {"role": "user", "content": f"Break down this task into manageable steps: {task['content']}"}
        ]
    )
    return response.choices[0].message['content'].strip().split('\n')

def process_time_management(task):
    response = anthropic_client.completions.create(
        model="claude-3-sonnet-20240229",
        max_tokens=300,
        prompt=f"Human: Provide a time management strategy for the following task: {task['content']}\n\nAssistant:"
    )
    return response.completion.strip()

def process_focus_techniques(task):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(f"Suggest focus techniques for someone with ADHD to complete this task: {task['content']}")
    return response.text.strip()

def process_learning_strategies(task):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that provides learning strategies for people with ADHD."},
            {"role": "user", "content": f"Suggest learning strategies for someone with ADHD to learn about: {task['content']}"}
        ]
    )
    return response.choices[0].message['content'].strip()

def process_emotional_regulation(task):
    response = anthropic_client.completions.create(
        model="claude-3-sonnet-20240229",
        max_tokens=300,
        prompt=f"Human: Suggest emotional regulation strategies for someone with ADHD dealing with: {task['content']}\n\nAssistant:"
    )
    return response.completion.strip()

@app.route('/schedule', methods=['POST'])
@token_required
def schedule(user_id):
    data = request.json
    if not data or not data.get('task_id') or not data.get('schedule_time'):
        return jsonify({'message': 'Invalid input'}), 400

    scheduler.add_job(
        trigger_task, 
        'date', 
        run_date=data['schedule_time'], 
        args=[data['task_id']], 
        id=data['task_id']
    )

    return jsonify({'message': 'Task scheduled successfully'}), 200

@app.route('/reschedule', methods=['POST'])
@token_required
def reschedule(user_id):
    data = request.json
    if not data or not data.get('task_id') or not data.get('new_schedule_time'):
        return jsonify({'message': 'Invalid input'}), 400

    scheduler.reschedule_job(
        data['task_id'], 
        trigger='date', 
        run_date=data['new_schedule_time']
    )

    return jsonify({'message': 'Task rescheduled successfully'}), 200

@app.route('/cancel', methods=['POST'])
@token_required
def cancel(user_id):
    data = request.json
    if not data or not data.get('task_id'):
        return jsonify({'message': 'Invalid input'}), 400

    scheduler.remove_job(data['task_id'])

    return jsonify({'message': 'Task cancelled successfully'}), 200

def trigger_task(task_id):
    query = """
    query ($task_id: uuid!) {
      tasks_by_pk(id: $task_id) {
        id
        user_id
        content
      }
    }
    """
    variables = {'task_id': task_id}
    
    try:
        result = execute_hasura_query(query, variables)
        task = result['data']['tasks_by_pk']
        if task:
            # Process the task
            create_task(task['user_id'])
            # Send notification
            create_notification({
                'user_id': task['user_id'],
                'subject': 'Task Reminder',
                'body': f"Don't forget to work on your task: {task['content']}"
            })
    except Exception as e:
        print(f"Error triggering task: {str(e)}")

@app.route('/notify', methods=['POST'])
@token_required
def notify(user_id):
    data = request.json
    if not data or not data.get('subject') or not data.get('body'):
        return jsonify({'message': 'Invalid input'}), 400

    data['user_id'] = user_id
    return create_notification(data)

def create_notification(data):
    # Get user email
    query = """
    query ($user_id: uuid!) {
      users_by_pk(id: $user_id) {
        email
      }
    }
    """
    variables = {'user_id': data['user_id']}
    
    try:
        result = execute_hasura_query(query, variables)
        user = result['data']['users_by_pk']
        if user:
            send_email(user['email'], data['subject'], data['body'])
            return jsonify({'message': 'Notification sent successfully'}), 200
        else:
            return jsonify({'message': 'User not found'}), 404
    except Exception as e:
        return jsonify({'message': 'Error sending notification', 'error': str(e)}), 500

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = app.config['SMTP_USERNAME']
    msg['To'] = to_email

    with smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT']) as server:
        server.starttls()
        server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
        server.send_message(msg)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
