from . import create_app, db
from .models import User, Organization, Cluster, Deployment

def init_db():
    """Initialize the database and create all tables"""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if we need to create an admin user
        if User.query.filter_by(role='admin').first() is None:
            print("Creating default admin user and organization...")
            
            # Create default organization
            org = Organization(name='Default Organization')
            db.session.add(org)
            db.session.flush()  # Get the org ID
            
            # Create admin user
            admin = User(
                username='admin',
                email='admin@example.com',
                role='admin',
                organization_id=org.id
            )
            admin.set_password('admin')  # Remember to change this in production!
            db.session.add(admin)
            
            try:
                db.session.commit()
                print("Created default admin user and organization successfully")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating default data: {str(e)}")
                raise
        else:
            print("Admin user already exists, skipping default data creation")
        
        print("Database initialized successfully") 