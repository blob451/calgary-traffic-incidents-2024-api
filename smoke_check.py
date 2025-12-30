import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','calgary_collisions.settings')
import django
django.setup()
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
from django.test import Client
c = Client(HTTP_HOST='localhost')
# Enable assessment to show run info
c.cookies['assessment'] = '1'

checks = []

def add(name, path, status):
    checks.append((name, path, status))

resp = c.get('/')
add('index', '/', resp.status_code)

resp = c.get('/api/schema/')
add('schema', '/api/schema/', resp.status_code)

for path in ['/docs/', '/redoc/']:
    r = c.get(path)
    add(path.strip('/'), path, r.status_code)

resp = c.get('/api/v1/collisions/')
add('collisions', '/api/v1/collisions/', resp.status_code)

# Stats endpoints
for path in [
  '/api/v1/stats/monthly-trend',
  '/api/v1/stats/by-hour',
  '/api/v1/stats/weekday',
  '/api/v1/stats/quadrant-share',
  '/api/v1/stats/top-intersections?limit=10',
  '/api/v1/stats/by-weather',
]:
    r = c.get(path)
    add(path.split('/')[-1], path, r.status_code)

# Near endpoint
r = c.get('/api/v1/collisions/near?lat=51.045&lon=-114.06&radius_km=1.5')
add('near', '/api/v1/collisions/near?lat=51.045&lon=-114.06&radius_km=1.5', r.status_code)

# Flags CRUD smoke
r = c.get('/api/v1/flags/')
add('flags-list', '/api/v1/flags/', r.status_code)

from core.models import Collision
cid = Collision.objects.values_list('collision_id', flat=True).first()
if cid:
    r = c.post('/api/v1/flags/', data={'collision': cid, 'note': 'smoke'}, content_type='application/json')
    add('flags-create', '/api/v1/flags/ (POST)', r.status_code)

r = c.get('/assessment/toggle')
add('assessment-toggle', '/assessment/toggle', r.status_code)

for name, path, st in checks:
    print(f"{name}\t{st}\t{path}")
