from horus_camera import SphericalCamera
from horus_gis import GeographicLocation
from horus_db import Recordings, Frames, Frame
from horus_spatialite import Spatialite, FrameMatchedIterator
from pyproj import Geod
from horus_geometries import Geometry_proj
import geopandas as gpd
import pandas as pd
import sys
from os import path
import traceback

from . import util

parser = util.create_argument_parser()

parser.add_argument("--sqlite-db", type=str,
                    help="the geosuite_database name")

parser.add_argument("--sqlite-framenr", type=str,
                    help="the field specifying the framenr")

parser.add_argument("--sqlite-recording", type=str,
                    help="the field specifying the recordingname")

parser.add_argument("--sqlite-geometry", type=str,
                    help="the field specifying an alternative geometry blob")

# Not tested
parser.add_argument("--recordings-on-disk", type=str,
                    help="Optionally provide a recording folder")

# Not tested
parser.add_argument("--recording-id", type=int,
                    help="Optionally provide a the static recording id.")


util.add_database_arguments(parser)
util.add_server_arguments(parser)


args = parser.parse_args()
client = util.get_client(args)
connection = util.get_connection(args)
recordings = Recordings(connection)

if args.sqlite_db is None:
    print("A sqlite database should be provided")
    exit()

# sqlite_frame_idx_field = "Frame_numb"
output_database = None
geod = Geod(ellps="WGS84")


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


def add_to_output(frame, geometry, filename, nr, matched_frame):
    """
       Add the curreont geometry and attributes to the output database
    """
    global output_database

    record = {}
    record["geometry"] = gpd.GeoSeries(geometry)
    record["snapshot"] = filename
    record["sub_id"] = nr
    record["frame_index"] = frame.index
    record["recording_id"] = frame.recordingid

    for k, v in matched_frame.metadata.items():
        record[k] = v

    gdf = gpd.GeoDataFrame(record)

    if output_database is None:
        output_database = gdf
    else:
        output_database = pd.concat([output_database, gdf])


def try_find_frame_within(geometry, mf: FrameMatchedIterator.MatchedFrame, distance_min, distance_max):
    """
       Try to find a frame from the same recording that is within (distance_min,distance_max)
    """
    frames = Frames(connection)
    cursor = frames.query(within=(*geometry.centroid.coords, distance_max),
                          recordingid=mf.recording.id,
                          distance=(*geometry.centroid.coords, "> %s",
                                    distance_min), limit=1)

    if (cursor != None):
        return Frame(cursor)
    return None


def look_at_point(point, mf: FrameMatchedIterator.MatchedFrame, side):
    """
        Transforms a 'Point' geometry into a square of sides 'side'x'side'
        in meters
    """
    gp = Geometry_proj()
    square = gp.point_to_square(point, 0.5)
    return [Look_at(mf.frame, square)]


def look_at_linestring(linestring, mf: FrameMatchedIterator.MatchedFrame, max_length, distance_min, distance_max, offset):
    """
        Transforms a 'LineString' geometry into sub LineStrings of maximum length
        of 'max_length' in meters.
    """
    gp = Geometry_proj()
    geom_length = geod.geometry_length(linestring)
    
    if geod.geometry_length(linestring) > max_length:
        
        linestrings = gp.split_linestring(linestring,max_length)
                
        look_at_all_sub_string = []
        for w in linestrings:

            frame = try_find_frame_within(w, mf, distance_min, distance_max)

            if not frame is None:
                mf.frame = frame

            look_at_all_sub_string.append(look_at_linestring(
                w, mf, max_length, distance_min, distance_max, offset)[0])

        return look_at_all_sub_string

    return [Look_at(mf.frame,gp.buffer(linestring, offset))]    


def look_at_polygon(polygon, mf: FrameMatchedIterator.MatchedFrame):
    """
        Transforms a 'Polygon' geometry into a collection of Polygons..
    """
    return [Look_at(mf.frame, polygon)]


def take_shaphost(db, mf: FrameMatchedIterator.MatchedFrame, geod):

    geometries = []
    geo = db.get_geometry(mf.spatialite_cursor)[db.geometry_field_name]
    
    if geo.type.startswith('Multi'):
        for g in geo.geoms:
            geometries.append(g)
    else:
        geometries.append(geo)

    width = 800
    look_at_all: [Look_at] = []

    for geom in geometries:
        if geom.type == "Polygon":
            look_at_all = [*look_at_all, *look_at_polygon(geom, mf)]
        elif geom.type == "LineString":
            look_at_all = [*look_at_all, *look_at_linestring(geom, mf, 5, 5, 20, 0.1)]       
        elif geom.type == "Point":
            look_at_all = [*look_at_all, *look_at_point(geom,mf, 0.3) ]       
        else:
            print("Not supported", geom.type)

    nr_shaphosts = len(look_at_all)

    for x, look_at in enumerate(look_at_all):
        look_at_geometry = look_at.to_geographic_loc_list()

        sp_camera.set_frame(mf.recording, look_at.frame)
        size = sp_camera.look_at_all(look_at_geometry, width)
        spherical_image = sp_camera.crop_to_geometry(sp_camera.acquire(size), look_at_geometry)

        # Write output
        db_id = mf.spatialite_cursor[db.field_info_map["rowid"].idx]
        print("Snapshot:", "db id", db_id, "nr",
              x+1, "/", nr_shaphosts, geom.type)

        filename = 'output/snapshot_db_id:' + \
            str(db_id) + '_' + str(x+1) + '_' + geom.type + '.jpeg'

        add_to_output(look_at.frame, look_at.geometry, filename, x+1, mf)

        with open(filename, 'wb') as image_file:
            image_file.write(spherical_image.get_image().getvalue())
            spherical_image.get_image().close()


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

sp_camera = SphericalCamera()
sp_camera.set_network_client(client)

fmi: FrameMatchedIterator = db.get_matched_frames_iterator()

if (not args.recording_id is None):
    fmi.set_static_recording_by_id(args.recording_id)


mf: FrameMatchedIterator.MatchedFrame = next(fmi, None)

while mf != None:

    try:
        if mf.oke():
            take_shaphost(db, mf, geod)
        else:
            print("\nIncomplete match")
            print(mf.dump())
    except Exception as e:
        print("Exception", e)
        print("Properties: ", mf.properties)
        print("Metadata: ", mf.metadata)
        pass
    mf = next(fmi, None)

db.close()

if not output_database is None:
    output_database.to_file("output/snapshots.geojson", driver='GeoJSON')
