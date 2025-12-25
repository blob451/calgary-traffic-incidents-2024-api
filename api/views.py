from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny

from core.models import Collision, CityDailyWeather, Quadrant, WeatherDay
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


def _filtered_collisions(request: HttpRequest):
    qs = Collision.objects.all()
    f = CollisionFilter(request.GET, queryset=qs)
    return f.qs


class StatsMonthlyTrend(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        # Annotate month and sum counts
        data = (
            qs.annotate(month=ExtractMonth("date"))
            .values("month")
            .annotate(total=Sum("count"))
            .order_by("month")
        )
        # Ensure months 1..12 present
        by_month = {row["month"]: row["total"] for row in data}
        out = [{"month": m, "total": int(by_month.get(m, 0) or 0)} for m in range(1, 13)]
        return Response({"results": out})


class StatsByHour(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        commute = (request.GET.get("commute") or "").lower().strip()
        qs = _filtered_collisions(request)
        if commute == "am":
            qs = qs.filter(hour__in=[7, 8, 9])
        elif commute == "pm":
            qs = qs.filter(hour__in=[16, 17, 18])
        data = (
            qs.values("hour")
            .annotate(total=Sum("count"))
            .order_by("hour")
        )
        by_hour = {row["hour"]: row["total"] for row in data}
        out = [{"hour": h, "total": int(by_hour.get(h, 0) or 0)} for h in range(0, 24)]
        return Response({"results": out, "commute": commute or None})


class StatsWeekday(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        data = qs.values("weekday").annotate(total=Sum("count")).order_by("weekday")
        by_weekday = {row["weekday"]: row["total"] for row in data}
        out = [{"weekday": d, "total": int(by_weekday.get(d, 0) or 0)} for d in range(0, 7)]
        return Response({"results": out})


class StatsQuadrantShare(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        data = qs.values("quadrant").annotate(total=Sum("count")).order_by("quadrant")
        # Ensure all quadrants present
        keys = [Quadrant.NE, Quadrant.NW, Quadrant.SE, Quadrant.SW, Quadrant.UNKNOWN]
        by_q = {row["quadrant"]: row["total"] for row in data}
        out = [{"quadrant": q, "total": int(by_q.get(q, 0) or 0)} for q in keys]
        return Response({"results": out})


class StatsTopIntersections(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        try:
            limit = int(request.GET.get("limit", 10))
        except Exception:
            limit = 10
        limit = max(1, min(limit, 100))

        qs = _filtered_collisions(request).exclude(intersection_key="")
        data = (
            qs.values("intersection_key", "location_text")
            .annotate(total=Sum("count"), n=Count("collision_id"))
            .order_by("-total", "location_text")[:limit]
        )
        out = [
            {
                "intersection_key": row["intersection_key"],
                "location_text": row["location_text"],
                "total": int(row["total"] or 0),
                "collisions": int(row["n"] or 0),
            }
            for row in data
        ]
        return Response({"results": out, "limit": limit})


class StatsByWeather(APIView):
    permission_classes = [AllowAny]

    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        # Join via date to CityDailyWeather for city-level weather day
        dates = list(qs.values_list("date", flat=True).distinct())
        weather = (
            CityDailyWeather.objects.filter(date__in=dates)
            .values("weather_day_city")
            .annotate(days=Count("date"))
        )
        # Totals for collisions per weather day
        mapping = {WeatherDay.DRY: 0, WeatherDay.WET: 0, WeatherDay.SNOWY: 0}
        # count collisions grouped by date, then map to weather_day_city
        per_date = qs.values("date").annotate(total=Sum("count"))
        weather_by_date = {
            d["date"]: d2["weather_day_city"]
            for d2 in CityDailyWeather.objects.filter(date__in=[p["date"] for p in per_date]).values(
                "date", "weather_day_city"
            )
        }
        for row in per_date:
            day = weather_by_date.get(row["date"]) or None
            if day in mapping:
                mapping[day] += int(row["total"] or 0)
        out = [
            {"weather_day": k, "total": v}
            for k, v in (
                (WeatherDay.DRY, mapping[WeatherDay.DRY]),
                (WeatherDay.WET, mapping[WeatherDay.WET]),
                (WeatherDay.SNOWY, mapping[WeatherDay.SNOWY]),
            )
        ]
        return Response({"results": out})
