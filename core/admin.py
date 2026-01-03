from django.contrib import admin

from core.models import (
    Collision,
    Flag,
    WeatherStation,
    WeatherObservation,
    CityDailyWeather,
)


@admin.register(WeatherStation)
class WeatherStationAdmin(admin.ModelAdmin):
    list_display = ("id", "climate_id", "name", "longitude", "latitude")
    search_fields = ("climate_id", "name")
    ordering = ("climate_id",)


@admin.register(WeatherObservation)
class WeatherObservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "station",
        "date",
        "t_max_c",
        "t_min_c",
        "total_precip_mm",
        "total_snow_cm",
        "gust_kmh",
        "weather_day",
        "freeze_day",
    )
    list_filter = ("weather_day", "freeze_day", "date")
    date_hierarchy = "date"
    search_fields = ("station__climate_id", "station__name")
    raw_id_fields = ("station",)


@admin.register(CityDailyWeather)
class CityDailyWeatherAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "weather_day_city",
        "freeze_day_city",
        "t_max_avg",
        "t_min_avg",
        "precip_any",
        "snow_any",
        "agreement_ratio",
    )
    list_filter = ("weather_day_city", "freeze_day_city", "date")
    date_hierarchy = "date"


@admin.register(Collision)
class CollisionAdmin(admin.ModelAdmin):
    list_display = (
        "collision_id",
        "date",
        "hour",
        "weekday",
        "month",
        "quadrant",
        "count",
        "nearest_station",
    )
    list_filter = ("quadrant", "date")
    search_fields = ("collision_id", "location_text", "description")
    ordering = ("-occurred_at",)
    date_hierarchy = "date"
    raw_id_fields = ("nearest_station",)


@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = ("id", "collision", "created_at")
    search_fields = ("collision__collision_id", "note")
    raw_id_fields = ("collision",)
