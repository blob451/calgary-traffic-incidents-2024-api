from django.db import models


class Quadrant(models.TextChoices):
    NW = "NW", "NW"
    NE = "NE", "NE"
    SW = "SW", "SW"
    SE = "SE", "SE"
    UNKNOWN = "UNK", "Unknown"


class WeatherDay(models.TextChoices):
    DRY = "DRY", "Dry"
    WET = "WET", "Wet"
    SNOWY = "SNY", "Snowy"


class WeatherStation(models.Model):
    climate_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    longitude = models.FloatField()
    latitude = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=["climate_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.climate_id})"


class WeatherObservation(models.Model):
    station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name="observations")
    date = models.DateField()

    t_max_c = models.FloatField(null=True, blank=True)
    t_min_c = models.FloatField(null=True, blank=True)
    t_mean_c = models.FloatField(null=True, blank=True)
    total_rain_mm = models.FloatField(null=True, blank=True)
    total_snow_cm = models.FloatField(null=True, blank=True)
    total_precip_mm = models.FloatField(null=True, blank=True)
    snow_on_ground_cm = models.FloatField(null=True, blank=True)
    gust_dir_10deg = models.IntegerField(null=True, blank=True)
    gust_kmh = models.IntegerField(null=True, blank=True)

    weather_day = models.CharField(max_length=3, choices=WeatherDay.choices, null=True, blank=True)
    freeze_day = models.BooleanField(null=True, blank=True)

    class Meta:
        unique_together = ("station", "date")
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["station", "date"]),
            models.Index(fields=["weather_day"]),
            models.Index(fields=["freeze_day"]),
        ]

    def __str__(self) -> str:
        return f"Obs {self.station_id} {self.date}"


class CityDailyWeather(models.Model):
    date = models.DateField(unique=True)
    weather_day_city = models.CharField(max_length=3, choices=WeatherDay.choices, null=True, blank=True)
    freeze_day_city = models.BooleanField(null=True, blank=True)
    t_max_avg = models.FloatField(null=True, blank=True)
    t_min_avg = models.FloatField(null=True, blank=True)
    precip_any = models.BooleanField(null=True, blank=True)
    snow_any = models.BooleanField(null=True, blank=True)
    agreement_ratio = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["date"])]

    def __str__(self) -> str:
        return f"CityWeather {self.date}"


class Collision(models.Model):
    collision_id = models.CharField(max_length=64, unique=True, db_index=True)
    occurred_at = models.DateTimeField()
    modified_at = models.DateTimeField(null=True, blank=True)
    date = models.DateField(db_index=True)
    hour = models.PositiveSmallIntegerField(null=True, blank=True)
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)

    quadrant = models.CharField(max_length=3, choices=Quadrant.choices, default=Quadrant.UNKNOWN, db_index=True)
    longitude = models.FloatField()
    latitude = models.FloatField()
    count = models.PositiveIntegerField(default=1)

    description = models.TextField(blank=True)
    location_text = models.CharField(max_length=255, blank=True)
    intersection_key = models.CharField(max_length=64, blank=True, db_index=True)

    nearest_station = models.ForeignKey(
        WeatherStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nearest_collisions",
    )

    class Meta:
        indexes = [
            models.Index(fields=["date", "quadrant"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["nearest_station"]),
        ]

    def __str__(self) -> str:
        return f"Collision {self.collision_id}"


class Flag(models.Model):
    collision = models.ForeignKey(Collision, on_delete=models.CASCADE, related_name="flags")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Flag for {self.collision.collision_id}"


# Create your models here.
