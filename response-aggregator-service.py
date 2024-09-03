# Microservices/ResponseAggregatorService.py

import pika
import os
import json
import requests

def connect_rabbitmq():
    credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER'), os.getenv('RABBITMQ_PASS'))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST'), credentials=credentials))
    return connection

def store_response(response_data):
    hasura_endpoint = os.getenv('HASURA_GRAPHQL_ENDPOINT')
    hasura_admin_secret = os.getenv('HASURA_ADMIN_SECRET')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': hasura_admin_secret
    }
    
    query = """
    mutation ($user_id: String!, $task_id: String!, $service: String!, $content: jsonb!) {
      insert_responses_one(object: {user_id: $user_id, task_id: $task_id, service: $service, content: $content}) {
        id
      }
    }
    """
    
    variables = {
        "user_id": response_data['user_id'],
        "task_id": response_data['task_id'],
        "service": response_data['service'],
        "content": json.dumps(response_data['content'])
    }
    
    response = requests.post(hasura_endpoint, json={'query': query, 'variables': variables}, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='response_queue')

    def callback(ch, method, properties, body):
        response_data = json.loads(body)
        print(f"Aggregating response from {response_data['service']}")
        try:
            result = store_response(response_data)
            print(f"Stored response with ID: {result['data']['insert_responses_one']['id']}")
        except Exception as e:
            print(f"Error storing response: {str(e)}")

    channel.basic_consume(queue='response_queue', on_message_callback=callback, auto_ack=True)
    print('Response Aggregator Service waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
