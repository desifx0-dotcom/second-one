"""
Command-line interface commands for administration and maintenance
"""
import os
import sys
import click
import json
from datetime import datetime, timedelta
from pathlib import Path
from flask.cli import with_appcontext
from sqlalchemy import func, text

from src.app.models import db, User, VideoJob, ProcessingLog, APIKey, BillingRecord
from src.app.utils import (
    ensure_directories, cleanup_old_files, get_directory_size,
    create_default_admin, backup_database
)

def register_commands(app):
    """Register CLI commands with Flask application"""
    
    # ========== DATABASE COMMANDS ==========
    
    @app.cli.command('init-db')
    @with_appcontext
    def init_db_command():
        """Initialize the database"""
        click.echo("Creating database tables...")
        db.create_all()
        click.echo("✓ Database tables created")
        
        # Setup PostgreSQL functions if using PostgreSQL
        if 'postgresql' in db.engine.url.drivername:
            try:
                from src.app.models import setup_postgres_functions
                setup_postgres_functions(db)
                click.echo("✓ PostgreSQL functions created")
            except Exception as e:
                click.echo(f"⚠️  PostgreSQL functions setup failed: {e}")
        
        # Create default admin
        create_default_admin()
        click.echo("✓ Default admin user created")
        
        # Create necessary directories
        ensure_directories()
        click.echo("✓ Application directories created")
    
    @app.cli.command('drop-db')
    @with_appcontext
    @click.confirmation_option(prompt='Are you sure you want to drop all database tables?')
    def drop_db_command():
        """Drop all database tables"""
        db.drop_all()
        click.echo("✓ Database tables dropped")
    
    @app.cli.command('reset-db')
    @with_appcontext
    @click.confirmation_option(prompt='Are you sure you want to reset the database? This will delete all data!')
    def reset_db_command():
        """Reset database (drop and recreate)"""
        db.drop_all()
        click.echo("✓ Database tables dropped")
        
        db.create_all()
        click.echo("✓ Database tables recreated")
        
        create_default_admin()
        click.echo("✓ Default admin user created")
    
    @app.cli.command('migrate-db')
    @with_appcontext
    def migrate_db_command():
        """Run database migrations"""
        try:
            from flask_migrate import upgrade
            upgrade()
            click.echo("✓ Database migrations applied")
        except Exception as e:
            click.echo(f"❌ Migration failed: {e}")
    
    @app.cli.command('backup-db')
    @with_appcontext
    @click.option('--output-dir', type=click.Path(), help='Output directory for backup')
    def backup_db_command(output_dir):
        """Create database backup"""
        backup_file = backup_database(Path(output_dir) if output_dir else None)
        if backup_file:
            click.echo(f"✓ Database backup created: {backup_file}")
        else:
            click.echo("❌ Database backup failed")
    
    # ========== USER MANAGEMENT COMMANDS ==========
    
    @app.cli.command('create-user')
    @with_appcontext
    @click.option('--email', required=True, help='User email')
    @click.option('--password', required=True, help='User password')
    @click.option('--username', help='Username (optional)')
    @click.option('--full-name', help='Full name (optional)')
    @click.option('--tier', type=click.Choice(['free', 'plus', 'pro', 'enterprise']), default='free', help='Subscription tier')
    @click.option('--admin', is_flag=True, help='Make user an admin')
    def create_user_command(email, password, username, full_name, tier, admin):
        """Create a new user"""
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            click.echo(f"❌ User with email {email} already exists")
            return
        
        # Create user
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            subscription_tier=tier,
            is_admin=admin,
            email_verified=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f"✓ User created: {email}")
        if admin:
            click.echo("  Admin privileges: Yes")
    
    @app.cli.command('list-users')
    @with_appcontext
    @click.option('--limit', default=50, help='Maximum number of users to show')
    @click.option('--active-only', is_flag=True, help='Show only active users')
    def list_users_command(limit, active_only):
        """List all users"""
        query = User.query
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        users = query.order_by(User.created_at.desc()).limit(limit).all()
        
        if not users:
            click.echo("No users found")
            return
        
        click.echo(f"{'ID':<36} {'Email':<30} {'Tier':<10} {'Status':<10} {'Created':<20}")
        click.echo("-" * 120)
        
        for user in users:
            status = 'Active' if user.is_active else 'Inactive'
            click.echo(f"{user.id:<36} {user.email[:28]:<30} {user.subscription_tier.value[:9]:<10} {status:<10} {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @app.cli.command('update-user')
    @with_appcontext
    @click.option('--email', required=True, help='User email')
    @click.option('--tier', type=click.Choice(['free', 'plus', 'pro', 'enterprise']), help='Update subscription tier')
    @click.option('--admin/--no-admin', default=None, help='Set admin status')
    @click.option('--active/--inactive', default=None, help='Set active status')
    @click.option('--reset-password', help='Reset user password')
    def update_user_command(email, tier, admin, active, reset_password):
        """Update user information"""
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"❌ User with email {email} not found")
            return
        
        if tier:
            user.subscription_tier = tier
            click.echo(f"  Tier updated to: {tier}")
        
        if admin is not None:
            user.is_admin = admin
            click.echo(f"  Admin status: {'Yes' if admin else 'No'}")
        
        if active is not None:
            user.is_active = active
            click.echo(f"  Active status: {'Active' if active else 'Inactive'}")
        
        if reset_password:
            user.set_password(reset_password)
            click.echo("  Password reset")
        
        if any([tier, admin is not None, active is not None, reset_password]):
            db.session.commit()
            click.echo(f"✓ User {email} updated")
        else:
            click.echo("No changes specified")
    
    @app.cli.command('delete-user')
    @with_appcontext
    @click.option('--email', required=True, help='User email')
    @click.confirmation_option(prompt='Are you sure you want to delete this user?')
    def delete_user_command(email):
        """Delete a user and all their data"""
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"❌ User with email {email} not found")
            return
        
        # Soft delete (mark as deleted)
        user.is_active = False
        user.deleted_at = datetime.utcnow()
        
        # Also delete user's API keys
        for api_key in user.api_keys:
            api_key.revoke("User deleted")
        
        db.session.commit()
        click.echo(f"✓ User {email} deleted (soft delete)")
    
    # ========== VIDEO JOBS COMMANDS ==========
    
    @app.cli.command('list-jobs')
    @with_appcontext
    @click.option('--limit', default=50, help='Maximum number of jobs to show')
    @click.option('--status', help='Filter by status')
    @click.option('--user-email', help='Filter by user email')
    @click.option('--days', type=int, help='Show jobs from last N days')
    def list_jobs_command(limit, status, user_email, days):
        """List video processing jobs"""
        from src.app.models import ProcessingStatus
        
        query = VideoJob.query
        
        if status:
            query = query.filter_by(status=ProcessingStatus(status))
        
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                query = query.filter_by(user_id=user.id)
            else:
                click.echo(f"❌ User with email {user_email} not found")
                return
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(VideoJob.created_at >= cutoff)
        
        jobs = query.order_by(VideoJob.created_at.desc()).limit(limit).all()
        
        if not jobs:
            click.echo("No jobs found")
            return
        
        click.echo(f"{'ID':<36} {'Filename':<30} {'Status':<20} {'User':<25} {'Created':<20}")
        click.echo("-" * 130)
        
        for job in jobs:
            user_email_short = job.user.email[:23] + '...' if len(job.user.email) > 25 else job.user.email
            filename_short = job.original_filename[:27] + '...' if len(job.original_filename) > 30 else job.original_filename
            
            click.echo(f"{job.id:<36} {filename_short:<30} {job.status.value[:19]:<20} {user_email_short:<25} {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @app.cli.command('retry-job')
    @with_appcontext
    @click.option('--job-id', required=True, help='Job ID to retry')
    def retry_job_command(job_id):
        """Retry a failed job"""
        from src.app.models import ProcessingStatus
        
        job = VideoJob.query.get(job_id)
        if not job:
            click.echo(f"❌ Job with ID {job_id} not found")
            return
        
        if job.status != ProcessingStatus.FAILED:
            click.echo(f"❌ Job is not in failed status (current: {job.status})")
            return
        
        # Reset job for retry
        job.status = ProcessingStatus.PENDING
        job.progress = 0
        job.current_step = None
        job.error_message = None
        job.error_details = None
        job.retry_count += 1
        
        db.session.commit()
        click.echo(f"✓ Job {job_id} reset for retry")
        
        # Log the retry
        job.log_event('info', 'Job reset for retry via CLI')
    
    @app.cli.command('cancel-job')
    @with_appcontext
    @click.option('--job-id', required=True, help='Job ID to cancel')
    def cancel_job_command(job_id):
        """Cancel a processing job"""
        from src.app.models import ProcessingStatus
        
        job = VideoJob.query.get(job_id)
        if not job:
            click.echo(f"❌ Job with ID {job_id} not found")
            return
        
        if job.status not in [ProcessingStatus.PROCESSING, ProcessingStatus.QUEUED, ProcessingStatus.TRANSCRIBING]:
            click.echo(f"❌ Job cannot be cancelled (current: {job.status})")
            return
        
        job.status = ProcessingStatus.CANCELLED
        job.updated_at = datetime.utcnow()
        
        db.session.commit()
        click.echo(f"✓ Job {job_id} cancelled")
        
        # Log the cancellation
        job.log_event('info', 'Job cancelled via CLI')
    
    @app.cli.command('cleanup-jobs')
    @with_appcontext
    @click.option('--days', default=30, help='Delete jobs older than N days')
    @click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
    @click.confirmation_option(prompt='Are you sure you want to cleanup old jobs?')
    def cleanup_jobs_command(days, dry_run):
        """Cleanup old completed/failed jobs"""
        from src.app.models import ProcessingStatus
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Find jobs to delete
        jobs_to_delete = VideoJob.query.filter(
            VideoJob.created_at < cutoff,
            VideoJob.status.in_([ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED])
        ).all()
        
        if not jobs_to_delete:
            click.echo("No jobs to cleanup")
            return
        
        if dry_run:
            click.echo(f"Would delete {len(jobs_to_delete)} jobs older than {days} days:")
            for job in jobs_to_delete[:10]:  # Show first 10
                click.echo(f"  {job.id} - {job.original_filename} - {job.status} - {job.created_at}")
            if len(jobs_to_delete) > 10:
                click.echo(f"  ... and {len(jobs_to_delete) - 10} more")
        else:
            deleted_count = 0
            for job in jobs_to_delete:
                # Soft delete
                job.deleted_at = datetime.utcnow()
                deleted_count += 1
            
            db.session.commit()
            click.echo(f"✓ Cleaned up {deleted_count} jobs older than {days} days (soft delete)")
    
    # ========== SYSTEM MAINTENANCE COMMANDS ==========
    
    @app.cli.command('cleanup-files')
    @with_appcontext
    @click.option('--days', default=7, help='Delete temporary files older than N days')
    @click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
    def cleanup_files_command(days, dry_run):
        """Cleanup temporary files"""
        from src.app.config import BaseConfig
        
        directories = [
            BaseConfig.TEMP_FOLDER,
            BaseConfig.PROCESSING_FOLDER,
        ]
        
        total_deleted = 0
        total_freed = 0
        
        for directory in directories:
            if dry_run:
                deleted_count = 0
                freed_size = 0
                
                for file_path in directory.rglob('*'):
                    if file_path.is_file():
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < datetime.now() - timedelta(days=days):
                            deleted_count += 1
                            freed_size += file_path.stat().st_size
                
                if deleted_count > 0:
                    click.echo(f"Would delete {deleted_count} files from {directory.name} ({(freed_size / (1024*1024)):.1f} MB)")
                    total_deleted += deleted_count
                    total_freed += freed_size
            else:
                deleted_count = cleanup_old_files(directory, days)
                if deleted_count > 0:
                    freed_size = 0  # We don't calculate this in the actual cleanup
                    click.echo(f"✓ Deleted {deleted_count} files from {directory.name}")
                    total_deleted += deleted_count
        
        if dry_run:
            if total_deleted > 0:
                click.echo(f"\nTotal: Would delete {total_deleted} files ({(total_freed / (1024*1024*1024)):.2f} GB)")
            else:
                click.echo("No files to cleanup")
        else:
            if total_deleted > 0:
                click.echo(f"\n✓ Cleanup complete: {total_deleted} files deleted")
            else:
                click.echo("No files to cleanup")
    
    @app.cli.command('system-stats')
    @with_appcontext
    def system_stats_command():
        """Show system statistics"""
        from src.app.config import BaseConfig
        from src.app.utils import format_file_size
        
        # Database statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_users = User.query.filter_by(is_admin=True).count()
        
        total_jobs = VideoJob.query.count()
        completed_jobs = VideoJob.query.filter_by(status='completed').count()
        failed_jobs = VideoJob.query.filter_by(status='failed').count()
        processing_jobs = VideoJob.query.filter(VideoJob.status.in_(['processing', 'queued', 'transcribing'])).count()
        
        total_api_keys = APIKey.query.count()
        active_api_keys = APIKey.query.filter_by(is_active=True).count()
        
        # Storage statistics
        total_storage = get_directory_size(BaseConfig.UPLOAD_FOLDER)
        temp_storage = get_directory_size(BaseConfig.TEMP_FOLDER)
        processing_storage = get_directory_size(BaseConfig.PROCESSING_FOLDER)
        outputs_storage = get_directory_size(BaseConfig.OUTPUTS_FOLDER)
        
        # Recent activity
        jobs_today = VideoJob.query.filter(
            func.date(VideoJob.created_at) == datetime.utcnow().date()
        ).count()
        
        new_users_today = User.query.filter(
            func.date(User.created_at) == datetime.utcnow().date()
        ).count()
        
        click.echo("=" * 60)
        click.echo("SYSTEM STATISTICS")
        click.echo("=" * 60)
        
        click.echo("\n👥 USER STATISTICS:")
        click.echo(f"  Total Users: {total_users}")
        click.echo(f"  Active Users: {active_users}")
        click.echo(f"  Admin Users: {admin_users}")
        click.echo(f"  New Users Today: {new_users_today}")
        
        click.echo("\n🎥 VIDEO JOB STATISTICS:")
        click.echo(f"  Total Jobs: {total_jobs}")
        click.echo(f"  Completed: {completed_jobs}")
        click.echo(f"  Failed: {failed_jobs}")
        click.echo(f"  Processing: {processing_jobs}")
        click.echo(f"  Jobs Today: {jobs_today}")
        
        click.echo("\n🔑 API KEY STATISTICS:")
        click.echo(f"  Total API Keys: {total_api_keys}")
        click.echo(f"  Active API Keys: {active_api_keys}")
        
        click.echo("\n💾 STORAGE USAGE:")
        click.echo(f"  Uploads: {format_file_size(total_storage)}")
        click.echo(f"  Temp Files: {format_file_size(temp_storage)}")
        click.echo(f"  Processing: {format_file_size(processing_storage)}")
        click.echo(f"  Outputs: {format_file_size(outputs_storage)}")
        
        total_storage_all = total_storage + temp_storage + processing_storage + outputs_storage
        click.echo(f"  Total: {format_file_size(total_storage_all)}")
        
        click.echo("\n⚙️  SYSTEM INFO:")
        click.echo(f"  Database: {db.engine.url.drivername}")
        click.echo(f"  Upload Directory: {BaseConfig.UPLOAD_FOLDER}")
        click.echo(f"  Max File Size: {format_file_size(BaseConfig.MAX_CONTENT_LENGTH)}")
        
        click.echo("\n" + "=" * 60)
    
    @app.cli.command('check-health')
    @with_appcontext
    def check_health_command():
        """Check system health"""
        from src.app.config import BaseConfig
        
        click.echo("🔍 SYSTEM HEALTH CHECK")
        click.echo("-" * 40)
        
        # Check database connection
        try:
            db.session.execute('SELECT 1')
            click.echo("✓ Database: Connected")
        except Exception as e:
            click.echo(f"❌ Database: Error - {e}")
        
        # Check Redis connection (if configured)
        if 'redis' in BaseConfig.REDIS_URL:
            try:
                import redis
                redis_client = redis.from_url(BaseConfig.REDIS_URL)
                redis_client.ping()
                click.echo("✓ Redis: Connected")
            except Exception as e:
                click.echo(f"❌ Redis: Error - {e}")
        
        # Check directories
        directories = [
            (BaseConfig.UPLOAD_FOLDER, "Upload Directory"),
            (BaseConfig.TEMP_FOLDER, "Temp Directory"),
            (BaseConfig.PROCESSING_FOLDER, "Processing Directory"),
            (BaseConfig.OUTPUTS_FOLDER, "Outputs Directory"),
            (BaseConfig.LOGS_FOLDER, "Logs Directory"),
        ]
        
        for directory, name in directories:
            if directory.exists():
                click.echo(f"✓ {name}: Exists")
            else:
                click.echo(f"❌ {name}: Missing")
        
        # Check file permissions
        try:
            test_file = BaseConfig.TEMP_FOLDER / 'test_permission.txt'
            test_file.write_text('test')
            test_file.unlink()
            click.echo("✓ File Permissions: OK")
        except Exception as e:
            click.echo(f"❌ File Permissions: Error - {e}")
        
        # Check AI API keys (partial check)
        if BaseConfig.OPENAI_API_KEY:
            click.echo("✓ OpenAI API Key: Configured")
        else:
            click.echo("⚠️  OpenAI API Key: Not configured")
        
        if BaseConfig.STABILITY_API_KEY:
            click.echo("✓ Stability API Key: Configured")
        else:
            click.echo("⚠️  Stability API Key: Not configured")
        
        click.echo("-" * 40)
        click.echo("Health check complete")
    
    @app.cli.command('export-data')
    @with_appcontext
    @click.option('--output', type=click.Path(), required=True, help='Output directory for exported data')
    @click.option('--format', type=click.Choice(['json', 'csv']), default='json', help='Export format')
    @click.option('--data-type', type=click.Choice(['users', 'jobs', 'all']), default='all', help='Data type to export')
    def export_data_command(output, format, data_type):
        """Export data for analysis or backup"""
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if data_type in ['users', 'all']:
            users = User.query.all()
            user_data = [user.to_dict(include_sensitive=False) for user in users]
            
            if format == 'json':
                output_file = output_dir / f'users_export_{timestamp}.json'
                with open(output_file, 'w') as f:
                    json.dump(user_data, f, indent=2, default=str)
                click.echo(f"✓ Users exported to {output_file} ({len(users)} records)")
            elif format == 'csv':
                # Simplified CSV export
                import csv
                output_file = output_dir / f'users_export_{timestamp}.csv'
                if user_data:
                    with open(output_file, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=user_data[0].keys())
                        writer.writeheader()
                        writer.writerows(user_data)
                    click.echo(f"✓ Users exported to {output_file} ({len(users)} records)")
        
        if data_type in ['jobs', 'all']:
            jobs = VideoJob.query.all()
            job_data = [job.to_dict(include_details=False) for job in jobs]
            
            if format == 'json':
                output_file = output_dir / f'jobs_export_{timestamp}.json'
                with open(output_file, 'w') as f:
                    json.dump(job_data, f, indent=2, default=str)
                click.echo(f"✓ Jobs exported to {output_file} ({len(jobs)} records)")
            elif format == 'csv':
                import csv
                output_file = output_dir / f'jobs_export_{timestamp}.csv'
                if job_data:
                    with open(output_file, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=job_data[0].keys())
                        writer.writeheader()
                        writer.writerows(job_data)
                    click.echo(f"✓ Jobs exported to {output_file} ({len(jobs)} records)")
        
        click.echo(f"\n📊 Export complete to: {output_dir}")
    
    @app.cli.command('generate-api-key')
    @with_appcontext
    @click.option('--user-email', required=True, help='User email')
    @click.option('--name', required=True, help='API key name')
    @click.option('--scopes', default='read,write', help='Comma-separated list of scopes')
    @click.option('--rate-limit', default=1000, help='Rate limit (requests per hour)')
    @click.option('--expires-days', type=int, help='Number of days until expiration')
    def generate_api_key_command(user_email, name, scopes, rate_limit, expires_days):
        """Generate a new API key for a user"""
        user = User.query.filter_by(email=user_email).first()
        if not user:
            click.echo(f"❌ User with email {user_email} not found")
            return
        
        # Generate API key
        key, key_prefix, key_hash = APIKey.generate_key()
        
        # Create API key record
        api_key = APIKey(
            user_id=user.id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes.split(','),
            rate_limit=rate_limit
        )
        
        if expires_days:
            api_key.expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        db.session.add(api_key)
        db.session.commit()
        
        click.echo(f"✓ API key generated for {user_email}")
        click.echo(f"\n🔑 API KEY: {key}")
        click.echo(f"⚠️  IMPORTANT: Save this key now. It won't be shown again!")
        click.echo(f"\n📋 Details:")
        click.echo(f"  Name: {name}")
        click.echo(f"  Scopes: {scopes}")
        click.echo(f"  Rate Limit: {rate_limit} requests/hour")
        click.echo(f"  Expires: {api_key.expires_at.strftime('%Y-%m-%d') if api_key.expires_at else 'Never'}")
        click.echo(f"  Masked Key: {api_key.masked_key}")
    
    # ========== DEVELOPMENT COMMANDS ==========
    
    @app.cli.command('seed-test-data')
    @with_appcontext
    @click.option('--users', default=10, help='Number of test users to create')
    @click.option('--jobs-per-user', default=5, help='Number of test jobs per user')
    @click.confirmation_option(prompt='Are you sure you want to seed test data?')
    def seed_test_data_command(users, jobs_per_user):
        """Seed database with test data (development only)"""
        if app.config.get('ENV') == 'production':
            click.echo("❌ Cannot seed test data in production environment")
            return
        
        import random
        from faker import Faker
        from src.app.models import ProcessingStatus, SubscriptionTier
        
        fake = Faker()
        
        click.echo(f"Seeding {users} test users with {jobs_per_user} jobs each...")
        
        # Create test users
        for i in range(users):
            email = f"test{i+1}@example.com"
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                user = existing_user
            else:
                user = User(
                    email=email,
                    username=f"testuser{i+1}",
                    full_name=fake.name(),
                    subscription_tier=random.choice(list(SubscriptionTier)),
                    email_verified=True,
                    is_active=True
                )
                user.set_password('Test@123')
                db.session.add(user)
                db.session.commit()
            
            # Create test jobs for user
            for j in range(jobs_per_user):
                status = random.choice(list(ProcessingStatus))
                created_at = fake.date_time_between(start_date='-30d', end_date='now')
                
                job = VideoJob(
                    user_id=user.id,
                    original_filename=f"test_video_{j+1}.mp4",
                    file_name=f"test_video_{j+1}_{created_at.strftime('%Y%m%d_%H%M%S')}.mp4",
                    file_path=f"/uploads/test/test_video_{j+1}.mp4",
                    file_size=random.randint(1024 * 1024, 500 * 1024 * 1024),  # 1MB to 500MB
                    duration=random.uniform(30, 600),  # 30 seconds to 10 minutes
                    status=status,
                    progress=100 if status == ProcessingStatus.COMPLETED else random.randint(0, 100),
                    created_at=created_at,
                    updated_at=created_at
                )
                
                if status == ProcessingStatus.COMPLETED:
                    job.completed_at = created_at + timedelta(minutes=random.randint(1, 30))
                    job.processing_time = (job.completed_at - created_at).total_seconds()
                    job.transcription = {'text': fake.text(max_nb_chars=500)}
                    job.titles = [fake.sentence() for _ in range(3)]
                    job.thumbnails = [f"/thumbnails/test_{j+1}_{k}.jpg" for k in range(3)]
                
                db.session.add(job)
            
            if (i + 1) % 10 == 0:
                db.session.commit()
                click.echo(f"  Created {i+1} users...")
        
        db.session.commit()
        click.echo(f"✓ Test data seeded: {users} users with {jobs_per_user} jobs each")
    
    @app.cli.command('clear-cache')
    @with_appcontext
    def clear_cache_command():
        """Clear application cache"""
        from src.app.extensions import cache
        cache.clear()
        click.echo("✓ Application cache cleared")
    
    # ========== MONITORING COMMANDS ==========
    
    @app.cli.command('view-logs')
    @with_appcontext
    @click.option('--lines', default=100, help='Number of lines to show')
    @click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help='Filter by log level')
    @click.option('--search', help='Search term')
    def view_logs_command(lines, level, search):
        """View application logs"""
        from src.app.config import BaseConfig
        
        log_file = BaseConfig.LOG_FILE
        if not log_file.exists():
            click.echo(f"❌ Log file not found: {log_file}")
            return
        
        import subprocess
        cmd = ['tail', '-n', str(lines), str(log_file)]
        
        if level or search:
            # Use grep for filtering
            grep_cmd = ['grep']
            if level:
                grep_cmd.extend(['-i', f'"{level}"'])
            if search:
                grep_cmd.extend(['-i', f'"{search}"'])
            
            cmd1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            cmd2 = subprocess.Popen(grep_cmd, stdin=cmd1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cmd1.stdout.close()
            output, error = cmd2.communicate()
            
            if error and 'No such file or directory' not in error.decode():
                click.echo(f"Error: {error.decode()}")
            
            click.echo(output.decode())
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            click.echo(result.stdout)
    
    logger.info("✓ CLI commands registered")