# Copyright(C) 2021 Horus View and Explore B.V.


import os
import sys
import logging
import itertools

sys.path.insert(0, "../")

from horus_db import Frames, Frame
from horus_media import ImageRequestBuilder, ImageProvider, Size, ComputationProvider

import util


# Comand line input handling
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)
util.add_size_argument(parser, (4096, 2048))
util.add_geometry_arguments(parser)

parser.add_argument("--path", type=str, help="path to output location")
parser.add_argument("--limit", metavar=("NUMBER"), type=int,
                    help="maximum number of frames")
parser.add_argument("-r", "--recording", metavar="ID",
                    nargs='*', type=int, help="recording id")

args = parser.parse_args()

# This example shows how to request orthographic images
output_path = args.path

if output_path is None:
    logging.error(f"Specify an output path using '--path'")
    exit()


connection = util.get_connection(args)
client = util.get_client(args)

frames = Frames(connection)
image_provider = ImageProvider()
computation_provider = ComputationProvider()

# Output parameters
size = Size(args.size[0], args.size[1])  # defaults to (4096px, 2048px)
recording_id = tuple(args.recording) if args.recording != None else None


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

    cursor = frames.query(recordingid=frame.recordingid, index=frame.index + 1)
    next_frame = Frame(cursor)
    if next_frame is not None:
        geometry = util.get_geometry(args, next_frame.altitude)
    else:
        geometry = util.get_geometry(args)

    request = client.fetch(
        request_builder.build_orthographic(size, geometry))

    result = image_provider.fetch(request)
    # Save the file
    filename = "orthographic_{}.tif".format(frame.index)
    with open(os.path.join(output_path, filename), 'wb') as image_file:
        image_file.write(result.image.getvalue())
        result.image.close()
