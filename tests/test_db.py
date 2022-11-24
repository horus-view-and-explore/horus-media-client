
# Copyright(C) 2019, 2020 Horus View and Explore B.V.

import unittest
import datetime

import psycopg2

from horus_db import Frames, Recordings, Frame, Recording, RecordingSetups
from horus_db import Iterator


def get_connection():
    return psycopg2.connect(
        "dbname=HorusWebMoviePlayer user=postgres password=horusweb")


class TestRecordings(unittest.TestCase):

    def test_get(self):
        connection = get_connection()
        recording_id = 5
        recordings = Recordings(connection)
        recording = Recording(recordings.get(recording_id))
        self.assertEqual(recording.id, 5)
        self.assertEqual(
            recording.directory, "D:\\Recordings\\DemoData\\Rotterdam360\\Ladybug5plus\\Recording_18-12-2019_12-03-08")
        self.assertEqual(recording.bounding_box,
                         "BOX(4.461778927 51.892380339,4.497248851 51.930770724)")
        self.assertEqual(recording.file_format, 1)

        self.assertEqual(recording.setup, None)
        recordings.get_setup(recording)
        setup = recording.setup
        self.assertEqual(setup.camera_height, 2.49)
        self.assertEqual(setup.lever_arm_x, 0)
        self.assertEqual(setup.lever_arm_y, 0)
        self.assertEqual(setup.lever_arm_z, 0)
        self.assertEqual(setup.id, 5)
        lever_arm = setup.lever_arm
        self.assertEqual(lever_arm.x, 0)
        self.assertEqual(lever_arm.y, 0)
        self.assertEqual(lever_arm.z, 0)

    def test_get_with_directory(self):
        connection = get_connection()
        recordings = Recordings(connection)
        results = list(Recording.query(
            recordings, directory_like="Rotterdam360", order_by="id"))

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, 4)
        self.assertEqual(
            results[0].directory, "D:\\Recordings\\DemoData\\Rotterdam360\\GoProMax\\Recording2019-12-18_12-53-06")

        self.assertEqual(results[1].id, 5)
        self.assertEqual(
            results[1].directory, "D:\\Recordings\\DemoData\\Rotterdam360\\Ladybug5plus\\Recording_18-12-2019_12-03-08")

    def test_get_with_directory_single(self):
        connection = get_connection()
        recordings = Recordings(connection)
        recording = next(Recording.query(
            recordings, directory_like="Rotterdam360\\\\Ladybug5plus"))

        self.assertEqual(recording.id, 5)
        self.assertEqual(
            recording.directory, "D:\\Recordings\\DemoData\\Rotterdam360\\Ladybug5plus\\Recording_18-12-2019_12-03-08")

    def test_query(self):
        connection = get_connection()
        recordings = Recordings(connection)
        cursor = recordings.all()
        self.assertIsNotNone(cursor)

        description_len = len(cursor.description)
        self.assertEqual(description_len, 4)

        iterator_count = 0
        for result in Iterator(cursor):
            iterator_count += 1
            self.assertEqual(len(result), description_len)

        self.assertGreater(cursor.rowcount, 3)
        self.assertEqual(iterator_count, cursor.rowcount)

    def test_query_setups(self):
        connection = get_connection()
        setups = RecordingSetups(connection)
        cursor = setups.all()
        self.assertIsNotNone(cursor)

        description_len = len(cursor.description)
        self.assertEqual(description_len, 7)

        iterator_count = 0
        for result in Iterator(cursor):
            iterator_count += 1
            self.assertEqual(len(result), description_len)

        self.assertGreater(cursor.rowcount, 3)
        self.assertEqual(iterator_count, cursor.rowcount)


class TestFrames(unittest.TestCase):

    def test_query(self):
        connection = get_connection()

        recordings = (973, 972)
        point = (5.7058276, 50.8510157)  # EPSG:4326 (lon, lat)
        distance = 2  # in meters

        frames = Frames(connection)
        cursor = frames.query(within=(point, distance),
                              recordingid=recordings, limit=1)
        self.assertIsNotNone(cursor)

        frame = Frame(cursor)

        timestamp = datetime.datetime(2016, 5, 11, 8, 6, 24, 90000)
        self.assertEqual(frame.id, 727692)
        self.assertEqual(frame.recordingid, 972)
        self.assertEqual(frame.guid, "c5a3c5f5-b760-44f7-875a-fddaa268d710")
        self.assertEqual(frame.uuid, "c5a3c5f5-b760-44f7-875a-fddaa268d710")
        self.assertEqual(frame.latitude, 50.8510157)
        self.assertEqual(frame.longitude, 5.7058276)
        self.assertEqual(frame.altitude, 95.029)
        self.assertEqual(frame.roll, -0.1474)
        self.assertEqual(frame.pitch, 1.1014)
        self.assertEqual(frame.azimuth, 162.0647)
        self.assertEqual(frame.heading, 162.0647)
        self.assertEqual(frame.timestamp, timestamp)
        self.assertEqual(frame.stamp, timestamp)
        self.assertEqual(frame.index, 271)
        self.assertEqual(frame.distance, 0.0)

    def test_query_distance(self):
        connection = get_connection()

        recordings = (973, 972)
        point = (5.7058276, 50.8510157)  # EPSG:4326 (lon, lat)
        distance_max = 2  # in meters
        distance_min = 5  # in meters

        frames = Frames(connection)
        cursor = frames.query(
            within=(point, distance_max),
            distance=(point,  "> %s", distance_min),
            recordingid=recordings,
            limit=1
        )
        self.assertIsNotNone(cursor)

    def test_query_recordingid(self):
        connection = get_connection()

        recordings = 972
        point = (5.7058276, 50.8510157)  # EPSG:4326 (lon, lat)
        distance = 2  # in meters

        frames = Frames(connection)
        cursor = frames.query(within=(point, distance),
                              recordingid=recordings, limit=3, offset=1)
        self.assertIsNotNone(cursor)

        frame = Frame(cursor)

        timestamp = datetime.datetime(2016, 5, 11, 8, 6, 24, 90000)
        self.assertEqual(frame.id, 727953)
        self.assertEqual(frame.recordingid, 972)
        self.assertEqual(frame.uuid, "9089f29d-9437-4a3c-bd88-ed9e27445289")


if __name__ == '__main__':
    unittest.main()
