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
from enum import Enum

def angle_between(v1, v2, up=numpy.array((0, 0, 1))):
    """ Returns the angle in radians between vectors 'v1' and 'v2'

    The angle is oriented according to the up vector.
    """

    angle = numpy.arccos(numpy.clip(numpy.dot(v1 / numpy.linalg.norm(v1), \
                v2 / numpy.linalg.norm(v2)), -1.0, 1.0))
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

    Conversions between ENU and Geodetic."""

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

    def rotate(self, point, angle):
        r = Rotation.from_euler('z', angle, degrees=True)
        return r.apply(point)

    def to_orientation(self, angle):
        # should use altitude ?
        return self.rotate(EnuModel.north, angle)

    def angle_between(self, v1, v2):
        return math.degrees(angle_between(v1, v2, [0, 0, 0]))

    def get_heading(self, point):
        return math.degrees(angle_between(EnuModel.north, point))
    
    def get_direction(self, point):
        yaw = (math.degrees(math.atan2(*point[:2])) + 360) % 360
        r = Rotation.from_euler('z', yaw, degrees=True)
        pitch = 90 - math.degrees(math.atan2(*(r.apply(point)[1:3])))
        return [yaw, pitch]


class CameraModel(EnuModel):
    def __init__(self, origin, heading):
        super(CameraModel, self).__init__(origin)
        self.orientation = self.to_orientation(-heading)

    @staticmethod
    def with_leverarms(origin, heading, leverarms):
        enu = EnuModel(origin)
        r = Rotation.from_euler('z', -heading + 90.0, degrees=True)
        return CameraModel(enu.to_geodetic(r.apply(leverarms)), heading)

    def look_at(self, location):
        return self.get_direction(self.to_enu(location))

    def look_at_angle(self, location):
        enu_location = self.to_enu(location)
        return math.degrees(angle_between(self.orientation, enu_location))


class GeographicLocation():
    """GeographicLocation longitude,latitude,altitude

    Geographic location refers to a position on the Earth. 
    Your absolute geographic location is defined by two coordinates,
    longitude and latitude. In the case of imagery, the altitude is added/required
    to be able to georeference pixels from this imagery.

    The reference system is that in which the recording has been stored in the database,
    which is usually EPSG Projection 4326 - WGS 84. 
    """
    lat: float
    lon: float
    alt: float

    def __init__(self, lon: float, lat: float, alt: float):
        self.lon = lon
        self.lat = lat
        self.alt = alt

    @staticmethod
    def from_tuple(tuple_lon_lat_alt):
        return GeographicLocation(
            tuple_lon_lat_alt[0],
            tuple_lon_lat_alt[1],
            tuple_lon_lat_alt[2])


class RelativeLocation():
    """RelativeLocation, east, north, up

        The relative location in meters using the ENU coordinate system.
    """
    east: float
    north: float
    up: float

    def __init__(self, east: float, north: float, up: float):
        self.east = east
        self.north = north
        self.up = up

    def location(self):
        return [self.east, self.north, self.up]

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



class SchemaProvider:
    ### Provides database schemas ###
    class Geometry:
        class Type(Enum):
            POINT_2D = 1
            POINT_3D = 2
        ### placeholder geometry class ###
        type:Type
        def __init__(self,type:Type):
            self.type = type

        def __repr__(self):
            if self.type == self.Type.POINT_2D:
                return 'Point'
            if self.type == self.Type.POINT_3D:
                return '3D Point'
                
    class AutoIncrement:
        def __init__(self):
            pass

    class Field:
        name:str
        description:str
        type

        def __init__(self, name:str, description,type):
            self.name = name
            self.description = description
            self.type = type

        def __repr__(self):
            cls = type(self)
            return f"{cls.__name__}({self.name}, {getattr(self.type, '__name__', self.type)})"

    class Schema:
        fields=[]
        name:str

        def __init__(self, name: str):
            self.name = name

    @staticmethod
    def merge(schema_a, schema_b):
        schema = SchemaProvider.Schema(schema_a.name + " / " + schema_b.name)
        schema.fields = schema_a.fields + schema_b.fields
        return schema

    @staticmethod
    def single_measurement():
        schema = SchemaProvider.Schema("Single measurement schema")
        schema.fields =  [
            SchemaProvider.Field("geometry","Center of the detection projected on the surface.",
                                 SchemaProvider.Geometry(SchemaProvider.Geometry.Type.POINT_3D)),

            #Frame fields (viewpoint information)
            SchemaProvider.Field("rec_id", "The id of the recording.", int),
            SchemaProvider.Field("frame_idx", "The index of the frame.", int),
            SchemaProvider.Field("azimuth", "Heading/Azimuth (true north) of movement of the camera.", float),
            SchemaProvider.Field("usr_id", "An unique id for this record.", int),


            #SchemaProvider.Field("camera_geom", "Position of the camera.",
            #                     SchemaProvider.Geometry(SchemaProvider.Geometry.Type.POINT_3D)),
            #Camera fields (rendering parameters)
            SchemaProvider.Field("cam_lat", "The latitude of the camera.", float),
            SchemaProvider.Field("cam_lon", "The longitude of the camera.", float),
            SchemaProvider.Field("cam_alt", "The altitude of the camera.", float),
            SchemaProvider.Field("cam_fov", "The field of view of the spherical camera.",float),
            SchemaProvider.Field("cam_yaw", "The yaw of the spherical camera.",float),
            SchemaProvider.Field("cam_pitch", "The pitch of the spherical camera.",float),
            SchemaProvider.Field("cam_width", "The width of the spherical camera.",int),
            SchemaProvider.Field("cam_height", "The height of the spherical camera.",int),

            # Detection fields
            SchemaProvider.Field("dt_class", "The detection class/type ID.",int),
            SchemaProvider.Field("dt_name", "The detection name.",str),
            SchemaProvider.Field("dt_x", "The highest left pixel of the detection.",int),
            SchemaProvider.Field("dt_y", "The highest top pixel of the detection.",int),
            SchemaProvider.Field("dt_width", "The width of the detection.",int),
            SchemaProvider.Field("dt_height", "The height of the detection.",int),
            SchemaProvider.Field("dt_conf", "The confidence.",float),
            SchemaProvider.Field("dt_dist", "The surface distance in meters to the detection.",float),
            SchemaProvider.Field("dt_px_x", "The pixel x coordinate of the detection(could be centroid x).", int),
            SchemaProvider.Field("dt_px_y", "The pixel y coordinate of the detection (could be centroid y).", int),
            SchemaProvider.Field("dt_yaw", "The geographical yaw of the camera wrt the detection.", float),
            SchemaProvider.Field("dt_pitch", "The geographical pitch of the camera wrt the detection.", float),
            # 
            SchemaProvider.Field("surf_px_x","The pixel x coordinate of the surface(could be centroid x).",int),
            SchemaProvider.Field("surf_px_y","The pixel y coordinate of the surface (could be centroid y).",int),
            SchemaProvider.Field("surf_yaw","The geographical yaw of the camera wrt the surface.",float),
            SchemaProvider.Field("surf_pitch","The geographical pitch of the camera wrt the surface.",float)

        ]

        return schema

    @staticmethod
    def clustering():
        schema = SchemaProvider.Schema("Clustering schema")
        schema.fields = [
            SchemaProvider.Field("clstr_id", "The cluster id of the cluster.", int),
            SchemaProvider.Field("clstr_conf", "Clustering confidence.", float),
        ]

        return schema

    def geometry_3dpoint(self):
        schema = SchemaProvider.Schema("Geometry 3dPoint")
        schema.fields = [
            SchemaProvider.Field("geometry", "Basic 3D Point geometry.",
                                 SchemaProvider.Geometry(SchemaProvider.Geometry.Type.POINT_3D))
        ]

        return schema