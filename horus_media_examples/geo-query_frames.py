# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame

# This example shows how to geo-query frames

def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")

connection = get_connection()
frames = Frames(connection)

# Get a frame
frame = Frame(frames.query())

if frame is None:
    print("No recordings!")
    exit()

# Get frames within a certain distance of this frame
point = (frame.longitude, frame.latitude)  # EPSG:4326 (lon, lat)
distance = 20  # in meters
cursor = frames.query(within=(point, distance))

frame = Frame(cursor)

while frame is not None:
    print(" ", frame.uuid, " ", frame.longitude, " ", frame.latitude)
    frame = Frame(cursor)