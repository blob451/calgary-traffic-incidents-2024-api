import random
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import factory
from faker import Faker

from core.models import (
    WeatherStation,
    WeatherObservation,
    CityDailyWeather,
    Collision,
    Flag,
    Quadrant,
    WeatherDay,
)

fake = Faker()


class WeatherStationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WeatherStation

    climate_id = factory.Sequence(lambda n: f"3031{n:03d}")
    name = factory.LazyAttribute(lambda o: f"Station {o.climate_id}")
    longitude = factory.LazyFunction(lambda: random.uniform(-114.3, -113.8))
    latitude = factory.LazyFunction(lambda: random.uniform(50.9, 51.2))


class WeatherObservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WeatherObservation

    station = factory.SubFactory(WeatherStationFactory)
    date = factory.LazyFunction(lambda: date(2024, 1, 1) + timedelta(days=random.randint(0, 365)))
    t_max_c = factory.LazyFunction(lambda: random.uniform(-20, 30))
    t_min_c = factory.LazyFunction(lambda: random.uniform(-30, 15))
    total_precip_mm = factory.LazyFunction(lambda: random.choice([0.0, 0.5, 2.0]))
    total_snow_cm = factory.LazyFunction(lambda: random.choice([0.0, 1.0]))
    gust_kmh = factory.LazyFunction(lambda: random.choice([None, 20, 40, 60]))
    weather_day = factory.LazyFunction(lambda: random.choice([WeatherDay.DRY, WeatherDay.WET, WeatherDay.SNOWY]))
    freeze_day = factory.LazyFunction(lambda: random.choice([True, False]))


class CityDailyWeatherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CityDailyWeather

    date = factory.LazyFunction(lambda: date(2024, 1, 1) + timedelta(days=random.randint(0, 365)))
    weather_day_city = factory.LazyFunction(lambda: random.choice([WeatherDay.DRY, WeatherDay.WET, WeatherDay.SNOWY]))
    freeze_day_city = factory.LazyFunction(lambda: random.choice([True, False]))
    t_max_avg = factory.LazyFunction(lambda: random.uniform(-15, 25))
    t_min_avg = factory.LazyFunction(lambda: random.uniform(-25, 10))
    precip_any = factory.LazyFunction(lambda: random.choice([True, False]))
    snow_any = factory.LazyFunction(lambda: random.choice([True, False]))
    agreement_ratio = factory.LazyFunction(lambda: random.uniform(0.4, 1.0))


class CollisionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collision

    collision_id = factory.Sequence(lambda n: f"C{2024}{n:05d}")
    @factory.lazy_attribute
    def occurred_at(self):
        tz = ZoneInfo("America/Edmonton")
        dt = datetime(2024, 6, 1, 12, 0, 0, tzinfo=tz) + timedelta(hours=random.randint(0, 500))
        return dt
    @factory.lazy_attribute
    def date(self):
        return self.occurred_at.date()
    hour = factory.LazyAttribute(lambda o: o.occurred_at.hour)
    weekday = factory.LazyAttribute(lambda o: o.occurred_at.weekday())
    month = factory.LazyAttribute(lambda o: o.occurred_at.month)
    quadrant = factory.LazyFunction(lambda: random.choice([Quadrant.NE, Quadrant.NW, Quadrant.SE, Quadrant.SW]))
    longitude = factory.LazyFunction(lambda: random.uniform(-114.3, -113.8))
    latitude = factory.LazyFunction(lambda: random.uniform(50.9, 51.2))
    count = factory.LazyFunction(lambda: random.choice([1, 1, 2]))
    description = factory.LazyFunction(lambda: fake.sentence(nb_words=6))
    location_text = factory.LazyFunction(lambda: fake.street_name())
    intersection_key = factory.LazyAttribute(lambda o: f"{round(o.latitude,4)}:{round(o.longitude,4)}")
    nearest_station = factory.SubFactory(WeatherStationFactory)


class FlagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Flag

    collision = factory.SubFactory(CollisionFactory)
    note = factory.LazyFunction(lambda: fake.sentence())

