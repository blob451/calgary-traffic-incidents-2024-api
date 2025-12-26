from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, QueryDict
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from rest_framework.permissions import AllowAny
from django.urls import reverse

from core.models import (
    Collision,
    CityDailyWeather,
    Quadrant,
    WeatherDay,
    WeatherStation,
    WeatherObservation,
)
from drf_spectacular.utils import extend_schema, OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from .serializers import (
    CollisionListSerializer,
    CollisionDetailSerializer,
    FlagSerializer,
)
from .filters import CollisionFilter

def index(request: HttpRequest) -> HttpResponse:
    # Basic counts to signal DB seeding status
    collisions_count = Collision.objects.count()
    stations_count = WeatherStation.objects.count()
    observations_count = WeatherObservation.objects.count()
    city_days_count = CityDailyWeather.objects.count()

    # Provide a sample collision_id for a quick detail link
    sample_collision_id = (
        Collision.objects.order_by('-occurred_at')
        .values_list('collision_id', flat=True)
        .first()
    )

    ctx = {
        'counts': {
            'collisions': collisions_count,
            'stations': stations_count,
            'observations': observations_count,
            'city_days': city_days_count,
        },
        'sample_collision_id': sample_collision_id,
    }
    return render(request, 'index.html', ctx)


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


class FlagViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FlagSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        from core.models import Flag

        return Flag.objects.select_related("collision").order_by("-created_at")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        try:
            flag_id = response.data.get('id')
            if flag_id is not None:
                loc = request.build_absolute_uri(reverse('flags-detail', args=[flag_id]))
                response['Location'] = loc
        except Exception:
            pass
        # Ensure 201 Created
        response.status_code = status.HTTP_201_CREATED
        return response


def _normalized_params(request: HttpRequest) -> QueryDict:
    """Map common alias params (e.g., from/to) to filter params."""
    q = request.GET.copy()
    if "from" in q and "from_date" not in q:
        q["from_date"] = q.get("from")
    if "to" in q and "to_date" not in q:
        q["to_date"] = q.get("to")
    return q


def _filtered_collisions(request: HttpRequest):
    qs = Collision.objects.all()
    f = CollisionFilter(_normalized_params(request), queryset=qs)
    return f.qs


class StatsMonthlyTrend(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, description='NE|NW|SE|SW|UNK'),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, description='dry|wet|snowy'),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        # Sum counts by existing month field
        data = qs.values("month").annotate(total=Sum("count")).order_by("month")
        # Ensure months 1..12 present
        by_month = {row["month"]: row["total"] for row in data}
        out = [{"month": m, "total": int(by_month.get(m, 0) or 0)} for m in range(1, 13)]
        return Response({"results": out})


class StatsByHour(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='commute', type=OpenApiTypes.STR, required=False, description='am|pm'),
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
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

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        qs = _filtered_collisions(request)
        data = qs.values("weekday").annotate(total=Sum("count")).order_by("weekday")
        by_weekday = {row["weekday"]: row["total"] for row in data}
        out = [{"weekday": d, "total": int(by_weekday.get(d, 0) or 0)} for d in range(0, 7)]
        return Response({"results": out})


class StatsQuadrantShare(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
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

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='limit', type=OpenApiTypes.INT, required=False),
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
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

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
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
            d2["date"]: d2["weather_day_city"]
            for d2 in CityDailyWeather.objects.filter(
                date__in=[p["date"] for p in per_date]
            ).values("date", "weather_day_city")
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


# --- Stage 6: Near endpoint ---
from math import radians, sin, cos, asin, sqrt


def _bbox(lat: float, lon: float, radius_km: float):
    # Approximate degree deltas
    lat_delta = radius_km / 111.32
    # Avoid division by zero at poles; cos in radians
    lon_delta = radius_km / max(1e-6, (111.32 * abs(cos(radians(lat)))))
    return (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta)


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371 * c


class CollisionsNear(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='lat', type=OpenApiTypes.NUMBER, required=True),
            OpenApiParameter(name='lon', type=OpenApiTypes.NUMBER, required=True),
            OpenApiParameter(name='radius_km', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='limit', type=OpenApiTypes.INT, required=False),
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        # Parse inputs
        try:
            lat = float(request.GET.get("lat"))
            lon = float(request.GET.get("lon"))
        except (TypeError, ValueError):
            return Response({"detail": "lat and lon are required float query parameters"}, status=400)

        try:
            radius = float(request.GET.get("radius_km", 1.0))
        except ValueError:
            radius = 1.0
        if radius <= 0:
            radius = 1.0
        radius = min(radius, 10.0)

        try:
            limit = int(request.GET.get("limit", 100))
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 500))

        lat_min, lat_max, lon_min, lon_max = _bbox(lat, lon, radius)

        base = _filtered_collisions(request)
        # Apply coarse bounding box first
        qs = base.filter(latitude__gte=lat_min, latitude__lte=lat_max, longitude__gte=lon_min, longitude__lte=lon_max)

        # Select only needed fields for distance computation
        rows = list(
            qs.values(
                "collision_id",
                "occurred_at",
                "quadrant",
                "longitude",
                "latitude",
                "count",
                "location_text",
            )
        )

        # Compute precise distance and filter to radius
        out = []
        for r in rows:
            rlon = float(r["longitude"])
            rlat = float(r["latitude"])
            d = _haversine_km(lon, lat, rlon, rlat)
            if d <= radius:
                out.append({
                    "collision_id": r["collision_id"],
                    "occurred_at": r["occurred_at"],
                    "quadrant": r["quadrant"],
                    "longitude": rlon,
                    "latitude": rlat,
                    "count": int(r["count"] or 1),
                    "location_text": r["location_text"],
                    "distance_km": round(d, 3),
                })

        out.sort(key=lambda x: x["distance_km"])  # nearest first
        out = out[:limit]

        return Response({
            "params": {"lat": lat, "lon": lon, "radius_km": radius, "limit": limit},
            "results": out,
            "count": len(out),
        })
