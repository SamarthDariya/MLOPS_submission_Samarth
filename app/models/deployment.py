from datetime import datetime, timezone
from .. import db

class Deployment(db.Model):
    __tablename__ = 'deployments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(63), nullable=False)
    image = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cluster_id = db.Column(db.Integer, db.ForeignKey('clusters.id'), nullable=False)
    ram_gb = db.Column(db.Float, nullable=False)
    cpu_cores = db.Column(db.Float, nullable=False)
    gpu_count = db.Column(db.Integer, default=0)
    environment = db.Column(db.JSON, default={})
    status = db.Column(db.String(20), default='pending')  # pending, running, stopped, failed
    priority = db.Column(db.Integer, default=1)  # 1-5, higher is more priority
    started_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', back_populates='deployments')
    cluster = db.relationship('Cluster', back_populates='deployments')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'user_id': self.user_id,
            'cluster_id': self.cluster_id,
            'ram_gb': self.ram_gb,
            'cpu_cores': self.cpu_cores,
            'gpu_count': self.gpu_count,
            'environment': self.environment,
            'status': self.status,
            'priority': self.priority,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class DeploymentQueue(db.Model):
    __tablename__ = 'deployment_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey('deployments.id'), unique=True)
    priority = db.Column(db.Integer, nullable=False, default=1)  # 1-5, higher is more priority
    queued_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    deployment = db.relationship('Deployment', backref=db.backref('queue_entry', uselist=False))

    def start(self):
        """Mark deployment as started and record timestamp"""
        self.status = 'running'
        self.started_at = datetime.utcnow()

    def complete(self, success=True):
        """Mark deployment as completed/failed and release resources"""
        self.status = 'completed' if success else 'failed'
        self.completed_at = datetime.utcnow()
        if hasattr(self, 'cluster') and self.cluster:
            self.cluster.release_resources(
                self.ram_gb,
                self.cpu_cores,
                self.gpu_count
            )

    def cancel(self):
        """Cancel a pending or running deployment"""
        if self.status in ['pending', 'running']:
            self.status = 'cancelled'
            self.completed_at = datetime.utcnow()
            if self.status == 'running' and hasattr(self, 'cluster') and self.cluster:
                self.cluster.release_resources(
                    self.ram_gb,
                    self.cpu_cores,
                    self.gpu_count
                )

    def can_start(self):
        """Check if deployment can start based on dependencies"""
        if not self.depends_on:
            return True
        
        for dep_id in self.depends_on:
            dep = Deployment.query.get(dep_id)
            if not dep or dep.status != 'completed':
                return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'deployment_id': self.deployment_id,
            'priority': self.priority,
            'queued_at': self.queued_at.isoformat()
        } 