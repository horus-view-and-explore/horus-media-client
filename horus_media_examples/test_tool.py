# Copyright(C) 2021 Horus View and Explore B.V.

import sys
from horus_db import Frames, Recordings, Frame, Recording
from horus_media import Grid, ImageProvider, ImageRequestBuilder, Mode, Scales
from . import util
from random import sample
import logging


# Command line input handling
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)

args = parser.parse_args()

connection = util.get_connection(args)
client = util.get_client(args)
image_provider = ImageProvider()

recordings = list(Recording.iter(Recordings(connection).all()))
frames = Frames(connection)
grid = Grid()

streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
streamHandler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(streamHandler)
logger.info("Started")
logger.setLevel(logging.INFO)

while True:
    recording = sample(recordings, 1)[0]
    cursor = frames.query(recordingid=recording.id)

    frame = Frame(cursor)

    while frame is not None:
        request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
        requests = client.fetch_all(request_builder.build(
            Mode.panoramic, Scales.Px_2048, section) for section in grid)
        logging.info(f"{frame} {request_builder}")
        frame = Frame(cursor)


