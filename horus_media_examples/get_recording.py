# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2

from horus_db import Recordings, Recording

# This example shows how to get a specific recording

def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")

connection = get_connection()
recordings = Recordings(connection)

cursor = recordings.all()

# Get the first recording
recording = Recording(cursor)

if recording is None:
    print("No recordings!")
    exit()

# Alternatively select a recording by id
cursor = recordings.get(id=recording.id)
recording = Recording(cursor)

# Or query the database for a recording by directory
cursor = connection.cursor()
cursor.execute("""SELECT id, recordingdirectory, boundingbox, fileformat
FROM recordings WHERE recordingdirectory = %s;""", (recording.directory,))
recording = Recording(cursor)

print(" ", recording.id, " ", recording.directory)