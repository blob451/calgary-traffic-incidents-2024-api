from __future__ import annotations

from typing import Optional

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from core.models import (
    Collision,
    WeatherStation,
    WeatherObservation,
    CityDailyWeather,
)


class WeatherStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherStation
        fields = ["id", "climate_id", "name", "longitude", "latitude"]


class CollisionListSerializer(serializers.ModelSerializer):
    nearest_station = WeatherStationSerializer(read_only=True)

    class Meta:
        model = Collision
        fields = [
            "collision_id",
            "occurred_at",
            "date",
            "hour",
            "weekday",
            "month",
            "quadrant",
            "longitude",
            "latitude",
            "count",
            "location_text",
            "nearest_station",
        ]


class StationObsSerializer(serializers.Serializer):
    t_max_c = serializers.FloatField(allow_null=True)
    t_min_c = serializers.FloatField(allow_null=True)
    t_mean_c = serializers.FloatField(allow_null=True)
    total_precip_mm = serializers.FloatField(allow_null=True)
    total_snow_cm = serializers.FloatField(allow_null=True)
    gust_kmh = serializers.IntegerField(allow_null=True)


class CityWeatherSerializer(serializers.Serializer):
    weather_day_city = serializers.CharField(allow_null=True)
    freeze_day_city = serializers.BooleanField(allow_null=True)
    t_max_avg = serializers.FloatField(allow_null=True)
    t_min_avg = serializers.FloatField(allow_null=True)
    precip_any = serializers.BooleanField(allow_null=True)
    snow_any = serializers.BooleanField(allow_null=True)
    agreement_ratio = serializers.FloatField(allow_null=True)


class CollisionDetailSerializer(CollisionListSerializer):
    station_weather = serializers.SerializerMethodField()
    city_weather = serializers.SerializerMethodField()

    class Meta(CollisionListSerializer.Meta):
        fields = CollisionListSerializer.Meta.fields + [
            "description",
            "intersection_key",
            "station_weather",
            "city_weather",
        ]

    @extend_schema_field(StationObsSerializer)
    def get_station_weather(self, obj: Collision) -> Optional[dict]:
        if not obj.nearest_station:
            return None
        obs = (
            WeatherObservation.objects.filter(
                station=obj.nearest_station, date=obj.date
            )
            .values(
                "t_max_c",
                "t_min_c",
                "t_mean_c",
                "total_precip_mm",
                "total_snow_cm",
                "gust_kmh",
            )
            .first()
        )
        return obs or None

    @extend_schema_field(CityWeatherSerializer)
    def get_city_weather(self, obj: Collision) -> Optional[dict]:
        cw = (
            CityDailyWeather.objects.filter(date=obj.date)
            .values(
                "weather_day_city",
                "freeze_day_city",
                "t_max_avg",
                "t_min_avg",
                "precip_any",
                "snow_any",
                "agreement_ratio",
            )
            .first()
        )
        return cw or None


class FlagSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    collision = serializers.SlugRelatedField(
        slug_field="collision_id", queryset=Collision.objects.all()
    )
    note = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        from core.models import Flag

        return Flag.objects.create(**validated_data)

    def validate_note(self, value: str) -> str:
        if value is None or not str(value).strip():
            raise serializers.ValidationError("Note must not be empty.")
        s = str(value).strip()
        if len(s) > 1000:
            raise serializers.ValidationError("Note is too long (max 1000 chars).")
        return s

    def update(self, instance, validated_data):
        # Allow updating note and collision
        if "note" in validated_data:
            instance.note = self.validate_note(validated_data["note"])
        if "collision" in validated_data:
            instance.collision = validated_data["collision"]
        instance.save()
        return instance


class CollisionNearSerializer(serializers.Serializer):
    collision_id = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    quadrant = serializers.CharField()
    longitude = serializers.FloatField()
    latitude = serializers.FloatField()
    count = serializers.IntegerField()
    location_text = serializers.CharField(allow_blank=True)
    distance_km = serializers.FloatField()


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    # Optional field-wise errors when validation returns a dict of lists
    # Using generic mapping for docs clarity without over-constraining shape
    # e.g., {"from": ["Invalid date format"], "to": ["..."]}


# --- Stats serializers (for OpenAPI docs) ---


class StatsMonthlyItemSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    total = serializers.IntegerField()


class StatsMonthlyTrendResponseSerializer(serializers.Serializer):
    results = StatsMonthlyItemSerializer(many=True)


class StatsByHourItemSerializer(serializers.Serializer):
    hour = serializers.IntegerField()
    total = serializers.IntegerField()


class StatsByHourResponseSerializer(serializers.Serializer):
    results = StatsByHourItemSerializer(many=True)
    commute = serializers.CharField(allow_null=True, required=False)


class StatsWeekdayItemSerializer(serializers.Serializer):
    weekday = serializers.IntegerField()
    total = serializers.IntegerField()


class StatsWeekdayResponseSerializer(serializers.Serializer):
    results = StatsWeekdayItemSerializer(many=True)


class StatsQuadrantShareItemSerializer(serializers.Serializer):
    quadrant = serializers.CharField()
    total = serializers.IntegerField()


class StatsQuadrantShareResponseSerializer(serializers.Serializer):
    results = StatsQuadrantShareItemSerializer(many=True)


class StatsTopIntersectionsItemSerializer(serializers.Serializer):
    intersection_key = serializers.CharField()
    location_text = serializers.CharField(allow_blank=True)
    total = serializers.IntegerField()
    collisions = serializers.IntegerField()


class StatsTopIntersectionsResponseSerializer(serializers.Serializer):
    results = StatsTopIntersectionsItemSerializer(many=True)
    limit = serializers.IntegerField()


class StatsByWeatherItemSerializer(serializers.Serializer):
    weather_day = serializers.CharField()
    total = serializers.IntegerField()


class StatsByWeatherResponseSerializer(serializers.Serializer):
    results = StatsByWeatherItemSerializer(many=True)
