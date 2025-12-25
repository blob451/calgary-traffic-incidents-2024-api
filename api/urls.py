from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'api/v1/collisions', views.CollisionViewSet, basename='collisions')
router.register(r'api/v1/flags', views.FlagViewSet, basename='flags')

urlpatterns = [
    path('', views.index, name='index'),
    path('', include(router.urls)),
    # Stats endpoints
    path('api/v1/stats/monthly-trend', views.StatsMonthlyTrend.as_view(), name='stats-monthly-trend'),
    path('api/v1/stats/by-hour', views.StatsByHour.as_view(), name='stats-by-hour'),
    path('api/v1/stats/weekday', views.StatsWeekday.as_view(), name='stats-weekday'),
    path('api/v1/stats/quadrant-share', views.StatsQuadrantShare.as_view(), name='stats-quadrant-share'),
    path('api/v1/stats/top-intersections', views.StatsTopIntersections.as_view(), name='stats-top-intersections'),
    path('api/v1/stats/by-weather', views.StatsByWeather.as_view(), name='stats-by-weather'),
    path('api/v1/collisions/near', views.CollisionsNear.as_view(), name='collisions-near'),
]
