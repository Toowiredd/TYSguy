# Microservices/APIGateway.py

from flask import Flask, request, jsonify
import pika
import os
import json
import jwt
from functools import wraps
import redis

app = Flask(__name__)

# Setup Redis for rate limiting
redis_client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=6379, db=0)

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(*args, **kwargs)
    return decorated

def rate_limit(limit=100, per=60):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = request.headers.get('User-ID')
            if not user_id:
                return jsonify({'message': 'User ID is missing!'}), 400
            
            key = f"rate_limit:{user_id}"
            count = redis_client.get(key)
            
            if count is None:
                redis_client.set(key, 1, ex=per)
            elif int(count) >= limit:
                return jsonify({'message': 'Rate limit exceeded!'}), 429
            else:
                redis_client.incr(key)
            
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.route('/task', methods=['POST'])
@token_required
@rate_limit()
def create_task():
    data = request.json
    if not data or 'content' not in data:
        return jsonify({'message': 'Invalid request'}), 400

    task = {
        'user_id': request.headers.get('User-ID'),
        'task_id': str(uuid.uuid4()),
        'content': data['content']
    }

    connection = connect_rabbitmq()
    channel = connection.channel()

    # Publish to all relevant queues
    queues = ['task_breakdown_queue', 'time_management_queue', 'focus_techniques_queue', 
              'learning_strategies_queue', 'emotional_regulation_queue']
    
    for queue in queues:
        channel.queue_declare(queue=queue)
        channel.basic_publish(exchange='', routing_key=queue, body=json.dumps(task))

    connection.close()

    return jsonify({'message': 'Task created successfully', 'task_id': task['task_id']}), 201

@app.route('/results/<task_id>', methods=['GET'])
@token_required
@rate_limit()
def get_results(task_id):
    # Here you would query your database (e.g., via Hasura) to get the aggregated results
    # This is a placeholder implementation
    results = {
        'task_id': task_id,
        'status': 'completed',
        'results': {
            'task_breakdown': ['Step 1', 'Step 2', 'Step 3'],
            'time_management': 'Use Pomodoro technique',
            'focus_techniques': 'Use noise-cancelling headphones',
            'learning_strategies': 'Create mind maps',
            'emotional_regulation': 'Practice deep breathing'
        }
    }
    return jsonify(results), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
