# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, Mode, Size, Geometry

# This example shows how to request a georeferenced orthographic image (geotiff)

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

# If available, the altitude of the next frame is used in calculating ground plane 
# (optional, required if results should be equal to the Horus MoviePlayer)
cursor = frames.query(recordingid=frame.recordingid, index=frame.index + 1)
next_frame = Frame(cursor)
if next_frame is not None:
    alti_next = next_frame.altitude
else:
    alti_next = None

# Set parameters

# Size of render buffer, should at least be the size of the original camera resolution of the roi
size = Size(4096, 2048) 

# The geometry values relative to the frame center, same as used in the Horus MoviePlayer ortho projection
geom_scale = 400 # output scale (px/m)
geom_width = 6 # geometry width (m)
geom_height = 2 # geometry height (m)
geom_dist = 4 # geometry distance (m)
geom_shift = 0 # geometry shift (m)
geometry = Geometry(geom_scale, geom_width, geom_height, geom_dist, geom_shift, alti_next)

# Get the image
request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
request = client.fetch(request_builder.build_orthographic(size, geometry))
result = image_provider.fetch(request)

# Save the file
filename = ".\\orthographic_{}.tif".format(frame.index)

with open(filename, 'wb') as f:
    f.write(result.image.getvalue())
    result.image.close()
