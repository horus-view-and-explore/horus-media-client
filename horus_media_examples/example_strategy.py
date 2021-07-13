# Copyright(C) 2019, 2020 Horus View and Explore B.V.
"""Horus Media Server strategy example

Given a sign location
Assumption:
- the sign targeted face is oriented towards the driving direction
- We drive on the right-hand side of the road

Goal:
- narrow horizontal fov, centered on the sign
- the sign is visible head on within the grabbed images
- the images are within a max distance from the sign

In addition it exemplifies geo-query based acquisition of georeferenced orthographic projection images (geotiff)
"""

import psycopg2

from horus_gis import CameraModel, geoPointParser
from horus_db import Frames, Recordings, Recording, Frame, Iterator
from horus_media import Client, ImageRequestBuilder, ImageProvider, Grid, Scales, Point, Box, Mode, Size, Direction, Geometry

import argparse
import logging


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("target", nargs='+', metavar="lon,lat,alt",
                    type=geoPointParser, help="target GPS location in decimal degrees")
parser.add_argument("-r", "--recording", metavar="ID",
                    nargs='*', type=int, help="recording id")
parser.add_argument("-s", "--server",  metavar="URL", type=str, default="http://localhost:5050/web/",
                    help="Horus Media Server endpoint")
parser.add_argument("-f", "--fov",  metavar=("HORIZONTAL", "VERTICAL"), nargs=2, type=float, default=(25, 90),
                    help="field of view size in degrees")
parser.add_argument("-m", "--mode",  type=str, default="panoramic", choices=[x.name for x in list(Mode)],
                    help="rendering mode")
parser.add_argument("-si", "--size",  metavar=("WIDTH", "HEIGHT"), nargs=2, type=int, default=(1024, 1024),
                    help="size of the image (spherical), size of the back-buffer (orthographic)")
parser.add_argument("-ci", "--clipping",  metavar=("MIN", "MAX"), type=float, nargs=2, default=(15, 100),
                    help="clipping interval in degrees")
parser.add_argument("-d", "--distance", type=float, default=10,
                    help="maximum distance from the target in meters")
parser.add_argument("--path", type=str, help="output location")
parser.add_argument("--attempts", metavar=("NUMBER"), type=int, help="maximum number of attempts", default=100)

# geom
parser.add_argument("-gsc", "--geom-scale", type=int, default=400,
                    help="output scale in px/m (orthographic)")
parser.add_argument("-gw", "--geom-width", type=float, default=6,
                    help="geometry width (orthographic)")
parser.add_argument("-gh", "--geom-height", type=float, default=2,
                    help="geometry height (orthographic)")
parser.add_argument("-gd", "--geom-dist", type=float, default=4,
                    help="geometry distance (orthographic)")
parser.add_argument("-gs", "--geom-shift", type=float, default=0,
                    help="geometry shift (orthographic)")

# db
parser.add_argument("--db-name", type=str,
                    default="HorusWebMoviePlayer", help="the database name")
parser.add_argument("--db-user", type=str, default="postgres",
                    help="database user name used to authenticate")
parser.add_argument("--db-password", type=str,
                    help="database password used to authenticate")
parser.add_argument("--db-host", type=str, default="localhost",
                    help="database database host address")
parser.add_argument("--db-port", type=int, default=5432,
                    help="database connection port number")

args = parser.parse_args()

temp_path = args.path
recording_id = tuple(args.recording) if args.recording != None else None
distance = args.distance
horizontal_fov = args.fov[0]
vertical_fov = args.fov[1]
mode = args.mode
size = Size(args.size[0], args.size[1])
clipping_interval = tuple(args.clipping)
geometry = Geometry(args.geom_scale, args.geom_width, args.geom_height, args.geom_dist, args.geom_shift, None)

db_params = [("host", args.db_host),
             ("port", str(args.db_port)),
             ("dbname", args.db_name),
             ("user", args.db_user),
             ("password", args.db_password),
             ]
try:
    connection_string = " ".join(
        map("=".join, filter(lambda x: x[1] != None, db_params)))
    connection = psycopg2.connect(connection_string)
except psycopg2.OperationalError as exception:
    logging.error(f"{exception} Connecting to database")
    exit()
try:
    client = Client(args.server)
except OSError as exception:
    logging.error(f"{exception}. Connecting to server {args.server}")
    exit()

frames = Frames(connection)
grid = Grid()
image_provider = ImageProvider(grid)


def compute_angle(frame, sign_location):
    camera_model = CameraModel(frame.get_location(), frame.heading)
    return - camera_model.look_at_angle(sign_location)


for location in args.target:
    print(f"Looking for {location}")
    results = []
    cursor = frames.query(within=(location, distance),
                          recordingid=recording_id, limit=1)
    frame = Frame(cursor)
    if not frame:
        logging.warning(
            f"Location {location} not found within {distance} meters")
        continue

    if recording_id:
        assert frame.recordingid in recording_id
    angle = compute_angle(frame, location)
    attempts = args.attempts
    while True:
        if (clipping_interval[0] <= angle <= clipping_interval[1]):
            requestBuilder = ImageRequestBuilder(frame.recordingid, frame.uuid)

            filename = None

            if mode == Mode.panoramic.name:
                fov = Box.create(center=(angle, 0),
                                width=horizontal_fov, height=vertical_fov)
                sections = grid.filter(fov=fov)
                requests = client.fetch_all(requestBuilder.build(
                    mode, Scales.Px_1024, section) for section in sections)
                result = image_provider.combine(
                    requests, Scales.Px_1024.size, Scales.Px_1024.size)
                if temp_path:
                    filename = temp_path + \
                        "stitched_{}_{}.jpg".format(
                            frame.recordingid,  frame.index)
                results.append({
                    "frame": frame,
                    "angle": angle,
                    "pixel_coordinate": result.to_pixel_coordinates((angle, 0)),
                    "stitch": result})

            if mode == Mode.spherical.name:
                request = client.fetch(requestBuilder.build_spherical(
                    size, Direction(angle, 0), horizontal_fov))
                result = image_provider.fetch(request, size.width, size.height)
                if temp_path:
                    filename = temp_path + "spherical_{}_{}.jpg".format(
                        frame.recordingid,  frame.index)
                results.append({
                    "frame": frame,
                    "angle": angle,
                    "pixel_coordinate": Point(size.width / 2, 0),
                    "stitch": result})

            if mode == Mode.orthographic.name:
                request = client.fetch(requestBuilder.build_orthographic(size, geometry))
                                                            
                result = image_provider.fetch(request)
                if temp_path:
                    filename = temp_path + "orthographic_{}_{}.tif".format(
                        frame.recordingid,  frame.index)
                results.append({
                    "frame": frame,
                    "angle": angle,
                    "pixel_coordinate": Point(0, 0),
                    "stitch": result})

            if filename:
                with open(filename, 'wb') as f:
                    f.write(result.image.getvalue())
                result.image.close()
        elif len(results) > 0:
            break
        elif attempts < 0:
            print("Exceeded maximum number of attempts.")
            break
        else:
            attempts = attempts - 1


        next_index = frame.index
        frame = Frame(cursor)
        if not frame:
            # request in batches of 40 frames using decreasing indexes
            indexes = tuple(range(next_index - 40, next_index))
            cursor = frames.query(
                index=indexes, order_by="index DESC", recordingid=recording_id)
            frame = Frame(cursor)
            if not frame:
                break
        angle = compute_angle(frame, location)

    for result in results:
        print()
        print("frame:", result["frame"])
        print("angle:", str(round(result["angle"], 2)), "deg")
        if "pixel_coordinate" in result:
            print("x coordinate:", str(result["pixel_coordinate"].x), "px")
        # print("fov:", result["stitch"].fov)


connection.close()
