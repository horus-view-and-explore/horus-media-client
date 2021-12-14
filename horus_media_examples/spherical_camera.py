# Copyright(C) 2021 Horus View and Explore B.V.

import psycopg2
import sys
import itertools

from horus_media import Size
from horus_camera import SphericalCamera, Pixel, SphericalImage, GeoReferencedPixel, GeographicLocation
from horus_db import Frames, Recordings, Frame, Recording
from . import util

# ----------    Overview  --------------
#
# This example shows how a series --minimum of 3-- of geo referenced pixels (GeoReferencedPixel)
# obtained from a spherical image are used to calculate an accurate GeographicLocation for a specific label.
#
# This is done in several steps:
#
# 0: Configuration
# 1: Create the SphericalCamera which we will use to acquire SphericalImages
# 2: Get some frames from the City of Rotterdam
# 3: Simulate pixel/points of interest within the images, (these where picked by hand)
# 4: Iterate over the labelled points of intererst per frame and apply the camera's yaw,pitch to look at that point.
# 5: Obtain the GeoReferencedPixel at out point of interest from step 4
# 6: Triangulate the labelled GeoReferencedPixels (minimum of 3 are required)
# 7: Write the geo-data to standard out in CSV format, which can be visually be verified by programs such a QGis

# Step 0
# Configuration part
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)

args = parser.parse_args()

connection = util.get_connection(args)
client = util.get_client(args)
recordings = Recordings(connection)

# Select the demo city of Rotterdam
recording = next(Recording.query(
    recordings, directory_like="Rotterdam360\\\\Ladybug5plus"))
recordings.get_setup(recording)
print(recording, " -> ", recording.directory)
print(recording.setup)

# Step 1. create and configure spherical camera
sp_camera = SphericalCamera()
sp_camera.set_network_client(client)

# Step 2. Get a recorded frame and place the camera onto that 'frame'
frames = Frames(connection)
results = Frame.query(frames, recordingid=recording.id,
                      index=210, order_by="index",)

# step 3. do some sight seeing..
# This sections hardcodes looking at points of interest, which
# normally would come from image processing or AI tooling.


class Poi():
    """Describes and labels a point of interest within the image """
    pixel: Pixel
    name: str
    yaw: float
    pitch: float

    def __init__(self, pixel, name, yaw, pitch) -> None:
        self.name = name
        self.pitch = pitch
        self.yaw = yaw
        self.pixel = pixel


# The list that describes:
# [ frame index -> [Points of interests] ]
frames_of_interest = [
    [210, [
        Poi(Pixel(287, 353), "p1", 20, -30),
        Poi(Pixel(209, 284), "p2", 20, -30),
        Poi(Pixel(213, 595), "p3", -40, -30)
    ]],
    [212, [
        Poi(Pixel(465, 590), "p1", 20, -30),
        Poi(Pixel(215, 343), "p2", 20, -30),
        Poi(Pixel(225, 604), "p3", -40, -30)
    ],
    ],
    [214, [
        Poi(Pixel(379, 613), "p1", 120, -30),
        Poi(Pixel(234, 303), "p2", 30, -30),
        Poi(Pixel(244, 542), "p3", -40, -30)
    ]
    ]
]

# Step 4,
# That actual processing of the provided data
# Creating a set of labelled geo referenced pixels [GeoReferencedPixel]
# which we will use to triangulate in step 6 for a more accurate location
list_of_images = []

for foi in frames_of_interest:
    results = Frame.query(frames, recordingid=recording.id,
                          index=foi[0], order_by="index",)
    frame = next(results)
    if frame is None:
        print("No frames!")
        exit()

    print("Got frame:", frame, frame.get_location())
    sp_camera.set_frame(recording, frame)
    print("camera_height", sp_camera.height)

    for poi in foi[1]:

        sp_camera.set_horizontal_fov(90)
        sp_camera.set_yaw(poi.yaw)
        sp_camera.set_pitch(poi.pitch)

        spherical_image = sp_camera.acquire(Size(800, 800))

        with open('frame' + str(frame.index) + '_' + poi.name + '.jpeg', 'wb') as image_file:
            image_file.write(spherical_image.get_image().getvalue())
            spherical_image.get_image().close()

        # Step 5
        # obtain a GeoReferencedPixel
        grp: GeoReferencedPixel = spherical_image.project_pixel_on_ground_surface(
            poi.pixel)
        grp.name = poi.name

        # you can store multiple GeoReferencedPixels with a different label
        spherical_image.store_geo_referenced_pixel(grp)

        list_of_images.append(spherical_image)

# Step 6
# Triangulate the labels
p1_tri: GeographicLocation = SphericalImage.triangulate("p1", list_of_images)
p2_tri: GeographicLocation = SphericalImage.triangulate("p2", list_of_images)
p3_tri: GeographicLocation = SphericalImage.triangulate("p3", list_of_images)

# Step 7 verify the results
# Print all the locations and info (in csv format)
print("")
print("latitude longitude altitude name frame recording row col")

# print  GeoReferencedPixel's
for img in list_of_images:
    for name in img.geo_referenced_pixels:
        grp: GeoReferencedPixel = img.geo_referenced_pixels[name]
        print(grp.geo_location.lat, grp.geo_location.lon, grp.geo_location.alt, grp.name,
              grp.frame_index, grp.recording_id, grp.pixel_location.row, grp.pixel_location.col)

print(p1_tri.lat, p1_tri.lon, p1_tri.alt, "p1_tr", -1, -1, -1, -1)
print(p2_tri.lat, p2_tri.lon, p2_tri.alt, "p2_tr", -1, -1, -1, -1)
print(p3_tri.lat, p3_tri.lon, p3_tri.alt, "p3_tr", -1, -1, -1, -1)
