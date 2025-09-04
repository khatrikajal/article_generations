from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Setup the article generation system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a default superuser'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Setting up Article Generation System...')
        
        # Run migrations
        self.stdout.write('Running migrations...')
        call_command('migrate', verbosity=0)
        
        # Collect static files
        self.stdout.write('Collecting static files...')
        call_command('collectstatic', '--noinput', verbosity=0)
        
        # Create superuser if requested
        if options['create_superuser']:
            self.create_default_superuser()
        
        self.stdout.write(
            self.style.SUCCESS('System setup completed successfully!')
        )
    
    def create_default_superuser(self):
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                'admin', 
                'admin@example.com', 
                'admin123'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    'Superuser created: admin/admin123'
                )
            )
        else:
            self.stdout.write('Superuser already exists')

