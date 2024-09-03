# Microservices/NotificationService.py

from flask import Flask, request, jsonify
import requests
import os
import pika
import json
from email.message import EmailMessage
import smtplib

app = Flask(__name__)

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def get_hasura_client():
    hasura_endpoint = os.getenv('HASURA_GRAPHQL_ENDPOINT')
    hasura_admin_secret = os.getenv('HASURA_ADMIN_SECRET')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': hasura_admin_secret
    }
    return hasura_endpoint, headers

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_FROM')
    msg['To'] = to_email

    # Send the message via SMTP server
    with smtplib.SMTP(os.getenv('SMTP_SERVER'), os.getenv('SMTP_PORT')) as s:
        s.starttls()
        s.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
        s.send_message(msg)

def process_notification(notification):
    hasura_endpoint, headers = get_hasura_client()
    
    query = """
    query ($user_id: uuid!) {
      users_by_pk(id: $user_id) {
        email
      }
    }
    """
    variables = {'user_id': notification['user_id']}
    response = requests.post(hasura_endpoint, json={'query': query, 'variables': variables}, headers=headers)
    user = response.json()['data']['users_by_pk']
    
    if user:
        send_email(user['email'], notification['subject'], notification['body'])
        print(f"Sent email notification to user: {notification['user_id']}")
    else:
        print(f"User not found: {notification['user_id']}")

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='notification_queue')

    def callback(ch, method, properties, body):
        notification = json.loads(body)
        process_notification(notification)

    channel.basic_consume(queue='notification_queue', on_message_callback=callback, auto_ack=True)
    print('Notification Service waiting for messages...')
    channel.start_consuming()

@app.route('/notify', methods=['POST'])
def create_notification():
    data = request.json
    if not data or not data.get('user_id') or not data.get('subject') or not data.get('body'):
        return jsonify({'message': 'Invalid input'}), 400

    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='notification_queue')
    channel.basic_publish(exchange='', routing_key='notification_queue', body=json.dumps(data))
    connection.close()

    return jsonify({'message': 'Notification queued successfully'}), 200

if __name__ == '__main__':
    # Run the RabbitMQ consumer in a separate thread
    import threading
    threading.Thread(target=main, daemon=True).start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5002)
