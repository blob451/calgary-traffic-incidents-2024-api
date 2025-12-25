from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'api/v1/collisions', views.CollisionViewSet, basename='collisions')
router.register(r'api/v1/flags', views.FlagViewSet, basename='flags')

urlpatterns = [
    path('', views.index, name='index'),
    path('', include(router.urls)),
]
