# Horus Media Server Client

## [Install latest release](https://github.com/horus-view-and-explore/horus-media-client/wiki/Install-latest-release)


## Example tools

Interactive examples: they require access to the horus test playground to run.

### Spherical camera
This example shows how a series _minimum of 3_ of geo referenced pixels `GeoReferencedPixel`
obtained from a spherical image are used to calculate an accurate GeographicLocation for a specific label.
```
python -m horus_media_examples.spherical_camera --help
```

### Recordings tool
This example can be used to list published recordings.
```
python -m horus_media_examples.recordings_tool --help
```

### Export spherical
This example can be used to export spherical views from a set of recordings.
```
python -m horus_media_examples.export_spherical --help
```
### Export orthographic
This example can be used to export orthographic views from a set of recordings.
```
python -m horus_media_examples.export_orthographic --help
```

### Triangulation examples


These examples require to manually install these modules:
```
pip install pandas pandera fiona geopandas
```

Run these examples in order.
```
python -m horus_media_examples.spherical_camera_single_measurement --help
```
```
python -m horus_media_examples.single_measurement_clustering
```
```
python -m horus_media_examples.triangulate_spherical_camera_single_measurement_clusters
```

```
python -m horus_media_examples.clustering_analytics
```

## [Run the example strategy](https://github.com/horus-view-and-explore/horus-media-client/wiki/Example-strategy-tool)

```
python3 -m horus_media_examples.example_strategy --help
```
