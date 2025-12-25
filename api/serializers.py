from __future__ import annotations

from typing import Optional

from rest_framework import serializers

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

