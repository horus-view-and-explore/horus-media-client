import numpy as np
from horus_gis import SchemaProvider
from horus_geopandas import HorusGeoDataFrame

import geopandas as gpd
import pandas as pd

import os

try:
    from sklearn.neighbors import BallTree
except ModuleNotFoundError:
    print("Install module 'sklearn' to run this example.")
    exit(1)


def dt_class_filter(database, index, indices):
    dt_class = database.at[index, "dt_class"]
    return [idx for idx in indices if database.at[idx, "dt_class"] == dt_class]


# Algorithm
def cluster(radius, tree, row_idx, database, datapoints, filter):
    # we have seen this point before
    if database.at[row_idx, "clstr_id"] != 0:
        return

    # Get the rows that fall within
    query = np.array([datapoints[row_idx]])
    ind = tree.query_radius(query, r=radius)
    ind = filter(database, row_idx, ind[0])

    relation = {idx: database.iloc[idx]["clstr_id"] for idx in ind}
    cids = {relation[k] for k in relation.keys()}

    cids.remove(0)

    length = len(cids)

    # all elements will receive the row_idx as clstr_id
    if length == 0:
        for k in relation:
            database.at[k, "clstr_id"] = row_idx
            database.at[k, "clstr_conf"] = 1.0

    # add instace to the found cluster
    if len(cids) == 1:
        new_id = next(iter(cids))
        for k in relation.keys():
            if database.at[k, "clstr_id"] != new_id:
                database.at[k, "clstr_id"] = new_id
                database.at[k, "clstr_conf"] = 1.0

    if len(cids) > 2:
        print("Edge case")
        exit(1)


### Read Data ####
sp = SchemaProvider()
schema = sp.merge(sp.single_measurement(), sp.clustering())
database = HorusGeoDataFrame(schema)

# provide a map of the new 'fields' with their default value
# missing fields will cause a schema exception
single_measurement_path = "output/single_measurement.shp"
if not os.path.exists(single_measurement_path):
    print(
        f"File '{single_measurement_path}' not found.\nRun 'horus_media_examples.spherical_camera_single_measurement' first."
    )
    exit(1)

database.append_file(
    single_measurement_path, default_values={"clstr_id": 0, "clstr_conf": 0.0}
)

# database has performed schema checks, and we will only update the cluster fields
# hence we can use the Geopandas dataframe directly
dataframe = database.dataframe


# Convert datapoints
datapoints = []

for index, row in dataframe.iterrows():  # Looping over all points
    datapoints.append(np.deg2rad([row["geometry"].y, row["geometry"].x]))


# Setup the Search tree
tree = BallTree(datapoints, metric="haversine")

# Adjust parameters
r_meter = 6371000.0
radius = 3.0 * (1.0 / r_meter)


# go fish
for index, row in dataframe.iterrows():
    cluster(radius, tree, index, dataframe, datapoints, dt_class_filter)


# Create output directory
output_dir = os.path.join(os.getcwd(), "output")

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

database.write_shapefile(os.path.join(output_dir, "single_measurement_clusters.shp"))
