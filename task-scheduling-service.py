# Microservices/TaskSchedulingService.py

from flask import Flask, request, jsonify
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import jwt
from functools import wraps

app = Flask(__name__)

# Configure APScheduler
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
            data = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(data['user_id'], *args, **kwargs)
    return decorated

def get_hasura_client():
    hasura_endpoint = os.getenv('HASURA_GRAPHQL_ENDPOINT')
    hasura_admin_secret = os.getenv('HASURA_ADMIN_SECRET')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': hasura_admin_secret
    }
    return hasura_endpoint, headers

def trigger_task(task_id):
    # This function will be called by the scheduler when it's time to execute a task
    hasura_endpoint, headers = get_hasura_client()
    
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
    response = requests.post(hasura_endpoint, json={'query': query, 'variables': variables}, headers=headers)
    task = response.json()['data']['tasks_by_pk']
    
    if task:
        # Trigger the task processing pipeline
        # This could involve sending messages to RabbitMQ queues, as in our previous setup
        print(f"Triggering task: {task['id']} for user: {task['user_id']}")
        # Add your task triggering logic here

@app.route('/schedule', methods=['POST'])
@token_required
def schedule_task(user_id):
    data = request.json
    if not data or not data.get('task_id') or not data.get('schedule_time'):
        return jsonify({'message': 'Invalid input'}), 400

    # Schedule the task
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
def reschedule_task(user_id):
    data = request.json
    if not data or not data.get('task_id') or not data.get('new_schedule_time'):
        return jsonify({'message': 'Invalid input'}), 400

    # Reschedule the task
    scheduler.reschedule_job(
        data['task_id'], 
        trigger='date', 
        run_date=data['new_schedule_time']
    )

    return jsonify({'message': 'Task rescheduled successfully'}), 200

@app.route('/cancel', methods=['POST'])
@token_required
def cancel_task(user_id):
    data = request.json
    if not data or not data.get('task_id'):
        return jsonify({'message': 'Invalid input'}), 400

    # Cancel the scheduled task
    scheduler.remove_job(data['task_id'])

    return jsonify({'message': 'Task cancelled successfully'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
