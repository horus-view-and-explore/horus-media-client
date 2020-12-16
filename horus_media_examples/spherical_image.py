# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, Size, Direction

# This example shows how to request a spherical image

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
size = Size(1024, 1024)
direction = Direction(yaw = 45, pitch = -20)

# Get the image
request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
request = client.fetch(request_builder.build_spherical(size, direction))
result = image_provider.fetch(request)

# Save the file
filename = ".\\spherical_{}.jpg".format(frame.id)

with open(filename, 'wb') as f:
    f.write(result.image.getvalue())
    result.image.close()
