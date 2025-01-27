#!/usr/bin/env python3
import click
from app import create_app
from app.db_init import init_db
from flask.cli import FlaskGroup

def create_cli_app():
    return create_app()

cli = FlaskGroup(create_app=create_cli_app)

@cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    init_db()

@cli.command('create-admin')
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def create_admin(username, email, password):
    """Create a new admin user."""
    app = create_app()
    with app.app_context():
        from app.models import User, Organization, db
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            click.echo('Error: Username already exists')
            return
            
        if User.query.filter_by(email=email).first():
            click.echo('Error: Email already exists')
            return
            
        # Get or create default organization
        org = Organization.query.first()
        if not org:
            org = Organization(name='Default Organization')
            db.session.add(org)
            db.session.flush()
        
        # Create admin user
        admin = User(
            username=username,
            email=email,
            role='admin',
            organization_id=org.id
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        click.echo(f'Created admin user: {username}')

if __name__ == '__main__':
    cli() 