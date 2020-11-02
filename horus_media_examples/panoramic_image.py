# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, Mode, Scales, Direction

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
request = client.fetch(request_builder.build(mode, scale))
result = image_provider.fetch(request)

# Save the file
filename = ".\\panoramic_{}.jpg".format(frame.index)

with open(filename, 'wb') as f:
    f.write(result.image.getvalue())
    result.image.close()
