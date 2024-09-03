# Microservices/FocusTechniquesService.py

import pika
import os
import google.generativeai as genai
import json

genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='focus_techniques_queue')
    channel.queue_declare(queue='response_queue')

    def callback(ch, method, properties, body):
        task = json.loads(body)
        print(f"Providing focus techniques for task: {task['content']}")
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(f"Suggest focus techniques for someone with ADHD to complete this task: {task['content']}")
        focus_technique = response.text.strip()
        response_data = {
            'user_id': task['user_id'],
            'task_id': task['task_id'],
            'service': 'focus_techniques',
            'content': focus_technique
        }
        channel.basic_publish(exchange='', routing_key='response_queue', body=json.dumps(response_data))

    channel.basic_consume(queue='focus_techniques_queue', on_message_callback=callback, auto_ack=True)
    print('Focus Techniques Service waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
