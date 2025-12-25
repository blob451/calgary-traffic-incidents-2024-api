from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, Iterable, Dict, Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.conf import settings

from core.models import WeatherStation, WeatherObservation, WeatherDay


def _norm_header(name: str) -> str:
    return name.strip().lower()


def _get(row: Dict[str, str], keys: Iterable[str], default: Optional[str] = None) -> Optional[str]:
    # case-insensitive partial key match helper
    lower_map = {k.lower(): v for k, v in row.items()}
    for key in keys:
        key_l = key.lower()
        # exact
        if key_l in lower_map:
            return lower_map[key_l]
        # partial contains
        for k in lower_map.keys():
            if key_l in k:
                return lower_map[k]
    return default


def _coerce_float(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    s = val.strip()
    if not s:
        return None
    if s.upper() == "M":
        return None
    if s.upper() == "T":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def _coerce_int(val: Optional[str]) -> Optional[int]:
    f = _coerce_float(val)
    return int(f) if f is not None else None


class Command(BaseCommand):
    help = "Load weather stations and daily observations from Environment Canada CSV files."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dir",
            dest="directory",
            default=str(Path(settings.BASE_DIR) / "Data"),
            help="Directory containing *_P1D.csv files (default: BASE_DIR/Data)",
        )

    def handle(self, *args, **options):
        directory = Path(options["directory"]).resolve()
        if not directory.exists():
            self.stderr.write(self.style.ERROR(f"Directory not found: {directory}"))
            return 1

        csv_files = sorted(directory.glob("en_climate_daily_*_P1D.csv"))
        if not csv_files:
            self.stderr.write(self.style.WARNING("No weather CSV files found matching pattern en_climate_daily_*_P1D.csv"))
            return 0

        created_stations = 0
        updated_stations = 0
        created_obs = 0
        updated_obs = 0

        with transaction.atomic():
            for path in csv_files:
                created_st, updated_st, c_obs, u_obs = self._load_file(path)
                created_stations += created_st
                updated_stations += updated_st
                created_obs += c_obs
                updated_obs += u_obs

        self.stdout.write(
            self.style.SUCCESS(
                f"Stations created/updated: {created_stations}/{updated_stations}; Observations created/updated: {created_obs}/{updated_obs}"
            )
        )
        return 0

    def _load_file(self, path: Path) -> tuple[int, int, int, int]:
        created_st = 0
        updated_st = 0
        created_obs = 0
        updated_obs = 0

        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Station fields
                name = _get(row, ["Station Name"]) or "Unknown"
                climate_id = _get(row, ["Climate ID"]) or ""
                lon = _coerce_float(_get(row, ["Longitude (x)", "Longitude"]))
                lat = _coerce_float(_get(row, ["Latitude (y)", "Latitude"]))
                if not climate_id:
                    # Skip rows without climate id
                    continue
                # Upsert station, ensuring required lon/lat on create
                station = WeatherStation.objects.filter(climate_id=climate_id).first()
                if station is None:
                    if lon is None or lat is None:
                        # cannot create without coordinates; skip until a row provides them
                        continue
                    station = WeatherStation.objects.create(
                        climate_id=climate_id,
                        name=name,
                        longitude=lon,
                        latitude=lat,
                    )
                    created_st += 1
                else:
                    changed = False
                    if name and station.name != name:
                        station.name = name
                        changed = True
                    if lon is not None and station.longitude != lon:
                        station.longitude = lon
                        changed = True
                    if lat is not None and station.latitude != lat:
                        station.latitude = lat
                        changed = True
                    if changed:
                        station.save(update_fields=["name", "longitude", "latitude"])
                        updated_st += 1

                # Observation fields
                date_str = _get(row, ["Date/Time", "Date"])
                if not date_str:
                    continue
                # format: YYYY-MM-DD
                try:
                    from datetime import date as _date

                    parts = [int(p) for p in date_str.split("-")[:3]]
                    obs_date = _date(parts[0], parts[1], parts[2])
                except Exception:
                    # Skip bad date
                    continue

                t_max = _coerce_float(_get(row, ["Max Temp"]))
                t_min = _coerce_float(_get(row, ["Min Temp"]))
                t_mean = _coerce_float(_get(row, ["Mean Temp"]))
                rain = _coerce_float(_get(row, ["Total Rain"]))
                snow = _coerce_float(_get(row, ["Total Snow"]))
                precip = _coerce_float(_get(row, ["Total Precip"]))
                snow_grnd = _coerce_float(_get(row, ["Snow on Grnd"]))
                gust_dir = _coerce_int(_get(row, ["Dir of Max Gust"]))
                gust = _coerce_int(_get(row, ["Spd of Max Gust"]))

                # Derived
                weather_day: Optional[str]
                if snow is not None and snow > 0:
                    weather_day = WeatherDay.SNOWY
                elif precip is not None and precip >= 0.2:
                    weather_day = WeatherDay.WET
                elif (
                    precip is not None and precip == 0.0
                ) and (
                    snow is not None and snow == 0.0
                ):
                    weather_day = WeatherDay.DRY
                else:
                    weather_day = None

                freeze_day = None
                if t_min is not None:
                    freeze_day = bool(t_min < 0)

                defaults = {
                    "t_max_c": t_max,
                    "t_min_c": t_min,
                    "t_mean_c": t_mean,
                    "total_rain_mm": rain,
                    "total_snow_cm": snow,
                    "total_precip_mm": precip,
                    "snow_on_ground_cm": snow_grnd,
                    "gust_dir_10deg": gust_dir,
                    "gust_kmh": gust,
                    "weather_day": weather_day,
                    "freeze_day": freeze_day,
                }
                obj, created = WeatherObservation.objects.update_or_create(
                    station=station, date=obs_date, defaults=defaults
                )
                if created:
                    created_obs += 1
                else:
                    updated_obs += 1

        return created_st, updated_st, created_obs, updated_obs
