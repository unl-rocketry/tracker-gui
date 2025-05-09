## See `main.py` for more information

import math
from typing import Optional, Self
from pygeomag import GeoMag
import datetime

EARTH_RADIUS_METERS = 6_378_137


class GPSPoint:
    """A single point on the Earth, including altitude."""

    def __init__(
        self,
        latitude: float = 0.0,
        longitude: float = 0.0,
        altitude: Optional[float] = None,
    ):
        self.lat = latitude
        self.lon = longitude
        self.alt = altitude

    def lat_rad(self) -> float:
        """Returns the latitude component in radians."""
        return math.radians(self.lat)

    def lon_rad(self) -> float:
        """Returns the longitude component in radians."""
        return math.radians(self.lon)

    def distance_to(self, other: Self) -> float:
        """Great-circle ground-only distance in meters between two GPS Points."""

        delta_lat_rad = other.lat_rad() - self.lat_rad()
        delta_lon_rad = other.lon_rad() - self.lon_rad()

        a = (
            math.sin(delta_lat_rad / 2) ** 2
            + math.cos(self.lat_rad())
            * math.cos(other.lat_rad())
            * math.sin(delta_lon_rad / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return EARTH_RADIUS_METERS * c

    def altitude_to(self, other: Self) -> Optional[float]:
        if self.alt is not None and other.alt is not None:
            return other.alt - self.alt
        else:
            return None

    def bearing_to(self, other: Self, positive: bool = False) -> float:
        """Find the absolute bearing (azimuth) to another point."""

        # Calculate the bearing
        bearing = math.atan2(
            math.sin(other.lon_rad() - self.lon_rad()) * math.cos(other.lat_rad()),
            math.cos(self.lat_rad()) * math.sin(other.lat_rad())
            - math.sin(self.lat_rad())
            * math.cos(other.lat_rad())
            * math.cos(other.lon_rad() - self.lon_rad()),
        )

        # Convert the bearing to degrees
        bearing = math.degrees(bearing)

        # Ensure the value is from -180→180 instead of 0→360
        if positive:
            bearing = (bearing + 360) % 360

        return bearing

    def bearing_mag_corrected_to(self, other: Self, positive: bool = False) -> float:
        """Find the absolute bearing (azimuth) to another point, to be used with a device basing its heading on magnetic north"""

        bearing = self.bearing_to(other, False)

        current_datetime = datetime.datetime.now()
        fractional_year = (
            float(
                (
                    current_datetime.date() - datetime.date(current_datetime.year, 1, 1)
                ).days
            )
            / 365.2425
        ) + current_datetime.year

        geo_mag = GeoMag(base_year=datetime.datetime.now(), high_resolution=True)
        result = geo_mag.calculate(
            glat=self.lat, glon=self.lon, alt=self.alt or 0.0, time=fractional_year
        )

        bearing = bearing + result.d

        if positive:
            bearing = (bearing + 360) % 360

        return bearing

    def elevation_to(self, other: Self) -> float:
        """Find the elevation above the horizon (altitude) to another point."""

        # Distance in meters, and horizontal angle (azimuth)
        horizontal_distance = self.distance_to(other)

        # In this case things would divide by zero, so bail
        if horizontal_distance == 0:
            return 0.0

        # Altitude difference in meters
        altitude_delta = self.altitude_to(other)

        if altitude_delta is None:
            raise Exception("Cannot calculate elevation with no altitude")

        # Vertical angle (altitude)
        vertical_angle = math.degrees(math.atan(altitude_delta / horizontal_distance))

        return vertical_angle


def m_to_ft(meters: float) -> float:
    """Helper function to convert meters to feet, mainly for display"""
    return meters / 0.3048


def crc8(data: bytes) -> int:
    """Calculate the 8-bit CRC for some arbitrary data."""
    crc = 0x00

    for element in data:
        crc ^= element
        for _ in range(8):
            if crc & 0x80 > 0:
                crc = (crc << 1) ^ 0xD5
            else:
                crc <<= 1

            # Truncate the CRC value to 8 bits
            crc &= 0xFF

    return crc
