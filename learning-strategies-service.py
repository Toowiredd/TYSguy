# Microservices/LearningStrategiesService.py

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
    channel.queue_declare(queue='learning_strategies_queue')
    channel.queue_declare(queue='response_queue')

    def callback(ch, method, properties, body):
        task = json.loads(body)
        print(f"Providing learning strategies for task: {task['content']}")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides learning strategies for people with ADHD."},
                {"role": "user", "content": f"Suggest learning strategies for someone with ADHD to learn about: {task['content']}"}
            ]
        )
        learning_strategies = response.choices[0].message['content'].strip()
        response_data = {
            'user_id': task['user_id'],
            'task_id': task['task_id'],
            'service': 'learning_strategies',
            'content': learning_strategies
        }
        channel.basic_publish(exchange='', routing_key='response_queue', body=json.dumps(response_data))

    channel.basic_consume(queue='learning_strategies_queue', on_message_callback=callback, auto_ack=True)
    print('Learning Strategies Service waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
