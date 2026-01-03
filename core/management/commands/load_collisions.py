from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
from pathlib import Path
from typing import Iterable, Optional, Dict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from core.models import Collision, WeatherStation, Quadrant


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


def nearest_station_id(lon: float, lat: float) -> Optional[int]:
    stations = list(WeatherStation.objects.all().values("id", "longitude", "latitude"))
    if not stations:
        return None
    best = None
    best_d = None
    for st in stations:
        s_lon = st.get("longitude")
        s_lat = st.get("latitude")
        if s_lon is None or s_lat is None:
            continue
        d = haversine_km(lon, lat, float(s_lon), float(s_lat))
        if best_d is None or d < best_d:
            best_d = d
            best = st["id"]
    return best


def parse_dt_local(s: str) -> Optional[datetime]:
    s = s.strip()
    if not s:
        return None
    # Expect format like: 2024/12/31 11:31:14 PM
    try:
        dt_naive = datetime.strptime(s, "%Y/%m/%d %I:%M:%S %p")
    except ValueError:
        # Fallback to common alternative
        try:
            dt_naive = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(getattr(settings, "TIME_ZONE", "America/Edmonton"))
        return timezone.make_aware(dt_naive, tz)
    except Exception:
        return timezone.make_aware(dt_naive)


def norm_quadrant(q: Optional[str]) -> str:
    if not q:
        return Quadrant.UNKNOWN
    q2 = q.strip().upper()
    if q2 in {Quadrant.NW, Quadrant.NE, Quadrant.SW, Quadrant.SE}:
        return q2
    return Quadrant.UNKNOWN


def in_bounds(lon: float, lat: float) -> bool:
    # Broad Calgary bounding box
    return (-114.5 <= lon <= -113.6) and (50.5 <= lat <= 51.3)


class Command(BaseCommand):
    help = "Load traffic collisions from Calgary CSV files and upsert into the database."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--csv",
            nargs="+",
            dest="csv_globs",
            help="One or more file globs for collision CSVs (e.g., Data/Traffic_Incidents_*.csv)",
        )
        parser.add_argument(
            "--dir",
            dest="directory",
            default=str(Path(settings.BASE_DIR) / "Data"),
            help="Directory to search for Traffic_Incidents_*.csv if --csv not provided",
        )

    def handle(self, *args, **options):
        csv_globs = options.get("csv_globs")
        directory = Path(options.get("directory")).resolve()

        files: list[Path] = []
        if csv_globs:
            for pattern in csv_globs:
                p = Path(pattern)
                if p.exists():
                    files.append(p)
                else:
                    # relative glob pattern
                    files.extend(Path().glob(str(pattern)))
        else:
            files = sorted(directory.glob("Traffic_Incidents_*.csv"))

        files = [p.resolve() for p in files if p.exists()]
        if not files:
            self.stderr.write(self.style.WARNING("No collision CSV files found."))
            return 0

        created = 0
        updated = 0
        skipped = 0
        # light diagnostics for skip reasons
        skip_reasons = {
            "no_id": 0,
            "invalid_coords": 0,
            "out_of_bounds": 0,
            "bad_start_dt": 0,
            "exception": 0,
        }

        with transaction.atomic():
            for path in files:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        try:
                            coll_id = row.get("id") or row.get("Id") or row.get("ID")
                            if not coll_id:
                                skipped += 1
                                skip_reasons["no_id"] += 1
                                continue

                            lon = float(row.get("Longitude", "") or "nan")
                            lat = float(row.get("Latitude", "") or "nan")
                            if not (lon == lon and lat == lat):  # NaN check
                                skipped += 1
                                skip_reasons["invalid_coords"] += 1
                                continue
                            if not in_bounds(lon, lat):
                                skipped += 1
                                skip_reasons["out_of_bounds"] += 1
                                continue

                            occ = parse_dt_local(row.get("START_DT", "") or "")
                            if not occ:
                                skipped += 1
                                skip_reasons["bad_start_dt"] += 1
                                continue
                            mod = parse_dt_local(row.get("MODIFIED_DT", "") or "")

                            desc = (row.get("DESCRIPTION") or "").strip()
                            loc_text = (row.get("INCIDENT INFO") or "").strip()
                            count = row.get("Count")
                            try:
                                count_val = int(count) if count and count.strip() else 1
                            except Exception:
                                count_val = 1

                            q = norm_quadrant(row.get("QUADRANT"))

                            # Derived fields
                            local_date = occ.date()
                            hour = occ.hour
                            weekday = occ.weekday()
                            month = occ.month
                            intersection_key = f"{round(lat, 4)}:{round(lon, 4)}"

                            st_id = nearest_station_id(lon, lat)

                            defaults = {
                                "occurred_at": occ,
                                "modified_at": mod,
                                "date": local_date,
                                "hour": hour,
                                "weekday": weekday,
                                "month": month,
                                "quadrant": q,
                                "longitude": lon,
                                "latitude": lat,
                                "count": count_val,
                                "description": desc,
                                "location_text": loc_text,
                                "intersection_key": intersection_key,
                                "nearest_station_id": st_id,
                            }

                            obj, was_created = Collision.objects.update_or_create(
                                collision_id=coll_id, defaults=defaults
                            )
                            if was_created:
                                created += 1
                            else:
                                updated += 1
                        except Exception:
                            skipped += 1
                            skip_reasons["exception"] += 1
                            continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Collisions upserted: created={created}, updated={updated}, skipped={skipped}"
            )
        )
        # Print a brief breakdown of skip reasons (stdout so it shows in CI logs)
        try:
            parts = ", ".join(f"{k}={v}" for k, v in skip_reasons.items() if v)
            if parts:
                self.stdout.write(self.style.NOTICE(f"Skip breakdown: {parts}"))
        except Exception:
            pass
        return 0
