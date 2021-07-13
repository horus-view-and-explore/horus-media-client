# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Frames, Recordings, Frame, Recording

# This example shows how to iterate over all the recordings

def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")

connection = get_connection()
recordings = Recordings(connection)

cursor = recordings.all()

recording = Recording(cursor)

while recording is not None:
    print(" ", recording.id, " ", recording.directory)
    recording = Recording(cursor)
