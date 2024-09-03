# Microservices/TaskBreakdownService.py

import pika
import os
import openai
import json

openai.api_key = os.getenv('OPENAI_API_KEY')

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='task_breakdown_queue')
    channel.queue_declare(queue='response_queue')

    def callback(ch, method, properties, body):
        task = json.loads(body)
        print(f"Breaking down task: {task['content']}")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that breaks down tasks for people with ADHD."},
                {"role": "user", "content": f"Break down this task into manageable steps: {task['content']}"}
            ]
        )
        subtasks = response.choices[0].message['content'].strip().split('\n')
        response_data = {
            'user_id': task['user_id'],
            'task_id': task['task_id'],
            'service': 'task_breakdown',
            'content': subtasks
        }
        channel.basic_publish(exchange='', routing_key='response_queue', body=json.dumps(response_data))

    channel.basic_consume(queue='task_breakdown_queue', on_message_callback=callback, auto_ack=True)
    print('Task Breakdown Service waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
