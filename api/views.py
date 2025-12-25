from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny

from core.models import Collision
from .serializers import (
    CollisionListSerializer,
    CollisionDetailSerializer,
    FlagSerializer,
)
from .filters import CollisionFilter

def index(request: HttpRequest) -> HttpResponse:
    return render(request, 'index.html')


class CollisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Collision.objects.select_related("nearest_station").order_by("-occurred_at")
    )
    permission_classes = [AllowAny]
    lookup_field = "collision_id"
    lookup_value_regex = r"[^/]+"
    filterset_class = CollisionFilter
    search_fields = ["description", "location_text"]
    ordering_fields = ["occurred_at", "date", "quadrant", "count"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CollisionDetailSerializer
        return CollisionListSerializer


class FlagViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = FlagSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        from core.models import Flag

        return Flag.objects.select_related("collision").order_by("-created_at")
