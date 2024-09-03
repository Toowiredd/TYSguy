# Microservices/UserAuthenticationService.py

from flask import Flask, request, jsonify
import jwt
import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import requests

app = Flask(__name__)

def get_hasura_client():
    hasura_endpoint = os.getenv('HASURA_GRAPHQL_ENDPOINT')
    hasura_admin_secret = os.getenv('HASURA_ADMIN_SECRET')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': hasura_admin_secret
    }
    return hasura_endpoint, headers

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Invalid input'}), 400

    hasura_endpoint, headers = get_hasura_client()
    
    # Check if user already exists
    query = """
    query ($email: String!) {
      users(where: {email: {_eq: $email}}) {
        id
      }
    }
    """
    variables = {'email': data['email']}
    response = requests.post(hasura_endpoint, json={'query': query, 'variables': variables}, headers=headers)
    
    if response.json()['data']['users']:
        return jsonify({'message': 'User already exists'}), 400

    # Create new user
    hashed_password = generate_password_hash(data['password'], method='sha256')
    user_id = str(uuid.uuid4())
    
    mutation = """
    mutation ($id: uuid!, $email: String!, $password: String!) {
      insert_users_one(object: {id: $id, email: $email, password: $password}) {
        id
      }
    }
    """
    variables = {'id': user_id, 'email': data['email'], 'password': hashed_password}
    response = requests.post(hasura_endpoint, json={'query': mutation, 'variables': variables}, headers=headers)
    
    if response.status_code == 200 and not response.json().get('errors'):
        return jsonify({'message': 'User created successfully'}), 201
    else:
        return jsonify({'message': 'Error creating user'}), 500

@app.route('/login', methods=['POST'])
def login():
    auth = request.json
    if not auth or not auth.get('email') or not auth.get('password'):
        return jsonify({'message': 'Could not verify'}), 401

    hasura_endpoint, headers = get_hasura_client()
    
    query = """
    query ($email: String!) {
      users(where: {email: {_eq: $email}}) {
        id
        password
      }
    }
    """
    variables = {'email': auth['email']}
    response = requests.post(hasura_endpoint, json={'query': query, 'variables': variables}, headers=headers)
    
    user = response.json()['data']['users']
    if not user:
        return jsonify({'message': 'User not found'}), 401
    
    if check_password_hash(user[0]['password'], auth['password']):
        token = jwt.encode({
            'user_id': user[0]['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, os.getenv('JWT_SECRET'))
        
        return jsonify({'token': token})
    
    return jsonify({'message': 'Invalid credentials'}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
