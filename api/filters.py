from __future__ import annotations

from typing import Optional

import django_filters as filters
from django.db.models import Exists, OuterRef

from core.models import Collision, CityDailyWeather, WeatherObservation, WeatherDay, Quadrant


def _str_to_bool(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return None


class CollisionFilter(filters.FilterSet):
    from_date = filters.DateFilter(field_name="date", lookup_expr="gte", label="from", method="filter_from")
    to_date = filters.DateFilter(field_name="date", lookup_expr="lte", label="to", method="filter_to")
    quadrant = filters.CharFilter(field_name="quadrant")
    weather_day_city = filters.CharFilter(method="filter_weather_day_city")
    freeze_day_city = filters.CharFilter(method="filter_freeze_day_city")
    heavy_rain = filters.CharFilter(method="filter_heavy_rain")
    heavy_snow = filters.CharFilter(method="filter_heavy_snow")
    gust_min = filters.NumberFilter(method="filter_gust_min")
    station = filters.CharFilter(method="filter_station")

    class Meta:
        model = Collision
        fields = []

    def filter_from(self, qs, name, value):
        return qs.filter(date__gte=value)

    def filter_to(self, qs, name, value):
        return qs.filter(date__lte=value)

    def filter_weather_day_city(self, qs, name, value):
        if not value:
            return qs
        mapping = {
            "dry": WeatherDay.DRY,
            "wet": WeatherDay.WET,
            "snowy": WeatherDay.SNOWY,
        }
        code = mapping.get(str(value).strip().lower())
        if not code:
            return qs
        dates = CityDailyWeather.objects.filter(weather_day_city=code).values("date")
        return qs.filter(date__in=dates)

    def filter_freeze_day_city(self, qs, name, value):
        v = _str_to_bool(value)
        if v is None:
            return qs
        dates = CityDailyWeather.objects.filter(freeze_day_city=v).values("date")
        return qs.filter(date__in=dates)

    def filter_heavy_rain(self, qs, name, value):
        v = _str_to_bool(value)
        if v is None:
            return qs
        dates = CityDailyWeather.objects.filter(precip_any=v).values("date")
        return qs.filter(date__in=dates)

    def filter_heavy_snow(self, qs, name, value):
        v = _str_to_bool(value)
        if v is None:
            return qs
        dates = CityDailyWeather.objects.filter(snow_any=v).values("date")
        return qs.filter(date__in=dates)

    def filter_gust_min(self, qs, name, value):
        try:
            threshold = float(value)
        except Exception:
            return qs
        exists = WeatherObservation.objects.filter(
            station_id=OuterRef("nearest_station_id"),
            date=OuterRef("date"),
            gust_kmh__gte=threshold,
        )
        return qs.filter(Exists(exists))

    def filter_station(self, qs, name, value):
        s = str(value).strip()
        if not s:
            return qs
        if s.isdigit():
            return qs.filter(nearest_station_id=int(s))
        # try match on climate_id or name
        return qs.filter(nearest_station__climate_id=s)

