# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Recordings, Frame, Recording

# This example shows how to iterate over all the frames in a recording

def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")

connection = get_connection()
recordings = Recordings(connection)
frames = Frames(connection)

cursor = recordings.all()

# Get the first recording
recording = Recording(cursor)
print(" ", recording.id, " ", recording.directory)

if recording is None:
    print("No recordings!")
    exit()

# Get all frames of a recording
cursor = frames.query(recordingid=recording.id)

frame = Frame(cursor)

while frame is not None:
    print(" ", frame.recordingid, " ", frame.uuid, " ", frame.longitude, " ", frame.latitude)
    frame = Frame(cursor)