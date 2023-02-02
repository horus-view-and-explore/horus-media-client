# Copyright(C) 2022 Horus View and Explore B.V.


import os
import logging

from horus_db import Frames, Frame
from horus_media import ImageRequestBuilder, ImageProvider, Mode, Scales

from . import util

# Command line input handling
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)
parser.add_argument("-t", "--time",  metavar=("START", "END"), nargs=2, type=str,
                    help="time interval to query. E.g. '2022-02-13T14:30:00' '2022-02-13T15:00:00'")
parser.add_argument("--path", type=str, help="path to output location")
parser.add_argument("--limit", metavar=("NUMBER"), type=int, default=100,
                    help="maximum number of frames")
parser.add_argument("-r", "--recording", metavar="ID",
                    nargs='*', type=int, help="recording id")


args = parser.parse_args()

# This example shows how to request a spherical image
output_path = args.path

if args.time is None or len(args.time) != 2:
    logging.error(f"Invalid time interval '{args.time}'")
    exit()

if output_path is None:
    logging.error(f"Specify an output path using '--path'")
    exit()

connection = util.get_connection(args)
client = util.get_client(args)

frames = Frames(connection)
image_provider = ImageProvider()

# Input parameters
recording_id = tuple(args.recording) if args.recording != None else None


# Get frames
results = Frame.query(frames,
                      # tuple of timestamp strings (begin, end)in ISO format
                      time_interval=args.time,
                      # recording id (optional)
                      recordingid=recording_id,
                      order_by="index",
                      limit=args.limit,
                      )

for frame in results:
    if frame is None:
        print("No frames!")
        exit()

    print(frame, "at", frame.stamp)

    # Get the image
    request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
    request = client.fetch(request_builder.build(
        Mode.panoramic, Scales.Px_1024))
    result = image_provider.fetch(request)

    # Save the file
    filename = "{}_{}_{}.jpg".format(
        frame.recordingid, frame.index, frame.stamp)

    with open(os.path.join(output_path, filename), 'wb') as image_file:
        image_file.write(result.image.getvalue())
        result.image.close()
