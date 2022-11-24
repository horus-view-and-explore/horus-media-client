# Copyright(C) 2021, 2022 Horus View and Explore B.V.
import copy
import os
from pprint import pprint


import json
from horus_media import Size
from horus_camera import SphericalCamera, Pixel, SphericalImage, GeoReferencedPixel, ViewParameterizedPixel
from horus_db import Frames, Recordings, Frame, Recording
from horus_gis import SchemaProvider
from . import util
from horus_geopandas import HorusGeoDataFrame
import geopandas as gpd

def fill_record(record,frame,grp: GeoReferencedPixel, det_vp: ViewParameterizedPixel,camera:SphericalCamera, image:SphericalImage, detection):

    # update geometry
    record["geometry"] = gpd.points_from_xy(x=[grp.geo_location.lon], y=[grp.geo_location.lat])
    # Record
    record["rec_id"] = grp.recording_id
    record["frame_idx"] = grp.frame_index
    record["azimuth"] = frame.azimuth
    #
    record["cam_fov"] = camera.h_fov.value
    record["cam_yaw"] = camera.yaw
    record["cam_pitch"] = camera.pitch
    record["cam_width"] = image.get_resolution().width
    record["cam_height"] = image.get_resolution().height
    record["cam_lat"] = image.get_geo_location_camera().lat
    record["cam_lon"] = image.get_geo_location_camera().lon
    record["cam_alt"] = image.get_geo_location_camera().alt
    #
    record["dt_class"] = detection.classification
    record["dt_name"] =  detection.name
    record["dt_x"] = detection.detection_pixel.col
    record["dt_y"] = detection.detection_pixel.row
    record["dt_width"] = detection.detection_size.width
    record["dt_height"] = detection.detection_size.height
    record["dt_conf"] = detection.confidence
    record["dt_dist"] = grp.distance

    # viewing parameters of the detection
    record["dt_px_x"] = det_vp.pixel_location.col
    record["dt_px_y"] = det_vp.pixel_location.row
    record["dt_yaw"] = det_vp.viewing_parameters.yaw
    record["dt_pitch"] = det_vp.viewing_parameters.pitch

    # viewing parameters of the surface projection
    record["surf_px_x"] = grp.pixel_location.col
    record["surf_px_y"] = grp.pixel_location.row
    record["surf_yaw"] = grp.viewing_parameters.yaw
    record["surf_pitch"] = grp.viewing_parameters.pitch



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


# Opening JSON file
f = open('input/spherical_camera_single_measurement.json')
data = json.load(f)

# Select the demo city of Rotterdam
recording = next(Recording.query(
    recordings, directory_like=data["recording_name"]))
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

sp = SchemaProvider()
database = HorusGeoDataFrame(sp.single_measurement())


class Camera:
    yaw: float
    pitch: float
    cam_size: Size
    cam_hor_fov:float

    def __init__(self):
        self.yaw = 0
        self.pitch = -10
        self.cam_size = Size(800,800)
        self.cam_hor_fov = 90

    def load(self,data):
        if "width" in data:
            self.cam_size = Size(int(data["width"]),self.cam_size.height)
        if "height" in data:
            self.cam_size = Size(self.cam_size.width,int(data["height"]))
        if "yaw" in data:
            self.yaw = float(data["yaw"])
        if "pitch" in data:
            self.pitch = float(data["pitch"])
        if "horizontal_fov" in data:
            self.cam_hor_fov = float(data["horizontal_fov"])


    def clone(self):
        return copy.deepcopy(self)

class Detection:
    """Describes and a Detection / Point of interest within the image """
    surface_pixel: Pixel
    detection_pixel: Pixel
    detection_size: Size
    classification :int
    name:str
    confidence : float
    camera: Camera

    def __init__(self,camera) -> None:
        self.camera = camera

    def load(self,dt):
        self.surface_pixel = Pixel(int(dt["surface_pixel"]["r"]),int(dt["surface_pixel"]["c"]))
        self.detection_pixel = Pixel(int(dt["detection_pixel"]["r"]), int(dt["detection_pixel"]["c"]))
        self.detection_size = Size(int(dt["detection_size"]["width"]), int(dt["detection_size"]["height"]))

        self.name = dt["name"]
        self.confidence = float(dt["confidence"])
        self.classification = int(dt["classification"])

        if "camera" in dt:
            self.camera.load(dt["camera"])







# Step 4,
# That actual processing of the provided data
# Creating a set of labelled geo referenced pixels [GeoReferencedPixel]
# which we will use to triangulate in step 6 for a more accurate location
list_of_images = []

camera = Camera()
camera.load(data["camera"])

detections_per_frame = data["detections_per_frame"]

# Create output directory
output_dir = os.path.join(os.getcwd(), 'output')

if not os.path.exists(output_dir):
    os.makedirs(output_dir)


for frame_id in detections_per_frame:
    results = Frame.query(frames, recordingid=recording.id,
                          index=frame_id, order_by="index",)
    frame = next(results)
    if frame is None:
        print("No frames!")
        exit()

    print("Got frame:", frame, frame.get_location())
    sp_camera.set_frame(recording, frame)
    print("camera_height", sp_camera.height)


    for detection_id in detections_per_frame[frame_id]:

        detection = Detection(camera.clone())
        detection.load(detections_per_frame[frame_id][detection_id])

        # -- obtain database frame
        record = database.new_frame()

        # -- set the camera
        sp_camera.set_horizontal_fov(detection.camera.cam_hor_fov)
        sp_camera.set_yaw(detection.camera.yaw)
        sp_camera.set_pitch(detection.camera.pitch)

        # -- acquire
        spherical_image = sp_camera.acquire(detection.camera.cam_size)

        # with open(output_dir + '/frame' + str(frame.index) + '_' + detection.name + '.jpeg', 'wb') as image_file:
        #    image_file.write(spherical_image.get_image().getvalue())
        #    spherical_image.get_image().close()

        # Step 5
        # obtain a GeoReferencedPixel on the surface
        grp: GeoReferencedPixel = spherical_image.project_pixel_on_ground_surface(
            detection.surface_pixel)
        grp.name = detection.name

        # step 6
        # obtain the ViewParameterizedPixel of the actual detection
        detection_parms = spherical_image.get_view_parameterized_pixel(detection.detection_pixel);

        fill_record(record,frame,grp,detection_parms,sp_camera,spherical_image, detection)
        record["usr_id"] = database.dataframe.shape[0]
        database.add_frame(record)



database.write_shapefile(os.path.join(output_dir, "single_measurement.shp"))

