# Copyright(C) 2021 Horus View and Explore B.V.


import os
import sys
import csv
import logging
import itertools

sys.path.insert(0, "../")

from horus_db import Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, Size, Direction, \
    ComputationRequestBuilder, ComputationProvider
from horus_gis import PositionVector, Geographic

import util


# Comand line input handling
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)
util.add_size_argument(parser, (1024, 1024))
parser.add_argument("-hf", "--horizontal-fov", type=float, default=(90),
                    help="horizontal field of view size in degrees")
parser.add_argument("-o", "--overlap", type=float, default=(20),
                    help="horizontal overlap in degrees")
parser.add_argument("--path", type=str, help="path to output location")
parser.add_argument("--limit", metavar=("NUMBER"), type=int,
                    help="maximum number of frames")
parser.add_argument("-r", "--recording", metavar="ID",
                    nargs='*', type=int, help="recording id")


args = parser.parse_args()

# This example shows how to request a spherical image
output_path = args.path

if output_path is None:
    logging.error(f"Specify an output path using '--path'")
    exit()

# Utility


def get_position_vector(frame, size, direction, fov):
    request_builder = ComputationRequestBuilder(frame.recordingid, frame.uuid)
    request = client.fetch(request_builder.build(size, direction, fov, 0, 0))
    result = computation_provider.fetch(request)
    return PositionVector(*result.values())


connection = util.get_connection(args)
client = util.get_client(args)

frames = Frames(connection)
image_provider = ImageProvider()
computation_provider = ComputationProvider()

# Output parameters
size = Size(args.size[0], args.size[1])  # defaults to (1024px, 1024px)
horizontal_fov = args.horizontal_fov  # defaults to 90 deg
overlap = args.overlap  # 20deg
recording_id = tuple(args.recording) if args.recording != None else None

displacement = horizontal_fov - overlap

directions = {
    "right": Direction(yaw=displacement, pitch=0),
    "center": Direction(yaw=0, pitch=0),
    "left": Direction(yaw=-displacement, pitch=0),
}

csv_header = [
    "File",
    "Index",
    "Altitude",
    "Azimuth",
    "Latitude",
    "Longitude",
    "Pitch",
    "Roll",
    "Stamp"
]


# Open output csv file
with open(os.path.join(output_path, 'output.csv'), 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(csv_header)

    # Get frames
    results = Frame.query(frames, recordingid=recording_id, order_by="index",)
    if args.limit:
        results = itertools.islice(results, args.limit)
    for frame in results:
        if frame is None:
            print("No frames!")
            exit()

        print(frame)

        # Get the image
        # Set parameters
        request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
        for direction_id, direction in directions.items():
            request = client.fetch(request_builder.build_spherical(
                size, direction, horizontal_fov))
            result = image_provider.fetch(request)

            # Save the file
            filename = "{}_{}.jpg".format(frame.index, direction_id)

            with open(os.path.join(output_path, filename), 'wb') as image_file:
                image_file.write(result.image.getvalue())
                result.image.close()

            # Compute accurate position with lever arm.
            position = get_position_vector(
                frame, size, direction, horizontal_fov)

            writer.writerow([
                filename,
                frame.index,
                position.alt,
                frame.azimuth,
                position.lat,
                position.lon,
                frame.pitch,
                frame.roll,
                frame.stamp.isoformat()])
