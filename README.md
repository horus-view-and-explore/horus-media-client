# Horus Media Server Client

An [Horus Media Server](https://horus.nu/horus-geo-suite/) client python library

## [Install latest release](https://github.com/horus-view-and-explore/horus-media-client/wiki/Install-latest-release)


## Example tools

Interactive examples

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

## [Run the example strategy](https://github.com/horus-view-and-explore/horus-media-client/wiki/Example-strategy-tool)

```
python3 -m horus_media_examples.example_strategy --help
```
