# Dariya - Deployment Management System

A Flask-based API service for managing deployments, organizations, and clusters with priority-based scheduling.

## Prerequisites

- Python 3.8 or higher
- Redis server
- SQLite (for development)

## Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # or
   .\venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and Start Redis Server**
   ```bash
   # On Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install redis-server
   sudo systemctl start redis-server

   # On MacOS with Homebrew
   brew install redis
   brew services start redis

   # Verify Redis is running
   redis-cli ping  # Should return "PONG"
   ```

5. **Environment Setup**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env file with your configurations if needed
   # Default values should work for local development
   ```

6. **Initialize Database**
   ```bash
   # Create database and apply migrations
   flask db upgrade
   
   # Initialize database with required tables
   python manage.py init-db
   ```

## Running the Application

1. **Start the Flask Application**
   ```bash
   python3 app.py
   ```
   The server will start at `http://localhost:5000`

2. **Create Admin User** (First Time Setup)
   ```bash
   # In another terminal
   source venv/bin/activate
   flask create-admin --username admin --email admin@example.com --password your_password
   ```

## API Documentation

### Authentication Endpoints
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user info

### Organization Endpoints
- `POST /api/organizations` - Create organization
- `GET /api/organizations` - List organizations
- `GET /api/organizations/{id}` - Get organization details
- `PUT /api/organizations/{id}` - Update organization
- `DELETE /api/organizations/{id}` - Delete organization
- `POST /api/organizations/{id}/invite` - Generate invite code
- `POST /api/organizations/join` - Join using invite code

### Cluster Endpoints
- `POST /api/clusters` - Create cluster
- `GET /api/clusters` - List clusters
- `GET /api/clusters/{id}` - Get cluster details
- `PUT /api/clusters/{id}` - Update cluster
- `GET /api/clusters/{id}/status` - Get cluster status

### Deployment Endpoints
- `POST /api/deployments` - Create deployment
- `GET /api/deployments` - List deployments
- `GET /api/deployments/{id}` - Get deployment details
- `PUT /api/deployments/{id}` - Update deployment
- `DELETE /api/deployments/{id}` - Delete deployment
- `GET /api/deployments/queue` - View deployment queue
- `PUT /api/deployments/{id}/priority` - Update deployment priority

## Development Notes

- The application uses SQLite for development. For production, configure a proper database in `.env`
- Redis is used for managing deployment scheduling and queue
- Default admin credentials should be changed in production
- All timestamps are in UTC

## Troubleshooting

1. **Redis Connection Issues**
   - Verify Redis is running: `redis-cli ping`
   - Check Redis connection settings in `.env`

2. **Database Issues**
   - Delete the `instance` folder and reinitialize the database
   - Run migrations again: `flask db upgrade`

3. **Deployment Scheduling Issues**
   - Check Redis logs
   - Verify cluster has sufficient resources
   - Check deployment priority settings

4. **Postman requests**
   - use the bearer token in the Authorization header
   - use the correct content type in the header
   - use the correct body format for JSON requests
   - if the token expires, you can refresh it by calling the /api/auth/refresh endpoint
   - if you get a 401 Unauthorized error, check the token and ensure it's correct