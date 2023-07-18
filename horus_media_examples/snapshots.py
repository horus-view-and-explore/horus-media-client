from horus_camera import SphericalCamera
from horus_gis import GeographicLocation
from horus_db import Frames, Frame
from horus_spatialite import Spatialite, FrameMatchedIterator
from pyproj import Geod
from horus_geometries import Geometry_proj
import geopandas as gpd
import pandas as pd
import sys
from os import path
import traceback
import math

from . import util


parser = util.create_argument_parser()
parser.add_argument("--sqlite-db", type=str, help="the geosuite_database name")
parser.add_argument(
    "--sqlite-framenr", type=str, help="the field specifying the framenr"
)
parser.add_argument(
    "--sqlite-recording", type=str, help="the field specifying the recordingname"
)
parser.add_argument(
    "--sqlite-geometry",
    type=str,
    help="the field specifying an alternative geometry blob",
)
# Not tested
parser.add_argument(
    "--recordings-on-disk", type=str, help="Optionally provide a recording folder"
)
# Not tested
parser.add_argument(
    "--recording-id", type=int, help="Optionally provide a the static recording id."
)
util.add_database_arguments(parser)
util.add_server_arguments(parser)

args = parser.parse_args()
if args.sqlite_db is None:
    print("A sqlite database should be provided")
    exit()

connection = util.get_connection(args)

sp_camera = SphericalCamera()
sp_camera.set_network_client(util.get_client(args))

# sqlite_frame_idx_field = "Frame_numb"
output_database = None
geod = Geod(ellps="WGS84")


def compute_heading(long_0, lat_0, long_1, lat_1):
    long_0 = math.radians(long_0)
    lat_0 = math.radians(lat_0)
    long_1 = math.radians(long_1)
    lat_1 = math.radians(lat_1)
    heading = math.atan2(
        math.sin(long_1 - long_0) * math.cos(lat_1),
        math.cos(lat_0) * math.sin(lat_1)
        - math.sin(lat_0) * math.cos(lat_1) * math.cos(long_1 - long_0),
    )
    heading = math.degrees(heading)
    heading = (heading + 360) % 360
    return heading


def compute_rel_geom_heading(frame, geom_centroid):
    geom_heading = compute_heading(frame.longitude, frame.latitude, *geom_centroid)
    return (360 + geom_heading - frame.heading) % 360


class GeomHeadingFrameSelector:
    """
    Select frame based on the direction of the geometry.
    """

    def __init__(self, rel_geom_heading_min, rel_geom_heading_max):
        self.rel_geom_heading_min = rel_geom_heading_min
        self.rel_geom_heading_max = rel_geom_heading_max

    def __call__(self, geom, cursor):
        """
        Return the first frame for which the relative geometry heading is within range.
        Return the first frame if no such frame is found.
        """
        geom_centroid = geom.centroid.coords[0]
        first_frame = Frame(cursor)
        frame = first_frame
        while frame is not None:
            rel_geom_heading = compute_rel_geom_heading(frame, geom_centroid)
            if self.rel_geom_heading_min < rel_geom_heading < self.rel_geom_heading_max:
                return frame
            frame = Frame(cursor)
        return first_frame


DISTANCE_MIN = 10
DISTANCE_MAX = 20
FRAME_LIMIT = 10
GEOM_HEADING_FRAME_SELECTOR = GeomHeadingFrameSelector(90, 270)


class Look_at:
    """
    Simple class that describes what geometry the virtual camera
    should look at and from which frame.
    """

    frame: Frame = None
    geometry = None

    def __init__(self, frame, geometry):
        self.frame = frame
        self.geometry = geometry
        self.gp = Geometry_proj()

    def to_geographic_loc_list(self):
        return self.gp.to_geographic(self.geometry)


def add_to_output(db, frame, geometry, filename, error, sub_id, matched_frame):
    """
    Add the current geometry and attributes to the output database
    """
    global output_database

    record = {}
    record["geometry"] = gpd.GeoSeries(geometry)
    record["snapshot"] = filename
    record["snapshot_error"] = error
    record["sub_id"] = sub_id
    record["frame_index"] = frame.index if frame else None
    record["recording_id"] = frame.recordingid if frame else None
    record["distance"] = (
        geod.line_length(*zip(*[frame.get_location()[:2], geometry.centroid.coords[0]]))
        if frame
        else None
    )

    for k, v in matched_frame.metadata.items():
        record[k] = v

    gdf = gpd.GeoDataFrame(record)

    if output_database is None:
        output_database = gdf
    else:
        output_database = pd.concat([output_database, gdf])


def try_find_frame(geometry, mf: FrameMatchedIterator.MatchedFrame):
    """
    Try to find a frame from the same recording that is within (DISTANCE_MIN, DISTANCE_MAX)
    """
    if mf.recording == None:
        return None
    else:
        frames = Frames(connection)
        cursor = frames.query(
            within=(*geometry.centroid.coords, DISTANCE_MAX),
            recordingid=mf.recording.id,
            distance=(*geometry.centroid.coords, "> %s", DISTANCE_MIN),
            limit=FRAME_LIMIT,
        )
        return GEOM_HEADING_FRAME_SELECTOR(geometry, cursor)


def look_at_point(point, mf: FrameMatchedIterator.MatchedFrame, side):
    """
    Transform a 'Point' geometry into a square of sides 'side'x'side' in meters.
    """
    assert point.geom_type == "Point"
    gp = Geometry_proj()
    square = gp.point_to_square(point, side)
    return [Look_at(mf.frame, square)]


def look_at_linestring(
    linestring,
    mf: FrameMatchedIterator.MatchedFrame,
    max_length,
    offset,
):
    """
    Transform a 'LineString' geometry into sub LineStrings of maximum length of 'max_length' in meters.
    """
    assert linestring.geom_type == "LineString"
    gp = Geometry_proj()

    if geod.geometry_length(linestring) > max_length:
        linestrings = gp.split_linestring(linestring, max_length)

        look_at_all_sub_string = []
        for w in linestrings:
            frame = try_find_frame(w, mf)

            if not frame is None:
                mf.frame = frame

            look_at_all_sub_string.append(
                look_at_linestring(w, mf, max_length, offset)[0]
            )

        return look_at_all_sub_string

    return [Look_at(mf.frame, gp.buffer(linestring, offset))]


def look_at_polygon(polygon, mf: FrameMatchedIterator.MatchedFrame):
    """
    Transform a 'Polygon' geometry into a collection of Polygons.
    """
    assert polygon.geom_type == "Polygon"
    return [Look_at(mf.frame, polygon)]


def take_snapshot(db, mf: FrameMatchedIterator.MatchedFrame):
    geometry = db.get_geometry(mf.spatialite_cursor)[db.geometry_field_name]

    geometries = []
    if geometry.geom_type.startswith("Multi"):
        for geom in geometry.geoms:
            geometries.append(geom)
    else:
        geometries.append(geometry)

    width = 800
    look_at_all: [Look_at] = []
    for geom in geometries:
        if geom.geom_type == "Polygon":
            look_at_all = [*look_at_all, *look_at_polygon(geom, mf)]
        elif geom.geom_type == "LineString":
            look_at_all = [*look_at_all, *look_at_linestring(geom, mf, 5, 0.1)]
        elif geom.geom_type == "Point":
            look_at_all = [*look_at_all, *look_at_point(geom, mf, 0.5)]
        else:
            print("Not supported", geom.geom_type)

    nr_snapshots = len(look_at_all)

    for x, look_at in enumerate(look_at_all):
        look_at_geometry = look_at.to_geographic_loc_list()
        db_id = mf.spatialite_cursor[db.field_info_map["rowid"].idx]
        print(
            "Snapshot:",
            "db id",
            db_id,
            "nr",
            x + 1,
            "/",
            nr_snapshots,
            geometry.geom_type,
        )
        filename = (
            "output/snapshot_db_id:"
            + str(db_id)
            + "_"
            + str(x + 1)
            + "_"
            + geometry.geom_type
            + ".jpeg"
        )
        error = ""
        if mf.recording != None and look_at.frame != None:
            try:
                sp_camera.set_frame(mf.recording, look_at.frame)
                size = sp_camera.look_at_all(look_at_geometry, width)
                spherical_image = sp_camera.crop_to_geometry(
                    sp_camera.acquire(size), look_at_geometry
                )
                with open(filename, "wb") as image_file:
                    image_file.write(spherical_image.get_image().getvalue())
                    spherical_image.get_image().close()
            except Exception as e:
                error = str(e)
                print("Exception:", error)
                print("Properties:", mf.properties)
                print("Metadata:", mf.metadata)
        else:
            error = f"No frame found within {DISTANCE_MIN}-{DISTANCE_MAX} meters from centroid of geometry."
            print("Error:", error)
            print("Spatialite cursor:", mf.spatialite_cursor)
        add_to_output(db, look_at.frame, look_at.geometry, filename, error, x + 1, mf)


db = Spatialite(args.sqlite_db)
if not args.recordings_on_disk is None:
    db.set_recordings_on_disk_root_folder(args.recordings_on_disk)
if not args.sqlite_recording is None:
    db.set_recording_field(args.sqlite_recording)
if not args.sqlite_framenr is None:
    db.set_frame_index_field(args.sqlite_framenr)
if not args.sqlite_geometry is None:
    db.set_geometry_field_name(args.sqlite_geometry)
    db.blob_contains_geometry(args.sqlite_geometry)
db.set_remote_db_connection(connection)
db.open()
db.resolve()
db.show_info()

fmi: FrameMatchedIterator = db.get_matched_frames_iterator()
fmi.set_distance_limits(DISTANCE_MIN, DISTANCE_MAX)
fmi.set_frame_limit(FRAME_LIMIT)
fmi.set_frame_selector(GEOM_HEADING_FRAME_SELECTOR)
if not args.recording_id is None:
    fmi.set_static_recording_by_id(args.recording_id)

mf: FrameMatchedIterator.MatchedFrame = next(fmi, None)

while mf != None:
    assert mf.spatialite_cursor != None
    try:
        take_snapshot(db, mf)
    except Exception as e:
        print("Exception:", e)
        print("Properties:", mf.properties)
        print("Metadata:", mf.metadata)
    mf = next(fmi, None)

db.close()

if not output_database is None:
    output_database.to_file("output/snapshots.geojson", driver="GeoJSON")
