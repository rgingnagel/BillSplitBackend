import os
from flask import Flask, abort, request, jsonify, g, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer
                          as Serializer, BadSignature, SignatureExpired)
from flask_restful import reqparse, abort, Api, Resource
import sqlite3
import json

# initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
api = Api(app)

# extensions
db = SQLAlchemy(app)
auth = HTTPBasicAuth()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(64))
    transactions = db.relationship('TransactionModel', backref='user',
                                lazy='dynamic')
    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.id})
        

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token
        user = User.query.get(data['id'])
        return user

class TransactionModel(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(64), index=True)
    date = db.Column(db.String(64))
    owner = db.Column(db.Integer, db.ForeignKey('users.id'))
    participants = db.Column(db.String(32))
    price = db.Column(db.Integer)
    def __init__(self, description, date, participants, price):
        self.description = description
        self.date = date
        self.owner = g.user.id
        self.participants = participants
        self.price = price

    # def __repr__(self):
    #     return '<User %r>' % (self.description)
    #     #return jsonify({'description': repr(self.description), 'date': repr(self.date), 'owner': repr(self.owner), 'participants': repr(self.participants), 'price': repr(self.price)})


@auth.verify_password
def verify_password(username_or_token, password):
    # first try to authenticate by token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.query.filter_by(username=username_or_token).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True


@app.route('/api/users', methods=['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400)    # missing arguments
    if User.query.filter_by(username=username).first() is not None:
        abort(400)    # existing user
    user = User(username=username)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return (jsonify({'username': user.username}), 201,
            {'Location': url_for('get_user', id=user.id, _external=True)})


@app.route('/api/users/<int:id>')
def get_user(id):
    user = User.query.get(id)
    if not user:
        abort(400)
    return jsonify({'username': user.username})


# @app.route('/api/token')
# @auth.login_required
# def get_auth_token():
#     token = g.user.generate_auth_token(600)
#     return jsonify({'token': token.decode('ascii'), 'duration': 600})


# @app.route('/api/resource')
# @auth.login_required
# def get_resource():
#     return jsonify({'data': 'Hello, %s!' % g.user.username})



# def abort_if_transaction_doesnt_exist(transaction_id):
#     if transaction_id not in TRANSACTIONS:
#         abort(404, message="Transaction {} doesn't exist".format(transaction_id))

parser = reqparse.RequestParser()
parser.add_argument('Description', type=str)
parser.add_argument('Date', type=str)
parser.add_argument('Owner', type=int)
parser.add_argument('Participants', type=str)
parser.add_argument('Price', type=int)


# Transaction
# shows a single transaction and lets you delete a transaction
class Transaction(Resource):
    @auth.login_required
    def get(self, transaction_id):
        # abort_if_transaction_doesnt_exist(transaction_id)
        transaction = TransactionModel.query.get(transaction_id)
        return jsonify({'description': transaction.description, 'date': transaction.date, 'owner': transaction.owner, 'participants': transaction.participants, 'price': transaction.price})

    
    @auth.login_required
    def delete(self, transaction_id):
        # abort_if_transaction_doesnt_exist(transaction_id)
        transaction = TransactionModel.query.get(transaction_id)
        db.session.delete(transaction)
        db.session.commit()
        return '', 204
    
    @auth.login_required
    def put(self, transaction_id):
        args = parser.parse_args()
        transaction = TransactionModel.query.get(transaction_id)
        transaction.description = args['Description']
        transaction.date = args['Date']
        transaction.owner = args['Owner']
        transaction.participants = args['Participants']
        transaction.price = args['Price']
        db.session.commit()
        return '', 201


# TodoList
# shows a list of all transactions, and lets you POST to add a new transaction

class TransactionList(Resource):
    @auth.login_required
    def get(self):
        transactions = TransactionModel.query.all()
        transactionsObject = {}
        for transaction in transactions:
            transactionObject = {'description': transaction.description, 'date': transaction.date, 'owner': transaction.owner, 'participants': transaction.participants, 'price': transaction.price}
            transactionsObject[transaction.id] = transactionObject
        return transactionsObject

    @auth.login_required
    def post(self):
        args = parser.parse_args()
        username = args['Description']
        date = args['Date']
        participants = args['Participants']
        price = args['Price']
        
        
        transaction = TransactionModel(username, date, participants, price)
        db.session.add(transaction)
        db.session.commit()


##
## Actually setup the Api resource routing here
##

api.add_resource(TransactionList, '/transactions')
# api.add_resource(Transaction, '/transactions/<transaction_id>')
api.add_resource(Transaction, '/transactions/<transaction_id>')



if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    app.run(debug=True)