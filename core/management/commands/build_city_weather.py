from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import WeatherObservation, CityDailyWeather, WeatherDay


class Command(BaseCommand):
    help = "Build city-level daily weather aggregates from station observations."

    def handle(self, *args, **options):
        dates = (
            WeatherObservation.objects.order_by().values_list("date", flat=True).distinct()
        )
        created = 0
        updated = 0
        with transaction.atomic():
            for d in dates:
                qs = WeatherObservation.objects.filter(date=d)
                # Collect values ignoring nulls
                t_max_vals = [v for v in qs.values_list("t_max_c", flat=True) if v is not None]
                t_min_vals = [v for v in qs.values_list("t_min_c", flat=True) if v is not None]
                precip_vals = [v for v in qs.values_list("total_precip_mm", flat=True) if v is not None]
                snow_vals = [v for v in qs.values_list("total_snow_cm", flat=True) if v is not None]
                weather_days = [v for v in qs.values_list("weather_day", flat=True) if v]
                freeze_days = [v for v in qs.values_list("freeze_day", flat=True) if v is not None]

                t_max_avg = mean(t_max_vals) if t_max_vals else None
                t_min_avg = mean(t_min_vals) if t_min_vals else None
                precip_any = bool([x for x in precip_vals if x > 0]) if precip_vals else None
                snow_any = bool([x for x in snow_vals if x > 0]) if snow_vals else None

                # Determine weather_day_city deterministically: Snowy > Wet > Dry
                day_city: Optional[str] = None
                if any((x or 0) > 0 for x in snow_vals):
                    day_city = WeatherDay.SNOWY
                elif any((x or 0) >= 0.2 for x in precip_vals):
                    day_city = WeatherDay.WET
                else:
                    day_city = WeatherDay.DRY

                # freeze_day_city by majority (fallback to any if majority uncertain)
                freeze_city: Optional[bool] = None
                if freeze_days:
                    true_count = sum(1 for v in freeze_days if v)
                    freeze_city = true_count >= (len(freeze_days) / 2)

                # agreement ratio: share of stations matching city day
                agree_ratio: Optional[float] = None
                if weather_days:
                    match = sum(1 for v in weather_days if v == day_city)
                    agree_ratio = match / len(weather_days)

                defaults = {
                    "weather_day_city": day_city,
                    "freeze_day_city": freeze_city,
                    "t_max_avg": t_max_avg,
                    "t_min_avg": t_min_avg,
                    "precip_any": precip_any,
                    "snow_any": snow_any,
                    "agreement_ratio": agree_ratio,
                }
                obj, was_created = CityDailyWeather.objects.update_or_create(date=d, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"City daily weather upserted: created={created}, updated={updated}"))
        return 0

