# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Frame

# This example shows how to get a specific frame

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

# Get frame by its uuid
cursor = frames.query(guid=frame.uuid)

frame = Frame(cursor)
print(" ", frame.uuid, " ", frame.longitude, " ", frame.latitude)

# Alternatively get frame by recording id and index (next frame)
cursor = frames.query(recordingid=frame.recordingid, index=frame.index + 1)

if frame is None:
    print("No next frame!")
    exit()

frame = Frame(cursor)
print(" ", frame.uuid, " ", frame.longitude, " ", frame.latitude)