"""Horus Gis

Utilities for GIS ENU to and from Geodetic conversions.
"""
# Copyright(C) 2019, 2020 Horus View and Explore B.V.

import numpy
import pymap3d
import math
import argparse
from typing import NamedTuple
from ast import literal_eval
from scipy.spatial.transform import Rotation

def angle_between(v1, v2, up=numpy.array((0, 0, 1))):
    """ Returns the angle in radians between vectors 'v1' and 'v2'

    The angle is oriented according to the up vector.
    """

    angle = numpy.arccos(numpy.dot(v1, v2) /
                         (numpy.linalg.norm(v1) * numpy.linalg.norm(v2)))
    if numpy.dot(numpy.cross(v1, v2), up) < 0:
        return -angle
    return angle


def xyz_to_yxz(p):
    """Swaps x and y iterating over a 3D vector"""
    yield p[1]
    yield p[0]
    yield p[2]


def geoPointParser(string):
    try:
        value = literal_eval(f"({string})")
        value = tuple(map(lambda x: float(x), value))
        if len(value) == 3:
            return value
    except:
        pass
    raise argparse.ArgumentTypeError(
        "'{string}' is not a valid location")


class EnuModel:
    """East North Up spatial of reference

    Conversions bewteen ENU and Geodetic."""

    east = numpy.array((1, 0, 0))
    north = numpy.array((0, 1, 0))
    up = numpy.array((0, 0, 1))

    def __init__(self, geodeticPoint):
        self.geodeticPoint = geodeticPoint

    def to_enu(self, geodeticPoint):
        return numpy.array(pymap3d.geodetic2enu(
            *xyz_to_yxz(geodeticPoint), *xyz_to_yxz(self.geodeticPoint)))

    def to_geodetic(self, point):
        """
        ENU to Azimuth, Elevation, Range

        Parameters
        ----------

        point : collection
            ENU point (meters, meters, meters)

        Results
        -------
            WGS84 point (lon, lat, alt)
        """
        return numpy.array([x for x in xyz_to_yxz(
            pymap3d.enu2geodetic(*point, *xyz_to_yxz(self.geodeticPoint)))])

    def to_orientation(self, angle):
        r = Rotation.from_euler('z', angle, degrees=True)
        # should use altitude ?
        return r.apply(EnuModel.north)

    def get_heading(self, point):
        return math.degrees(angle_between(EnuModel.north, point))


class CameraModel(EnuModel):
    def __init__(self, origin, heading):
        super(CameraModel, self).__init__(origin)
        self.orientation = self.to_orientation(-heading)

    def look_at(self, location):
        return self.to_enu(location)

    def look_at_angle(self, location):
        enu_location = self.to_enu(location)
        return math.degrees(angle_between(self.orientation, enu_location))


class PositionVector(NamedTuple):
    lat: float
    lon: float
    alt: float
    yaw: float
    pitch: float

class Geographic:
    @staticmethod
    def __normalize(v):
        norm = numpy.linalg.norm(v)
        if norm == 0: 
            return v
        return v / norm

    @staticmethod
    def __get_line(lat, lon, alt, bearing, pitch):
        p = pymap3d.geodetic2ecef(lat, lon, alt)

        d = numpy.array([math.cos(math.radians(pitch)) * math.sin(math.radians(bearing)),
                        math.cos(math.radians(pitch)) * math.cos(math.radians(bearing)),
                        math.sin(math.radians(pitch))])

        m = numpy.array([[-1 * math.sin(math.radians(lon)), 
                        -1 * math.sin(math.radians(lat)) * math.cos(math.radians(lon)), 
                        math.cos(math.radians(lat)) * math.cos(math.radians(lon))], 
                        [math.cos(math.radians(lon)), 
                        -1 * math.sin(math.radians(lat)) * math.sin(math.radians(lon)), 
                        math.cos(math.radians(lat)) * math.sin(math.radians(lon))],
                        [0, math.cos(math.radians(lat)), math.sin(math.radians(lat))]])

        d = m.dot(d)
        d = Geographic.__normalize(d)

        return p, d

    @staticmethod
    def __get_point(lines):
        m = numpy.zeros([3,3])
        left = numpy.zeros([3,3])
        right = numpy.zeros([3])

        for origin, direction in lines:
            m = numpy.identity(3) - \
                numpy.column_stack([numpy.array([direction * direction[0]]).T, 
                numpy.array([direction * direction[1]]).T, 
                numpy.array([direction * direction[2]]).T])
            left += m
            right += m.dot(origin)

        output = numpy.linalg.inv(left).dot(right)

        return numpy.array(pymap3d.ecef2geodetic(*output))
    
    @staticmethod
    def triangulate(pos_vectors):
        """ Triangulate position based on at least 3 position vectors """
        lines = []
        for i in pos_vectors:
            lines.append(Geographic.__get_line(*i))
        return Geographic.__get_point(lines)
