from pathlib import Path
import textwrap

from django.core.management import call_command

from core.models import WeatherStation, WeatherObservation, Collision, WeatherDay


def test_load_weather_command_small(tmp_path, db, settings):
    data = textwrap.dedent(
        '''\
        "Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time","Year","Month","Day","Max Temp (°C)","Min Temp (°C)","Total Precip (mm)","Total Snow (cm)","Spd of Max Gust (km/h)"
        "-114.01","51.12","CALGARY INTL A","3031092","2024-01-01","2024","01","01","3.0","-5.0","0.0","0.0","20"
        "-114.01","51.12","CALGARY INTL A","3031092","2024-01-02","2024","01","02","2.0","-1.0","1.2","0.0","40"
        '''
    )
    f = tmp_path / "en_climate_daily_AB_3031092_2024_P1D.csv"
    f.write_text(data, encoding="utf-8")

    call_command("load_weather", "--dir", str(tmp_path))

    assert WeatherStation.objects.filter(climate_id="3031092").exists()
    assert WeatherObservation.objects.filter(station__climate_id="3031092").count() == 2


def test_load_collisions_command_small(tmp_path, db, settings):
    # Collision CSV with two rows
    data = textwrap.dedent(
        '''\
        "INCIDENT INFO","DESCRIPTION","START_DT","MODIFIED_DT","QUADRANT","Longitude","Latitude","Count","id","Point"
        "Loc A","Incident.","2024/12/31 11:31:14 PM","2024/12/31 11:55:02 PM","SE","-114.0717","50.9686","1","COLL-1","POINT (-114.0717 50.9686)"
        "Loc B","Incident.","2024/12/31 10:16:11 PM","2025/01/01 12:19:14 AM","NW","-114.0266","50.9541","2","COLL-2","POINT (-114.0266 50.9541)"
        '''
    )
    f = tmp_path / "Traffic_Incidents_20251218.csv"
    f.write_text(data, encoding="utf-8")

    call_command("load_collisions", "--csv", str(f))

    assert Collision.objects.count() == 2
    assert Collision.objects.filter(collision_id="COLL-1", count=1).exists()
    assert Collision.objects.filter(collision_id="COLL-2", count=2).exists()


def test_load_weather_handles_trace_and_missing(tmp_path, db, settings):
    data = textwrap.dedent(
        '''\
        "Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time","Total Precip (mm)","Total Snow (cm)","Min Temp (A�C)"
        "-114.01","51.12","CALGARY INTL A","3031999","2024-02-01","T","0.0","-0.5"
        "-114.01","51.12","CALGARY INTL A","","2024-02-02","0.3","T","-1.0"
        "-114.01","51.12","CALGARY INTL A","3031999","bad-date","0.0","0.0","-5.0"
        '''
    )
    (tmp_path / "en_climate_daily_AB_3031999_2024_P1D.csv").write_text(data, encoding="utf-8")

    call_command("load_weather", "--dir", str(tmp_path))

    station = WeatherStation.objects.get(climate_id="3031999")
    obs = WeatherObservation.objects.get(station=station, date="2024-02-01")
    assert obs.total_precip_mm == 0.0
    assert obs.total_snow_cm == 0.0
    assert obs.weather_day == WeatherDay.DRY
    assert obs.freeze_day is True


def test_load_collisions_skip_reasons(tmp_path, db, settings, capsys):
    data = textwrap.dedent(
        '''\
        "INCIDENT INFO","DESCRIPTION","START_DT","MODIFIED_DT","QUADRANT","Longitude","Latitude","Count","id","Point"
        "No Id","Desc","2024/01/02 01:00:00 AM","2024/01/02 01:05:00 AM","SE","-114.0","50.9","1","","POINT (-114 50.9)"
        "Bad Coords","Desc","2024/01/02 01:00:00 AM","2024/01/02 01:05:00 AM","NW","nan","50.9","1","BAD-1","POINT (-114 50.9)"
        "Good","Desc","2024/01/02 01:00:00 AM","2024/01/02 01:05:00 AM","NE","-114.02","50.95","","GOOD-1","POINT (-114.02 50.95)"
        '''
    )
    f = tmp_path / "Traffic_Incidents_Sample.csv"
    f.write_text(data, encoding="utf-8")

    call_command("load_collisions", "--csv", str(f))

    captured = capsys.readouterr().out
    assert "no_id=1" in captured and "invalid_coords=1" in captured
    assert Collision.objects.filter(collision_id="GOOD-1", count=1).exists()
