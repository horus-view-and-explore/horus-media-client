from horus_gis import SchemaProvider, PositionVector, Geographic
from horus_geopandas import HorusGeoDataFrame
import geopandas as gpd
import os

### Read Data ####
sp = SchemaProvider()
schema = sp.merge(sp.single_measurement(), sp.clustering())
database = HorusGeoDataFrame(schema)

single_measurement_path = "output/single_measurement.shp"
if not os.path.exists(single_measurement_path):
    print(
        f"File '{single_measurement_path}' not found.\nRun 'horus_media_examples.spherical_camera_single_measurement' first."
    )
    exit(1)
database.append_file("output/single_measurement_clusters.shp")

dataframe = database.dataframe

### Reconstruct PositionVector
surf_vpp_per_cluster = {k: [] for k in dataframe["clstr_id"].unique()}
geolocation_per_cluster = {}
confidence_per_cluster = {}


for index, row in dataframe.iterrows():  # Looping over all points
    ### Surface info =  ViewParameterizedPixel
    pos_vector = PositionVector(
        dataframe.at[index, "cam_lat"],
        dataframe.at[index, "cam_lon"],
        dataframe.at[index, "cam_alt"],
        dataframe.at[index, "surf_yaw"],
        dataframe.at[index, "surf_pitch"],
    )
    id = dataframe.at[index, "clstr_id"]
    surf_vpp_per_cluster[id].append(pos_vector)


### Triangulate
for vpp in surf_vpp_per_cluster:
    pos_vectors = surf_vpp_per_cluster[vpp]
    geolocation_per_cluster[vpp] = Geographic.triangulate(pos_vectors)
    confidence_per_cluster[vpp] = 0.7  # some metric

### Write Data
schema = sp.merge(sp.geometry_3dpoint(), sp.clustering())
database = HorusGeoDataFrame(schema)

for vpp in surf_vpp_per_cluster:
    lat = geolocation_per_cluster[vpp][0]
    lon = geolocation_per_cluster[vpp][1]
    alt = geolocation_per_cluster[vpp][2]

    record = database.new_frame()
    record["geometry"] = gpd.points_from_xy(x=[lon], y=[lat], z=[alt])
    record["clstr_id"] = vpp
    record["clstr_conf"] = confidence_per_cluster[vpp]
    database.add_frame(record)


database.write_shapefile("output/cluster_locations.shp")
