# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, Mode, Scales, Direction, Grid

# This example shows how to request a panoramic image

def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")

connection = get_connection()
frames = Frames(connection)
client = Client()
image_provider = ImageProvider()

# Get a frame
frame = Frame(frames.query())

if frame is None:
    print("No recordings!")
    exit()

# Set parameters
mode = Mode.panoramic
scale = Scales.Px_2048

# Get the image

request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)

#(min, max) yaw in deg
directions = {
    "front":(-45, 45),
    "back":(135, 225),
    "left":(-135, -45),
    "right":(45, 135),
}

grid = Grid()
for direction in directions:
    min_yaw = directions[direction][0]
    max_yaw = directions[direction][1]
    sections = grid.filter(h_min=-44, h_max=44, w_min=min_yaw, w_max=max_yaw)
    requests = client.fetch_all(request_builder.build(Mode.panoramic, scale, section) for section in sections)
    result = image_provider.combine(requests, scale.size, scale.size)

    # Save the file
    filename = ".\\panoramic_{}_{}.jpg".format(frame.index, direction)

    with open(filename, 'wb') as f:
        f.write(result.image.getvalue())
        result.image.close()
