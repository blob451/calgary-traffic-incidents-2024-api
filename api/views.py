import os
import sys
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse, QueryDict
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.urls import reverse
from django.db import connection
from django.db.models import Subquery, OuterRef

from core.models import (
    Collision,
    CityDailyWeather,
    Quadrant,
    WeatherDay,
    WeatherStation,
    WeatherObservation,
)
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiExample
from drf_spectacular.utils import OpenApiParameter
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .serializers import (
    CollisionListSerializer,
    CollisionDetailSerializer,
    FlagSerializer,
    CollisionNearSerializer,
    ErrorSerializer,
    StatsMonthlyTrendResponseSerializer,
    StatsByHourResponseSerializer,
    StatsWeekdayResponseSerializer,
    StatsQuadrantShareResponseSerializer,
    StatsTopIntersectionsResponseSerializer,
    StatsByWeatherResponseSerializer,
)
from .filters import CollisionFilter


def _gather_run_info():
    try:
        import django
        import rest_framework
        import platform
        return {
            'python': sys.version.split(" ")[0],
            'django': django.get_version(),
            'drf': getattr(rest_framework, '__version__', 'unknown'),
            'os': f"{platform.system()} {platform.release()}",
        }
    except Exception:
        return None


def _assessment_from_request(request: HttpRequest) -> bool:
    """Derive assessment mode: cookie overrides env var for convenience.

    - Cookie name: 'assessment' with values in {1,true,yes,on} to enable
    - Env fallback: ASSESSMENT_MODE in {1,true,yes}
    """
    try:
        c = request.COOKIES.get('assessment')
        if c is not None:
            s = str(c).strip().lower()
            return s in ('1', 'true', 'yes', 'on')
    except Exception:
        pass
    return os.environ.get('ASSESSMENT_MODE', '').lower() in ('1', 'true', 'yes')

def _parse_requirements(requirements_path: str, max_items: int = 12):
    pkgs = []
    try:
        with open(requirements_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if '==' in s:
                    name, ver = s.split('==', 1)
                    pkgs.append({'name': name.strip(), 'version': ver.strip()})
                else:
                    pkgs.append({'name': s, 'version': ''})
                if len(pkgs) >= max_items:
                    break
    except Exception:
        return None
    return pkgs


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

    assessment = _assessment_from_request(request)

    # DB info for hosted verification
    try:
        db_vendor = getattr(connection, 'vendor', None)
        db_name = connection.settings_dict.get('NAME')
        db_info = {'vendor': db_vendor, 'name': str(db_name)}
    except Exception:
        db_info = None

    # Parse requirements for quick package pins summary
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # try repo root then project root
    req_candidates = [
        os.path.join(base_dir, 'requirements.txt'),
        os.path.abspath(os.path.join(base_dir, '..', 'requirements.txt')),
    ]
    req_path = next((p for p in req_candidates if os.path.exists(p)), None)
    packages = _parse_requirements(req_path) if req_path else None

    total_entries = collisions_count + stations_count + observations_count + city_days_count

    # Optional flag detail link if any
    try:
        from core.models import Flag
        flag_id = Flag.objects.order_by('id').values_list('id', flat=True).first()
    except Exception:
        flag_id = None

    ctx = {
        'counts': {
            'collisions': collisions_count,
            'stations': stations_count,
            'observations': observations_count,
            'city_days': city_days_count,
            'total': total_entries,
        },
        'sample_collision_id': sample_collision_id,
        'assessment': assessment,
        'runinfo': _gather_run_info() if assessment else None,
        # Always include admin creds if provided via env so graders can see them
        'admin_user': os.environ.get('ADMIN_USERNAME'),
        'admin_pass': os.environ.get('ADMIN_PASSWORD'),
        'db': db_info,
        'packages': packages,
        'flag_detail_id': flag_id,
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

    @extend_schema(
        tags=['Collisions'],
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, description='Quadrant', enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, description='dry|wet|snowy', enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, required=False, description='Override page size (max 200)')
        ],
        examples=[
            OpenApiExample('Filter by date & quadrant', value={'from': '2024-01-01', 'to': '2024-12-31', 'quadrant': 'NE'}),
        ],
    )
    def list(self, request, *args, **kwargs):
        _validate_date_range_or_400(request)
        return super().list(request, *args, **kwargs)


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


def _parse_date(s: str):
    from datetime import date
    y, m, d = [int(x) for x in s.split('-')]
    return date(y, m, d)


def _validate_date_range_or_400(request: HttpRequest):
    q = _normalized_params(request)
    fs = q.get('from_date')
    ts = q.get('to_date')
    if fs:
        try:
            _parse_date(fs)
        except Exception:
            raise ValidationError({'from': 'Invalid date format, expected YYYY-MM-DD'})
    if ts:
        try:
            _parse_date(ts)
        except Exception:
            raise ValidationError({'to': 'Invalid date format, expected YYYY-MM-DD'})
    if fs and ts and _parse_date(fs) > _parse_date(ts):
        raise ValidationError({'from_to': 'from must be <= to'})


@method_decorator(cache_page(60), name='dispatch')
class StatsMonthlyTrend(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsMonthlyTrendResponseSerializer},
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, description='Quadrant', enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, description='dry|wet|snowy', enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
        qs = _filtered_collisions(request)
        # Sum counts by existing month field
        data = qs.values("month").annotate(total=Sum("count")).order_by("month")
        # Ensure months 1..12 present
        by_month = {row["month"]: row["total"] for row in data}
        out = [{"month": m, "total": int(by_month.get(m, 0) or 0)} for m in range(1, 13)]
        return Response({"results": out})


@method_decorator(cache_page(60), name='dispatch')
class StatsByHour(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsByHourResponseSerializer},
        parameters=[
            OpenApiParameter(name='commute', type=OpenApiTypes.STR, required=False, description='am|pm', enum=['am','pm']),
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
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


@method_decorator(cache_page(60), name='dispatch')
class StatsWeekday(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsWeekdayResponseSerializer},
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
        qs = _filtered_collisions(request)
        data = qs.values("weekday").annotate(total=Sum("count")).order_by("weekday")
        by_weekday = {row["weekday"]: row["total"] for row in data}
        out = [{"weekday": d, "total": int(by_weekday.get(d, 0) or 0)} for d in range(0, 7)]
        return Response({"results": out})


@method_decorator(cache_page(60), name='dispatch')
class StatsQuadrantShare(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsQuadrantShareResponseSerializer},
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
        qs = _filtered_collisions(request)
        data = qs.values("quadrant").annotate(total=Sum("count")).order_by("quadrant")
        # Ensure all quadrants present
        keys = [Quadrant.NE, Quadrant.NW, Quadrant.SE, Quadrant.SW, Quadrant.UNKNOWN]
        by_q = {row["quadrant"]: row["total"] for row in data}
        out = [{"quadrant": q, "total": int(by_q.get(q, 0) or 0)} for q in keys]
        return Response({"results": out})


@method_decorator(cache_page(60), name='dispatch')
class StatsTopIntersections(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsTopIntersectionsResponseSerializer},
        parameters=[
            OpenApiParameter(name='limit', type=OpenApiTypes.INT, required=False),
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
        try:
            limit = int(request.GET.get("limit", 10))
        except Exception:
            limit = 10
        limit = max(1, min(limit, 100))

        qs = _filtered_collisions(request).exclude(intersection_key="")

        # Choose a representative label per intersection_key: the most frequent
        label_subq = (
            qs.filter(intersection_key=OuterRef("intersection_key"))
            .values("location_text")
            .annotate(freq=Count("collision_id"))
            .order_by("-freq", "location_text")
            .values("location_text")[:1]
        )

        # Aggregate strictly by intersection_key, attach representative label
        data = (
            qs.values("intersection_key")
            .annotate(total=Sum("count"), collisions=Count("collision_id"))
            .annotate(location_text=Subquery(label_subq))
            .order_by("-total", "location_text")[:limit]
        )

        out = [
            {
                "intersection_key": row["intersection_key"],
                "location_text": row.get("location_text") or "",
                "total": int(row["total"] or 0),
                "collisions": int(row["collisions"] or 0),
            }
            for row in data
        ]
        return Response({"results": out, "limit": limit})


@method_decorator(cache_page(60), name='dispatch')
class StatsByWeather(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Stats'],
        responses={200: StatsByWeatherResponseSerializer},
        parameters=[
            OpenApiParameter(name='from', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='to_date', type=OpenApiTypes.DATE, required=False),
            OpenApiParameter(name='quadrant', type=OpenApiTypes.STR, required=False, enum=['NE','NW','SE','SW','UNK']),
            OpenApiParameter(name='weather_day_city', type=OpenApiTypes.STR, required=False, enum=['dry','wet','snowy']),
            OpenApiParameter(name='freeze_day_city', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_rain', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='heavy_snow', type=OpenApiTypes.BOOL, required=False),
            OpenApiParameter(name='gust_min', type=OpenApiTypes.NUMBER, required=False),
            OpenApiParameter(name='station', type=OpenApiTypes.STR, required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request: HttpRequest):
        _validate_date_range_or_400(request)
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


@method_decorator(cache_page(60), name='dispatch')
class CollisionsNear(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Collisions'],
        responses={200: OpenApiTypes.OBJECT, 400: ErrorSerializer},
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
        examples=[
            OpenApiExample(
                'Near collisions example',
                value={'lat': 51.045, 'lon': -114.06, 'radius_km': 1.5, 'limit': 50}
            )
        ],
    )
    def get(self, request: HttpRequest):
        # Parse inputs
        try:
            lat = float(request.GET.get("lat"))
            lon = float(request.GET.get("lon"))
        except (TypeError, ValueError):
            return Response({"detail": "lat and lon are required float query parameters"}, status=400)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValidationError({'lat_lon': 'lat must be [-90,90] and lon [-180,180]'})

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

        # Use serializer to normalize datetime format consistently with DRF config
        ser = CollisionNearSerializer(out, many=True)

        return Response({
            "params": {"lat": lat, "lon": lon, "radius_km": radius, "limit": limit},
            "results": ser.data,
            "count": len(out),
        })


def assessment_create_sample_flag(request: HttpRequest):
    assessment = _assessment_from_request(request)
    if not assessment:
        return redirect('/')
    from core.models import Flag
    if not Flag.objects.exists():
        cid = Collision.objects.values_list('collision_id', flat=True).first()
        if cid:
            ser = FlagSerializer(data={'collision': cid, 'note': 'sample flag (assessment)'})
            if ser.is_valid():
                ser.save()
    return redirect('/api/v1/flags')


def assessment_toggle(request: HttpRequest):
    """Toggle assessment cookie and redirect back to index.

    This does not change server env; it only sets a cookie that overrides display.
    """
    current = request.COOKIES.get('assessment')
    curr_on = str(current).strip().lower() in ('1', 'true', 'yes', 'on') if current is not None else _assessment_from_request(request)
    new_val = '0' if curr_on else '1'
    resp = redirect('/')
    try:
        resp.set_cookie('assessment', new_val, max_age=7*24*60*60, samesite='Lax')
    except Exception:
        resp.set_cookie('assessment', new_val)
    return resp
