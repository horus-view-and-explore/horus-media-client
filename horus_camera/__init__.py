
import math
import io

from horus_db import Frame, Recording
from horus_media import Client, ImageRequestBuilder, ImageRequest, ImageProvider, Size, Direction, \
    ComputationRequestBuilder, ComputationProvider, Rect
from horus_gis import PositionVector, Geographic, CameraModel


class FieldOfView():
    value: float
    min: float
    max: float

    def __init__(self, value: float, min: float, max: float):
        self.value = value
        self.min = min
        self.max = max


class GeographicLocation():
    """GeographicLocation longitude,latitude,altitude

    Geographic location refers to a position on the Earth. 
    Your absolute geographic location is defined by two coordinates,
    longitude and latitude. In the case of imagery, the altitude is added/required
    to be able to georeference pixels from this imagery.

    The reference system is that in which the recording has been stored in the database,
    which is usually EPSG Projection 4326 - WGS 84. 
    """
    lat: float
    lon: float
    alt: float

    def __init__(self, lon: float, lat: float, alt: float):
        self.lon = lon
        self.lat = lat
        self.alt = alt

    @staticmethod
    def from_tuple(tuple_lon_lat_alt):
        return GeographicLocation(
            tuple_lon_lat_alt[0],
            tuple_lon_lat_alt[1],
            tuple_lon_lat_alt[2])

class RelativeLocation():
    """RelativeLocation, east, north, up
    
        The relative location in meters using the ENU coordinate system.
    """
    east: float
    north: float
    up: float

    def __init__(self, east: float, north: float, up: float):
        self.east = east
        self.north = north
        self.up = up

    def location(self):
        return [self.east, self.north, self.up]

class Pixel():
    row: int
    col: int

    def __init__(self, row: int,  col: int):
        self.row = row
        self.col = col


class ViewParameterizedPixel():
    """Parameters for georeferencing

    The ViewParameterizedPixel is a data structure that
    has all the information that is required for geo-referencing
    pixels. 

    ViewParameterizedPixels can be obtained from specific 
    Imagery that have geo-referencing capabilities, such as the SphericalImage.

    A set of 3 different ViewParameterizedPixels from 3 different locations
    can than be used for triangulation resulting in a GeographicLocation.

    Attributes:
        name                Label to identify the pixel
        pixel_location      The pixel location in pixel coordinates
        viewing_parameters
        recording_id        The id of the source recording
        frame_index         The index of the source frame in the source recording
        user_data           Dictionary to store optional user-defined data about this pixel
    """
    name: str
    pixel_location: Pixel
    viewing_parameters: PositionVector
    recording_id: int
    frame_index: int
    user_data: dict

    def __init__(self):
        self.user_data = {}


class GeoReferencedPixel(ViewParameterizedPixel):
    """Parameters for georeferencing with GeographicLocation.

    The GeoReferencedPixel is the same data structure as the 
    ViewParameterizedPixel with an additional GeographicLocation.

    A single ViewParameterizedPixel can be turned into a GeoReferencedPixel
    when additional constraints/assumptions are added to the Pixel/PositionVector.

    In the case of the SphericalImage, the function project_pixel_on_ground_surface 
    adds constraints on the altitude coordinate, thus allowing for an estimation
    on the GeographicLocation.

    The distance is the ground distance from camera to geo_location.
    """
    distance: float
    geo_location: GeographicLocation
    relative_loc: RelativeLocation

    def __init__(self, vpp: ViewParameterizedPixel):
        super(GeoReferencedPixel, self).__init__()
        self.name = vpp.name
        self.pixel_location = vpp.pixel_location
        self.viewing_parameters = vpp.viewing_parameters
        self.recording_id = vpp.recording_id
        self.frame_index = vpp.frame_index


"""Horus Camera

The camera
"""
# Copyright(C) 2019, 2020 Horus View and Explore B.V.


class Camera():
    """The base camera class.

    """
    h_fov: FieldOfView           # horizontal field of view
    v_fov: FieldOfView           # vertical field of view
    yaw: float                   # yaw of the camera ?immutable
    pitch: float                 # pitch of the camera ?immutable
    frame: Frame                 # current frame
    recording: Recording         # current recording
    network_client: Client       # network client
    height: float                # height in meters

    def __init__(self):
        self.h_fov = None
        self.v_fov = None

    def set_horizontal_fov(self, fov: float):
        """Adjust the camera's horizontal field of view """

        if self.h_fov is None:
            raise Exception(
                'This camera does not support horizontal field of view.')
        if fov < self.h_fov.min or fov > self.h_fov.max:
            raise Exception('Horizontal field of view out of bounds.')

        self.h_fov.value = fov

    def set_vertical_fov(self, fov: float):
        """Adjust the camera's vertical field of view """

        if self.v_fov is None:
            raise Exception(
                'This camera does not support vertical field of view.')
        if fov < self.v_fov.min or fov > self.v_fov.max:
            raise Exception('Vertical field of view out of bounds.')

        self.h_fov.value = fov

    def set_frame(self, recording: Recording, frame: Frame):
        """Places the camera at a specific frame """
        self.frame = frame
        self.recording = recording
        if recording.setup is not None:
            self.set_camera_height(recording.setup.camera_height)

    def set_yaw(self, yaw: float):
        """Changes the yaw of the camera """
        self.yaw = yaw

    def set_pitch(self, pitch: float):
        """Changes the pitch of the camera """
        self.pitch = pitch

    def set_camera_height(self, height: float):
        """Changes the height (meters) of the camera with respect to the altitude 
            of the current frame.
        """
        self.height = height

    def set_network_client(self, client: Client):
        """Add networking capabilities to the camera """
        self.network_client = client

####################################################################
#               SPHERICAL CAMERA AND IMAGERY                       #
####################################################################


class SphericalImage():
    """ Spherical Image

        The result of picture taken through a spherical lens, with the 
        required information for localization.

    """
    nw_client: Client
    image_provider: ImageProvider
    image_request: ImageRequest
    frame: Frame
    recording: Recording
    camera_height: float
    result = None
    camera_model: CameraModel
    computation_provider: ComputationProvider
    geo_referenced_pixels: list
    view_parameterized_pixels: list

    def __init__(self):
        self.camera_model = None
        self.geo_referenced_pixels = {}
        self.view_parameterized_pixels = {}
        pass

    def get_geo_location_camera(self) -> GeographicLocation:
        """ Returns the geographical position of where the image was taken."""
        return GeographicLocation.from_tuple(self.frame.get_location())

    def get_geo_location(self) -> GeographicLocation:
        """ Returns the geographical position on the ground plane."""
        geo = GeographicLocation.from_tuple(self.frame.get_location())
        geo.alt -= self.get_camera_height()

    def get_camera_height(self):
        """ Returns the camera height with respect to the altitude of the geographical altitude."""
        return self.camera_height

    def get_resolution(self) -> Size:
        """ Returns the image resolution (width,height)"""
        # appareturn Size(self.result.w,self.result.h)
        return self.image_request.size

    def get_field_of_view(self) -> float:
        """ Returns the image field of view (horizontal,vertical)"""
        return float(self.image_request.fov)

    def set_network_configuration(self, nw_client, provider, computation, request, camera_height, frame, recording):
        """ Initializes the SphericalImage for network usage.

            Additional computations are available when a SphericalImage has been captured
            using a SphericalCamera with a connection to the media-server. In almost all cases
            the SphericalCamera's network configuration is automatically configured by the SphericalCamera.                            
        """
        self.nw_client = nw_client
        self.image_provider = provider
        self.computation_provider = computation
        self.image_request = request
        self.camera_height = camera_height
        self.frame = frame
        self.recording = recording

    def fetch(self):
        """ Fetch the internal contents of the image.

            The function fetch allows the user to choose when to fetch the actual imagery data
            from the media-server. By default the SphericalCamera::get_image(..,manual_fetch:bool) function will perform 
            the fetch automatically, however changing the manual_fetch:bool variable it is possible to control when to 
            fetch the actual data.
        """

        client_result = self.nw_client.fetch(self.image_request)
        self.result = self.image_provider.fetch(client_result)

    def get_image(self) -> io.BytesIO:
        return self.result.image

    def get_camera_model(self) -> CameraModel:
        """ Returns/Creates a camera model from the current position.

            The CameraModel(EnuModel) can be used to make inferences as well as generating 
            points and polygons in carthesian space.
        """
        if self.camera_model == None:
            camera_location = self.frame.get_location()
            camera_heading = self.frame.heading
            if self.recording.setup is not None:
                self.camera_model = CameraModel.with_leverarms(camera_location, camera_heading,
                                                               self.recording.setup.lever_arm)
            else:
                self.camera_model = CameraModel(
                    camera_location, camera_heading)

        return self.camera_model

    def get_view_parameterized_pixel(self, pixel: Pixel) -> ViewParameterizedPixel:
        """ Returns a ViewParameterizedPixel

            This function transfroms coordinates x,y (col,row)from pixel space to a
            postition and view direction (ViewParameterizedPixel).
            A series of labelled GeoReferencedPixels/ViewParameterizedPixels can be used 
            for triangulation to obtain a GeographicLocation with higher precision.      
        """
        vpp = ViewParameterizedPixel()
        vpp.name = None
        vpp.pixel_location = pixel
        vpp.frame_index = self.frame.index
        vpp.recording_id = self.recording.id

        request_builder = ComputationRequestBuilder(
            self.frame.recordingid, self.frame.uuid)
        request = self.nw_client.fetch(request_builder.build(self.get_resolution(
        ), self.image_request.direction, self.get_field_of_view(), pixel.col, pixel.row))
        result = self.computation_provider.fetch(request)

        # yaw is with respect to north
        vpp.viewing_parameters = PositionVector(*result.values())

        return vpp

    def project_pixel_on_ground_surface(self, pixel: Pixel) -> GeoReferencedPixel:
        """ Returns a GeoReferencedPixel

            This function maps coordinates x,y (col,row)from pixel space into Geographical
            space, with the corresponding angles and postion with respect to the camera.
            It does so by assuming that the horizontal plane is uniform over the entire distance,
            and that the pixel of interest can be mapped on the surface. 
            This function is typically used to get an estimate of an object in the image that rests 
            on the ground floor. A series of labelled GeoReferencedPixels/ViewParameterizedPixels can be used 
            for triangulation to obtain a GeographicLocation with higher precision.  
        """

        grp = GeoReferencedPixel(self.get_view_parameterized_pixel(pixel))

        if not -90.0 < grp.viewing_parameters.pitch < 0.0:
            raise Exception(
                'Pitch {p:2f} is out of range [-90.0, 0.0]'.format(p=grp.viewing_parameters.pitch))

        angle = 90 + grp.viewing_parameters.pitch

        ground_north_vector = math.tan(
            math.radians(angle)) * self.get_camera_height()
        vector = SphericalImage.rotate(
            0, ground_north_vector, 0, 0, math.radians(- grp.viewing_parameters.yaw))
        camera_model = self.get_camera_model()
        grp.distance = ground_north_vector
        grp.relative_loc = RelativeLocation(*vector, -self.get_camera_height())
        grp.geo_location = GeographicLocation(*camera_model.to_geodetic(grp.relative_loc.location()))

        return grp

    def store_geo_referenced_pixel(self, grp: GeoReferencedPixel):
        """ Store the GeoReferencedPixel"""
        self.geo_referenced_pixels[grp.name] = grp

    def store_view_parameterized_pixel(self, vvp: ViewParameterizedPixel):
        """ Store the ViewParameterizedPixel"""
        self.view_parameterized_pixels[vvp.name] = vvp

    def rotate(x, y, xo, yo, theta):  # rotate x,y around xo,yo by theta (rad)
        xr = math.cos(theta)*(x-xo)-math.sin(theta)*(y-yo) + xo
        yr = math.sin(theta)*(x-xo)+math.cos(theta)*(y-yo) + yo
        return [xr, yr]

    @staticmethod
    def triangulate(label, list_of_images) -> GeographicLocation:
        """ Triangulate using the stored labelled 
            ViewParameterizedPixels and GeoReferencedPixels.
        """
        viewing_params_with_label = []

        for img in list_of_images:
            for name in img.geo_referenced_pixels:
                grp: GeoReferencedPixel = img.geo_referenced_pixels[name]
                if grp.name == label:
                    viewing_params_with_label.append(grp.viewing_parameters)

            for name in img.view_parameterized_pixels:
                vvp: ViewParameterizedPixel = img.view_parameterized_pixels[name]
                if vvp.name == label:
                    viewing_params_with_label.append(vvp.viewing_parameters)

        loc = Geographic.triangulate(viewing_params_with_label)
        return GeographicLocation(loc[1], loc[0], loc[2])


class SphericalCamera(Camera):
    """Camera with a spherical lens.

    This class describes a camera with a spherical lens based on the gnomonic projection 
    https://en.wikipedia.org/wiki/Gnomonic_projection. 

    The lens has the following properties:
        horizontal field of view [0,90]  <--- @todo marten
        vertical field of view [0,90]    <--- @todo marten

    """
    yaw: float
    pitch: float

    def __init__(self):
        """Construct a Spherical camera. """
        super().__init__()
        self.h_fov = FieldOfView(90.0, 1.0, 160.0)

    def set_pitch(self, pitch: float):
        """Adjust the camera's pitch

            The pitch range: 
            looking down:   -90 deg
            looking up  :    90 deg

        """
        self.pitch = pitch

    def set_yaw(self, yaw: float):
        """Adjust the camera's yaw

            The yaw range: 
            max left :  -180 deg
            max right:   180 deg

        """
        self.yaw = yaw

    def set_horizontal_fov(self, fov: float):
        """Adjust the camera's horizontal field of view """
        super().set_horizontal_fov(fov)

    def set_frame(self, recording: Recording, frame: Frame):
        """Places the camera at a specific frame """
        super().set_frame(recording, frame)

    def set_camera_height(self, height: float):
        """Changes the height (meters) of the camera with respect to the altitude 
            of the current frame.
        """
        super().set_camera_height(height)

    def set_network_client(self, client: Client):
        """Add networking capabilities to the camera """
        super().set_network_client(client)

    def look_at(self, geo_location: GeographicLocation):
        """Set the view direction yaw/pitch of the current frame to a geographic location"""
        if self.recording.setup is not None:
            camera_model = CameraModel.with_leverarms(self.frame.get_location(), self.frame.heading,
                                                      self.recording.setup.lever_arm)
        else:
            camera_model = CameraModel(
                self.frame.get_location(), self.frame.heading)

        yaw, pitch = camera_model.look_at(
            [geo_location.lon, geo_location.lat, geo_location.alt])
        self.set_yaw(yaw - self.frame.heading)
        self.set_pitch(pitch)

    def acquire(self, size: Size, manual_fetch: bool = False) -> SphericalImage:
        """Acquire a Spherical image from the current position/configuration of the camera"""

        ver_fov = 2 * math.degrees(math.atan(size.height * math.tan(
            (math.radians(self.h_fov.value)) / 2) / size.width))

        if not self.h_fov.min < ver_fov < self.h_fov.max:
            raise Exception('Vertical fov {ver_fov:2f} is out of range [{min:1f}, [{max:1f}]]'.format(
                ver_fov=ver_fov, min=self.h_fov.min, max=self.h_fov.max))

        if self.network_client != None:
            request_builder = ImageRequestBuilder(
                self.frame.recordingid, self.frame.uuid)
            request = request_builder.build_spherical(
                size, Direction(self.yaw, self.pitch), self.h_fov.value)

            image = SphericalImage()
            image.set_network_configuration(self.network_client, ImageProvider(
            ), ComputationProvider(), request, self.height, self.frame, self.recording)

            if not manual_fetch:
                image.fetch()

            return image

        return None
