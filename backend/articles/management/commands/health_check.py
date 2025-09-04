# articles/management/commands/health_check.py
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Perform system health checks'
    
    def handle(self, *args, **options):
        self.stdout.write('Performing system health checks...')
        
        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            self.stdout.write(self.style.SUCCESS('Database: OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Database: {str(e)}'))
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            value = cache.get('health_check')
            if value == 'ok':
                self.stdout.write(self.style.SUCCESS('Cache: OK'))
            else:
                self.stdout.write(self.style.ERROR('Cache: Failed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Cache: {str(e)}'))