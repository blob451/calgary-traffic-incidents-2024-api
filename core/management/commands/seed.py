from django.core.management.base import BaseCommand
from django.core.management import call_command

from core.models import Collision, WeatherStation, WeatherObservation, CityDailyWeather


class Command(BaseCommand):
    help = "Seed database: migrate, load weather, load collisions, build city weather, and create a sample flag if none. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument('--dir', default='Data', help='Data directory (default: Data)')
        parser.add_argument('--skip-migrate', action='store_true', help='Skip migrate step')

    def handle(self, *args, **opts):
        data_dir = opts['dir']
        if not opts['skip_migrate']:
            self.stdout.write(self.style.NOTICE('Applying migrations...'))
            call_command('migrate')

        self.stdout.write(self.style.NOTICE('Loading weather...'))
        call_command('load_weather', '--dir', data_dir)
        self.stdout.write(self.style.NOTICE('Loading collisions...'))
        call_command('load_collisions', '--dir', data_dir)
        self.stdout.write(self.style.NOTICE('Building city daily weather...'))
        call_command('build_city_weather')

        # Create a sample flag if none exists
        from api.serializers import FlagSerializer
        from core.models import Flag

        if not Flag.objects.exists():
            cid = Collision.objects.values_list('collision_id', flat=True).first()
            if cid:
                ser = FlagSerializer(data={'collision': cid, 'note': 'sample flag (seed)'})
                if ser.is_valid():
                    ser.save()

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"Seed summary: Collisions={Collision.objects.count()}, Stations={WeatherStation.objects.count()}, Observations={WeatherObservation.objects.count()}, CityDays={CityDailyWeather.objects.count()}, Flags={getattr(Flag, 'objects', None) and Flag.objects.count()}"
        ))

