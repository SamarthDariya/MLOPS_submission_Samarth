import os
from datetime import timedelta

# Flask settings
SECRET_KEY = os.environ['SECRET_KEY']  # Required
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Database settings
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///mlops_platform.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# JWT settings
JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']  # Required
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# JWT Cookie settings
JWT_TOKEN_LOCATION = ['headers', 'cookies']  # Look for tokens in headers and cookies
JWT_COOKIE_SECURE = os.getenv('JWT_COOKIE_SECURE', 'False').lower() == 'true'  # Set to True in production
JWT_COOKIE_CSRF_PROTECT = True
JWT_COOKIE_SAMESITE = 'Lax'

# Redis settings
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Deployment settings
MAX_QUEUE_SIZE = int(os.getenv('MAX_QUEUE_SIZE', 100))
DEFAULT_DEPLOYMENT_PRIORITY = int(os.getenv('DEFAULT_DEPLOYMENT_PRIORITY', 1))
MAX_DEPLOYMENT_PRIORITY = int(os.getenv('MAX_DEPLOYMENT_PRIORITY', 5))

# Resource limits
MAX_RAM_GB_PER_DEPLOYMENT = float(os.getenv('MAX_RAM_GB_PER_DEPLOYMENT', 32))
MAX_CPU_CORES_PER_DEPLOYMENT = float(os.getenv('MAX_CPU_CORES_PER_DEPLOYMENT', 8))
MAX_GPU_COUNT_PER_DEPLOYMENT = int(os.getenv('MAX_GPU_COUNT_PER_DEPLOYMENT', 4))

# Security settings
PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
INVITE_CODE_EXPIRY_HOURS = int(os.getenv('INVITE_CODE_EXPIRY_HOURS', 24))

# Scheduling settings
SCHEDULER_INTERVAL_SECONDS = int(os.getenv('SCHEDULER_INTERVAL_SECONDS', 10))
MAX_CONCURRENT_DEPLOYMENTS_PER_CLUSTER = int(os.getenv('MAX_CONCURRENT_DEPLOYMENTS_PER_CLUSTER', 10)) 