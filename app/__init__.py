from flask import Flask, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
import redis
from datetime import timedelta
import os
from dotenv import load_dotenv
from config import config
import logging
from flask_cors import CORS
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
bcrypt = Bcrypt()

def create_app(config_name='default'):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    if config_name == 'testing':
        app.config.from_object('config.TestingConfig')
    else:
        app.config.from_object('config.Config')
    
    # Initialize logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app)

    # Initialize Redis
    app.redis = redis.Redis(
        host=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT'],
        db=app.config['REDIS_DB']
    )

    with app.app_context():
        # Create database tables
        db.create_all()
    
    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.organizations import org_bp
    from .routes.clusters import cluster_bp
    from .routes.deployments import deployment_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(org_bp, url_prefix='/api/organizations')
    app.register_blueprint(cluster_bp, url_prefix='/api/clusters')
    app.register_blueprint(deployment_bp, url_prefix='/api/deployments')

    # Initialize deployment scheduler
    from .services.scheduler import DeploymentScheduler
    scheduler = DeploymentScheduler()
    scheduler.init_app(app)
    app.scheduler = scheduler
    
    # Start scheduler
    scheduler.start()
    
    @app.teardown_appcontext
    def cleanup(exception=None):
        if hasattr(app, 'scheduler'):
            app.scheduler.stop()
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token has expired',
            'redirect_to': url_for('auth.login')
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': 'Invalid token',
            'redirect_to': url_for('auth.login')
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': 'Authorization token is missing',
            'redirect_to': url_for('auth.login')
        }), 401

    @jwt.user_lookup_error_loader
    def user_lookup_error_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'User not found',
            'redirect_to': url_for('auth.login')
        }), 401

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

    return app
