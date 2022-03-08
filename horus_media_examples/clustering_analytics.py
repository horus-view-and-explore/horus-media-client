from horus_analytics import Clustering_analysis
import os


single_measurement_path = "output/single_measurement_clusters.shp"
if not os.path.exists(single_measurement_path):
    print(f"File '{single_measurement_path}' not found.\nRun 'horus_media_examples.spherical_camera_single_measurement' first.")
    exit(1)

cluster_locations_path = "output/cluster_locations.shp"
if not os.path.exists(cluster_locations_path):
    print(f"File '{cluster_locations_path}' not found.\nRun 'horus_media_examples.triangulate_spherical_camera_singlemeasurement_clusters' first.")
    exit(1)

ca = Clustering_analysis()
ca.cluster_data_layer(single_measurement_path)
ca.cluster_location(cluster_locations_path)

ca.analyse_cluster_entries()
ca.analyse_cluster()

ca.write_package("output/clustering_analysis.gpkg")