from horus_gis import SchemaProvider
import horus_gis as hg
from horus_geopandas import HorusGeoDataFrame

import pandas as pd
import geopandas as gpd
import fiona

from math import radians, cos, sin, asin, sqrt


def haversine(point1, point2):  # lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """

    lon1 = point1.x
    lat1 = point1.y
    lon2 = point2.x
    lat2 = point2.y

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    m = 6367000 * c
    return m


class Clustering_analysis:
    cluster_layer: HorusGeoDataFrame
    cluster_location_layer: HorusGeoDataFrame
    schema_provider: SchemaProvider

    layers: None

    def __init__(self):
        self.schema_provider = SchemaProvider()
        self.layers = {}

    def cluster_data_layer(self, filename, layer=None):
        schema = self.schema_provider.merge(
            self.schema_provider.single_measurement(), self.schema_provider.clustering()
        )

        self.cluster_layer = HorusGeoDataFrame(schema)
        self.cluster_layer.append_file(filename, layer)

    def cluster_location(self, filename, layer=None):
        schema = self.schema_provider.merge(
            self.schema_provider.geometry_3dpoint(), self.schema_provider.clustering()
        )
        self.cluster_location_layer = HorusGeoDataFrame(schema)
        self.cluster_location_layer.append_file(filename, layer)

    def analyse_cluster_entries(self):
        """
        Adds the cluster_entries_analysis layer with:
        distance: meter to triangulation
        """

        schema = SchemaProvider.Schema("Analysis cluster entries")
        schema.fields = [
            SchemaProvider.Field(
                "geometry",
                "Row idx (observeration) geometry.",
                SchemaProvider.Geometry(SchemaProvider.Geometry.Type.POINT_3D),
            ),
            SchemaProvider.Field("usr_id", "The id", int),
            SchemaProvider.Field(
                "distance", "Distance between approximation and triangulation.", int
            ),
            SchemaProvider.Field(
                "angle", "Angle between camera movement and detected object.", float
            ),
        ]
        database = HorusGeoDataFrame(schema)

        loc_df = self.cluster_location_layer.dataframe
        data_df = self.cluster_layer.dataframe
        for index, row in loc_df.iterrows():
            mask = data_df["clstr_id"] == row["clstr_id"]
            entries = data_df.loc[mask]
            for point_i, point_r in entries.iterrows():
                record = database.new_frame()
                record["geometry"] = point_r["geometry"]
                record["usr_id"] = point_r["usr_id"]
                record["distance"] = haversine(row["geometry"], point_r["geometry"])
                record["angle"] = point_r["dt_yaw"] - point_r["azimuth"]

                database.add_frame(record)

        self.layers["cluster_entries_analysis"] = database

    def analyse_cluster(self):
        """
        Adds the cluster_analysis layer with:
        distance: meter to triangulation
        """
        schema = SchemaProvider.Schema("Analysis clusters")
        schema.fields = [
            SchemaProvider.Field(
                "geometry",
                "Cluster geometry.",
                SchemaProvider.Geometry(SchemaProvider.Geometry.Type.POINT_3D),
            ),
            SchemaProvider.Field(
                "clstr_pts", "Number of points used for clustering.", int
            ),
        ]
        database = HorusGeoDataFrame(schema)

        loc_df = self.cluster_location_layer.dataframe
        data_df = self.cluster_layer.dataframe
        for index, row in loc_df.iterrows():
            mask = data_df["clstr_id"] == row["clstr_id"]
            entries = data_df.loc[mask]

            record = database.new_frame()
            geoms = []
            for point_i, point_r in entries.iterrows():
                geoms.append(point_r["geometry"])
            record["clstr_pts"] = len(geoms)
            database.add_frame(record)

        self.layers["cluster_analysis"] = database

    def write_package(self, filename):
        self.layers["cluster_layer"] = self.cluster_layer
        self.layers["cluster_location_layer"] = self.cluster_location_layer
        for k, v in self.layers.items():
            v.write_geopackage(filename, layer=k)
