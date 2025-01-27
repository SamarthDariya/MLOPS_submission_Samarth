from flask import Flask
from config import config
from app import create_app

app = create_app('default')

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False) 