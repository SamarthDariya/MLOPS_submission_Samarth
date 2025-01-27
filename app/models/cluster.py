from .. import db
from datetime import datetime, timezone

class Cluster(db.Model):
    __tablename__ = 'clusters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Total resources
    total_ram_gb = db.Column(db.Float, nullable=False)
    total_cpu_cores = db.Column(db.Float, nullable=False)
    total_gpu_count = db.Column(db.Integer, default=0)
    
    # Available resources
    available_ram_gb = db.Column(db.Float)
    available_cpu_cores = db.Column(db.Float)
    available_gpu_count = db.Column(db.Integer)
    
    status = db.Column(db.String(20), default='active')  # active, maintenance, offline
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = db.relationship('Organization', back_populates='clusters')
    deployments = db.relationship('Deployment', back_populates='cluster')

    def __init__(self, **kwargs):
        super(Cluster, self).__init__(**kwargs)
        # Initialize available resources to total resources
        self.available_ram_gb = kwargs.get('total_ram_gb')
        self.available_cpu_cores = kwargs.get('total_cpu_cores')
        self.available_gpu_count = kwargs.get('total_gpu_count', 0)

    def can_accommodate(self, ram_gb, cpu_cores, gpu_count):
        """Check if the cluster can accommodate the requested resources"""
        return (self.available_ram_gb >= ram_gb and
                self.available_cpu_cores >= cpu_cores and
                self.available_gpu_count >= gpu_count)

    def allocate_resources(self, ram_gb, cpu_cores, gpu_count):
        """Allocate resources if available"""
        if not self.can_accommodate(ram_gb, cpu_cores, gpu_count):
            return False
        
        self.available_ram_gb -= ram_gb
        self.available_cpu_cores -= cpu_cores
        self.available_gpu_count -= gpu_count
        return True

    def release_resources(self, ram_gb, cpu_cores, gpu_count):
        """Release allocated resources back to the pool"""
        self.available_ram_gb = min(self.total_ram_gb, self.available_ram_gb + ram_gb)
        self.available_cpu_cores = min(self.total_cpu_cores, self.available_cpu_cores + cpu_cores)
        self.available_gpu_count = min(self.total_gpu_count, self.available_gpu_count + gpu_count)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'organization_id': self.organization_id,
            'status': self.status,
            'total_ram_gb': self.total_ram_gb,
            'total_cpu_cores': self.total_cpu_cores,
            'total_gpu_count': self.total_gpu_count,
            'available_ram_gb': self.available_ram_gb,
            'available_cpu_cores': self.available_cpu_cores,
            'available_gpu_count': self.available_gpu_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 