# Microservices/EmotionalRegulationService.py

import pika
import os
import anthropic
import json

client = anthropic.Client(api_key=os.getenv('ANTHROPIC_API_KEY'))

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='emotional_regulation_queue')
    channel.queue_declare(queue='response_queue')

    def callback(ch, method, properties, body):
        task = json.loads(body)
        print(f"Providing emotional regulation strategies for: {task['content']}")
        response = client.completion(
            prompt=f"Human: Suggest emotional regulation strategies for someone with ADHD dealing with: {task['content']}\n\nAssistant:",
            max_tokens_to_sample=300,
            model="claude-v1"
        )
        emotional_strategies = response.completion.strip()
        response_data = {
            'user_id': task['user_id'],
            'task_id': task['task_id'],
            'service': 'emotional_regulation',
            'content': emotional_strategies
        }
        channel.basic_publish(exchange='', routing_key='response_queue', body=json.dumps(response_data))

    channel.basic_consume(queue='emotional_regulation_queue', on_message_callback=callback, auto_ack=True)
    print('Emotional Regulation Service waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
