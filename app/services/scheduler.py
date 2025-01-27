import threading
import time
from datetime import datetime, timezone
from sqlalchemy import desc
from ..models import Deployment, Cluster, DeploymentQueue, db
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class DeploymentScheduler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.app = None
            logger.info("Deployment scheduler initialized")
    
    def init_app(self, app):
        """Initialize the scheduler with the Flask app"""
        self.app = app
        logger.info("Scheduler initialized with app")
    
    def start(self):
        """Start the scheduler"""
        logger.info("Deployment scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Deployment scheduler stopped")
    
    def notify_new_deployment(self, deployment_id):
        """Handle new deployment notification"""
        logger.info(f"New deployment notification received: {deployment_id}")
        try:
            self.schedule_deployment(deployment_id)
        except Exception as e:
            logger.error(f"Error processing new deployment {deployment_id}: {str(e)}")
    
    def notify_priority_change(self, deployment_id):
        """Handle priority change notification"""
        logger.info(f"Priority change notification received: {deployment_id}")
        try:
            self.schedule_deployment(deployment_id)
        except Exception as e:
            logger.error(f"Error processing priority change for deployment {deployment_id}: {str(e)}")
    
    def schedule_deployment(self, deployment_id):
        """Attempt to schedule a specific deployment"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            logger.warning(f"Deployment not found: {deployment_id}")
            return False
        
        # Check if cluster is active
        cluster = deployment.cluster
        if cluster.status != 'active':
            logger.warning(f"Cluster {cluster.id} is not active")
            return False
        
        # Check resource availability
        if (cluster.available_ram_gb >= deployment.ram_gb and
            cluster.available_cpu_cores >= deployment.cpu_cores and
            cluster.available_gpu_count >= deployment.gpu_count):
            
            try:
                # Allocate resources
                cluster.available_ram_gb -= deployment.ram_gb
                cluster.available_cpu_cores -= deployment.cpu_cores
                cluster.available_gpu_count -= deployment.gpu_count
                
                # Update deployment status
                deployment.status = 'running'
                deployment.started_at = datetime.now(timezone.utc)
                deployment.updated_at = datetime.now(timezone.utc)
                
                # Remove from queue
                queue_entry = DeploymentQueue.query.filter_by(deployment_id=deployment_id).first()
                if queue_entry:
                    db.session.delete(queue_entry)
                
                db.session.commit()
                logger.info(f"Successfully scheduled deployment {deployment_id}")
                return True
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error scheduling deployment {deployment_id}: {str(e)}")
                return False
                
        logger.debug(f"Insufficient resources for deployment {deployment_id}")
        return False

    def schedule_pending_deployments(self):
        """Schedule all pending deployments based on priority and resources"""
        with self.scheduling_lock:
            try:
                # Get queued deployments ordered by priority and time
                queue = DeploymentQueue.query.order_by(
                    DeploymentQueue.priority.desc(),
                    DeploymentQueue.queued_at.asc()
                ).all()
                
                # Get active clusters
                active_clusters = set(entry.deployment.cluster_id 
                                   for entry in queue 
                                   if entry.deployment.cluster.status == 'active')
                
                # Track scheduled count per cluster
                scheduled_count = {cluster_id: 0 for cluster_id in active_clusters}
                
                for entry in queue:
                    cluster_id = entry.deployment.cluster_id
                    max_concurrent = self.app.config.get('MAX_CONCURRENT_DEPLOYMENTS_PER_CLUSTER', 10)
                    
                    # Skip if cluster reached max concurrent deployments
                    if scheduled_count.get(cluster_id, 0) >= max_concurrent:
                        continue
                    
                    if self.schedule_deployment(entry.deployment_id):
                        scheduled_count[cluster_id] = scheduled_count.get(cluster_id, 0) + 1
                
                logger.debug(f"Scheduled deployments per cluster: {scheduled_count}")
                
            except Exception as e:
                logger.error(f"Error in schedule_pending_deployments: {str(e)}")
                db.session.rollback()

    def preempt_lower_priority(self, high_priority_deployment):
        """Attempt to preempt lower priority deployments to make room for a higher priority one"""
        cluster = Cluster.query.get(high_priority_deployment.cluster_id)
        if not cluster:
            return False

        # Get all running deployments with lower priority
        running_deployments = (Deployment.query
            .filter_by(cluster_id=cluster.id, status='running')
            .filter(Deployment.priority < high_priority_deployment.priority)
            .order_by(Deployment.priority)  # Start with lowest priority
            .all())

        required_ram = high_priority_deployment.required_ram_gb
        required_cpu = high_priority_deployment.required_cpu_cores
        required_gpu = high_priority_deployment.required_gpu_count

        preempted = []
        freed_ram = freed_cpu = freed_gpu = 0

        # Try to free up enough resources by preempting lower priority deployments
        for dep in running_deployments:
            if (freed_ram >= required_ram and 
                freed_cpu >= required_cpu and 
                freed_gpu >= required_gpu):
                break

            # Preempt this deployment
            dep.cancel()
            preempted.append(dep)
            
            freed_ram += dep.required_ram_gb
            freed_cpu += dep.required_cpu_cores
            freed_gpu += dep.required_gpu_count

        # If we freed enough resources, try to schedule the high priority deployment
        if (freed_ram >= required_ram and 
            freed_cpu >= required_cpu and 
            freed_gpu >= required_gpu):
            if self._try_schedule_deployment(high_priority_deployment):
                db.session.commit()
                return True

        # If scheduling failed, restore the preempted deployments
        for dep in preempted:
            dep.status = 'running'
            cluster.allocate_resources(
                dep.required_ram_gb,
                dep.required_cpu_cores,
                dep.required_gpu_count
            )

        db.session.commit()
        return False

    def update_queue_positions(self):
        """Update queue positions for all pending deployments"""
        pending_deployments = (Deployment.query
            .filter_by(status='pending')
            .order_by(desc(Deployment.priority), Deployment.created_at)
            .all())

        for position, deployment in enumerate(pending_deployments, 1):
            deployment.queue_position = position

        db.session.commit() 