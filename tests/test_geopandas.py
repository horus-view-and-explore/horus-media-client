# Copyright(C) 2022 Horus View and Explore B.V.

import unittest

import os

from horus_gis import SchemaProvider
from horus_geopandas import HorusGeoDataFrame
import geopandas as gpd

# Create output directory
output_dir = "./tests/data/"
try:
    os.mkdir(output_dir)
except OSError:
    pass


class TestTriangulation(unittest.TestCase):
    def test_triangulation_examples(self):
        # import horus_media_examples.spherical_camera_single_measurement
        try:
            import horus_media_examples.single_measurement_clustering
        except Exception as e:
            self.fail(
                "{} failed ({}: {})".format(
                    "horus_media_examples.single_measurement_clustering", type(e), e
                )
            )
        try:
            import horus_media_examples.triangulate_spherical_camera_single_measurement_clusters
        except Exception as e:
            self.fail(
                "{} failed ({}: {})".format(
                    "horus_media_examples.triangulate_spherical_camera_single_measurement_clusters",
                    type(e),
                    e,
                )
            )
        try:
            import horus_media_examples.clustering_analytics
        except Exception as e:
            self.fail(
                "{} failed ({}: {})".format(
                    "horus_media_examples.clustering_analytics", type(e), e
                )
            )


class TestHorusGeoDataFrame(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestHorusGeoDataFrame, self).__init__(*args, **kwargs)
        # Obtain schema
        self.schema = SchemaProvider()
        self.database = HorusGeoDataFrame(self.schema.single_measurement())

    def test_create_record(self):
        geom = gpd.points_from_xy([-58.66000], [-34.58000])
        record = self.database.new_frame(geom)

        # update geometry
        record["geometry"] = geom
        # Record
        record["rec_id"] = 1
        record["frame_idx"] = 2
        record["azimuth"] = 3
        record["usr_id"] = 4
        #
        record["cam_fov"] = 90.0
        record["cam_yaw"] = 20.0
        record["cam_pitch"] = -30
        record["cam_width"] = 800
        record["cam_height"] = 800
        record["cam_lat"] = 51.912414163999998
        record["cam_lon"] = 4.481792547000000
        record["cam_alt"] = 51.954732000000000
        #
        record["dt_class"] = 1
        record["dt_name"] = "sign-a"
        record["dt_x"] = 100
        record["dt_y"] = 20
        record["dt_width"] = 100
        record["dt_height"] = 100
        record["dt_conf"] = 0.9
        record["dt_dist"] = 1.5

        # viewing parameters of the detection
        record["dt_px_x"] = 15
        record["dt_px_y"] = 15
        record["dt_yaw"] = 15.6
        record["dt_pitch"] = 15.6

        # viewing parameters of the surface projection
        record["surf_px_x"] = 15
        record["surf_px_y"] = 15
        record["surf_yaw"] = 15.6
        record["surf_pitch"] = 15.6

        self.database.add_frame(record)

        self.database.write_shapefile(
            os.path.join(output_dir, "single_measurement.shp")
        )

        self.database.write_geojson(
            os.path.join(output_dir, "single_measurement.geojson")
        )

        self.database.write_geopackage(
            os.path.join(output_dir, "single_measurement.gpkg"),
            layer="singlemeasurement",
        )
