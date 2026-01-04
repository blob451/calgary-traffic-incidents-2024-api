import pytest
from datetime import date
from django.core.management import call_command
from core.models import WeatherStation, WeatherObservation, CityDailyWeather, WeatherDay


@pytest.mark.django_db
def test_build_city_weather_sets_daily_summary_fields():
    st1 = WeatherStation.objects.create(climate_id="3031001", name="Airport", longitude=-114.07, latitude=51.05)
    st2 = WeatherStation.objects.create(climate_id="3031002", name="University", longitude=-114.12, latitude=51.09)

    d = date(2024, 2, 15)

    WeatherObservation.objects.create(
        station=st1,
        date=d,
        t_max_c=1.0,
        t_min_c=-5.0,
        total_precip_mm=0.0,
        total_snow_cm=2.0,
        gust_kmh=25,
        weather_day=WeatherDay.SNOWY,
        freeze_day=True,
    )
    WeatherObservation.objects.create(
        station=st2,
        date=d,
        t_max_c=4.0,
        t_min_c=-2.0,
        total_precip_mm=1.2,
        total_snow_cm=0.0,
        gust_kmh=35,
        weather_day=WeatherDay.WET,
        freeze_day=False,
    )

    call_command("build_city_weather")

    cw = CityDailyWeather.objects.get(date=d)
    assert cw.weather_day_city == WeatherDay.SNOWY
    assert cw.freeze_day_city is True
    assert cw.precip_any is True
    assert cw.snow_any is True
    assert cw.t_max_avg == pytest.approx((1.0 + 4.0) / 2)
    assert cw.t_min_avg == pytest.approx((-5.0 + -2.0) / 2)
    assert cw.agreement_ratio == pytest.approx(0.5)
