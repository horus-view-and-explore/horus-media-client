# Copyright(C) 2019, 2020 Horus View and Explore B.V.

import unittest

import numpy
from horus_gis import EnuModel, CameraModel, SchemaProvider


class TestEnuModel(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestEnuModel, self).__init__(*args, **kwargs)

        # lon, lat, altitude # origin of ENU, (altitude is height above ellipsoid)
        self.camera_location = numpy.array((48.0, 5.0, 10.0))
        self.look_at_target_location = numpy.array((48.001, 5.01, 10.0))
        self.look_at_vector_result = (110.897, 1105.829, -0.097)

    def test_to_enu_reference(self):
        camera_enu_reference = EnuModel(self.camera_location)
        origin = camera_enu_reference.to_geodetic((0, 0, 0))
        self.assertTrue(numpy.allclose(origin, self.camera_location))

    def test_to_enu(self):
        camera_enu_reference = EnuModel(self.camera_location)
        look_at_vector = camera_enu_reference.to_enu(self.look_at_target_location)

        self.assertTrue(
            numpy.allclose(numpy.around(look_at_vector, 3), self.look_at_vector_result),
            "look_at_target_location to ENU",
        )

        self.assertEqual(
            numpy.around(numpy.linalg.norm(look_at_vector), 3),
            1111.376,
            "look_at_vector_result magnitude",
        )

        heading = camera_enu_reference.get_heading(look_at_vector)
        self.assertEqual(numpy.around(heading, 3), -5.727, "Heading")


class TestCameraModel(unittest.TestCase):
    def test_look_at(self):
        camera_location = (4.486625622, 51.895778197, 49.305309)
        camera_heading = 65.734584
        look_at_location = (4.486649, 51.89575, 47.28)

        camera_model = CameraModel(camera_location, camera_heading)
        look_at_angle = camera_model.look_at_angle(look_at_location)

        diff = look_at_angle - 87.49439415551622

        self.assertTrue(diff < 0.001, "look_at_angle")


class TestSchemaProvider(unittest.TestCase):
    def single_measurement_schema(self):
        sp = SchemaProvider()
        schema = sp.single_measurement()
        self.assertEqual(23, len(schema))


if __name__ == "__main__":
    unittest.main()
