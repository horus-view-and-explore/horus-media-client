"""Horus Media"""
# Copyright(C) 2019, 2020 Horus View and Explore B.V.


from dataclasses import dataclass
from PIL import Image
from itertools import chain
from enum import Enum

import urllib.parse
import io
import math
import json
import logging
import http.client


@dataclass
class Point:
    x: float = 0
    y: float = 0

    def __iter__(self):
        yield self.x
        yield self.y

    def __getitem__(self, ii):
        """Get a list item"""
        if ii == 0:
            return self.x
        if ii == 1:
            return self.y

    def __len__(self):
        return 2


@dataclass
class Rect(Point):
    width: float = 0
    height: float = 0


@dataclass
class Box:
    min: Point
    max: Point

    @classmethod
    def create(cls, center, width=0, height=0):
        if not isinstance(center, Point):
            center = Point(*center)
        x_interval = (center.x + width/2, center.x - width/2)
        y_interval = (center.y + height/2, center.y - height/2)
        return Box(Point(min(x_interval), min(y_interval)), Point(max(x_interval), max(y_interval)))


@dataclass(frozen=True)
class Section:
    x: int
    y: int
    ax: float
    ay: float
    index: int


class Grid:
    """ Grid  8x4 (c x r) """

    def __init__(self, w_min=-180, w_max=180, h_min=-90, h_max=90, r=4, c=8):
        assert w_min < w_max
        assert h_min < h_max
        self.rows = r
        self.cols = c
        self.section_height = (h_max - h_min)/r
        self.section_width = (w_max - w_min)/c
        self.__map = {}
        for index in range(r * c):
            x = index % c
            y = (r-1) - index // c
            ax = x*self.section_width - w_max
            ay = y*self.section_height - h_max
            self.__map[index] = Section(x, y, ax, ay, index)

    def __iter__(self):
        """ Returns the Iterator object """
        return (section for section in self.__map.values())

    def __str__(self):
        return str(self.__map)

    def __getitem__(self, ii):
        """Get a list item"""
        return self.__map[ii]

    def __len__(self):
        """List length"""
        return len(self.__map)

    def __contains__(self, value):
        if isinstance(value, Section):
            return value.index in self.__map
        return value in self.__map

    @dataclass(frozen=True)
    class Comparator:
        min: float
        max: float
        size: float

        def __contains__(self, value):
            return self.min < (value + self.size) and value < self.max

    def filter(self, fov=None, w_min=-180, w_max=180, h_min=-90, h_max=90):
        """
        fov is a Box with min, max points
        """
        if fov:
            w_min = fov.min.x
            h_min = fov.min.y
            w_max = fov.max.x
            h_max = fov.max.y
        assert w_min < w_max
        assert h_min < h_max
        assert h_min >= -90
        assert h_max <= 90

        w_min_wrapped = (w_min % 360) - (360 if w_min < 0 else 0)
        if w_min_wrapped < -180:
            w_min_wrapped = 360 + w_min_wrapped

        w_max_wrapped = (w_max % 360) - (360 if w_max < 0 else 0)
        if w_max_wrapped > 180:
            w_max_wrapped = -360 + w_max_wrapped

        h = self.Comparator(h_min,  h_max, self.section_height)
        if w_min_wrapped < w_max_wrapped:
            w = self.Comparator(
                w_min_wrapped,  w_max_wrapped, self.section_width)
            for section in self.__map.values():
                if section.ay in h and section.ax in w:
                    yield section
        elif w_min_wrapped > w_max_wrapped:
            assert w_max_wrapped >= -180
            assert w_min_wrapped <= 180
            w_left = self.Comparator(-180,  w_max_wrapped, self.section_width)
            w_right = self.Comparator(w_min_wrapped,  180, self.section_width)
            for section in self.__map.values():
                if section.ay in h and (section.ax in w_left or section.ax in w_right):
                    yield section


@dataclass(frozen=True)
class Scale:
    id: int
    size: int


@dataclass(frozen=True)
class Scales:
    Px_256 = Scale(1, 256)
    Px_512 = Scale(2, 512)
    Px_1024 = Scale(3, 1024)
    Px_2048 = Scale(4, 2048)
    Px_4096 = Scale(5, 4096)

    __SCALES = (
        Px_256,
        Px_512,
        Px_1024,
        Px_2048,
        Px_4096,
    )

    @classmethod
    def from_size(cls, size):
        """ Returns the closest round-up scale that contains the requested size.
        Returns None if no applicable scale is found.
        """
        result = cls.__SCALES[-1]
        for scale in reversed(cls.__SCALES):
            if scale.size < size:
                return result
            result = scale
        return result

class Mode(Enum):
    panoramic = 0
    spherical = 1
    orthographic = 2
    geographic = 3

    def __str__(self):
        return self.name

@dataclass(frozen=True)
class Size:
    width: int
    height: int

@dataclass(frozen=True)
class Direction:
    yaw: float
    pitch: float

@dataclass(frozen=True)
class Geometry:
    scale: int
    width: float
    height: float
    distance: float
    shift: float
    altitude: float

class Client:
    def __init__(self, url="http://localhost:5050/web/"):
        self.url = url
        self.__parsed_url = urllib.parse.urlparse(url)
        self.__connection = http.client.HTTPConnection(
            self.__parsed_url.hostname, self.__parsed_url.port, timeout=4)
        self.__connection.connect()

    def fetch(self, request):
        request.url = urllib.parse.urljoin(
            self.__parsed_url.path, request.resource)
        self.__connection.request("GET", request.url)
        response = self.__connection.getresponse()

        request.response = response
        result = response.read()
        if type(request.local_file) == str:
            with open(request.local_file, "wb") as file:
                file.write(result)
        request.set_result(result)
        return request

    def fetch_all(self, requests):
        jobs = []
        for request in requests:
            self.fetch(request)
            jobs.append(request)

        return jobs


class ImageRequest:
    def __init__(self, builder, resource, mode=None, scale=None, section=None, size=None, direction=None, fov=None, cams = None, geometry=None):
        self.local_file = None
        self.builder = builder
        self.resource = resource
        self.mode = mode
        self.scale = scale
        self.section = section
        self.size = size
        self.direction = direction
        self.fov = fov
        self.cams = cams
        self.geometry = geometry
        self.url = None
        self.response = None
        self.__result = None

    def set_result(self, value):
        self.__result = value

    def result(self):
        return self.__result


class ImageRequestBuilder:
    def __init__(self, recording, frame):
        self.path_template = None
        self.recording = recording
        self.frame = frame
        self.__resource = f"./images/{recording}/{frame}"

    def build_spherical(self, size=None, direction=None, vof=None, cams=None):
        return self.build(Mode.spherical, None, None, size, direction, vof, cams, None)

    def build_orthographic(self, size, geometry):
        return self.build(Mode.orthographic, None, None, size, None, None, None, geometry)

    def build_geographic(self, size, direction=None, vof=None, x=None, y=None):
        if x and y:
            geometry = Geometry(0, x, y, 0, 0, 0)
        else:
            geometry = None
        return self.build(Mode.geographic, None, None, size, direction, vof, None, geometry)

    def build(self, mode=None, scale=None, section=None, size=None, direction=None, fov=None, cams=None, geometry=None):
        data = {}
        if mode:
            data["mode"] = mode
        if scale:
            data["scale"] = scale.id
        if section:
            data["section"] = section.index
        if size:
            data["size"] = str(size.width) + 'x' + str(size.height)
        if direction:
            data["yaw"] = direction.yaw
            data["pitch"] = direction.pitch
        if fov:
            data["hor_fov"] = fov
        if cams:
            data["cams"] = cams
        if geometry:
            data["scale"] = geometry.scale
            data["geom_width"] = geometry.width
            data["geom_height"] = geometry.height
            data["geom_dist"] = geometry.distance
            data["geom_shift"] = geometry.shift
            if geometry.altitude:
                data["alti_next"] = geometry.altitude
        url_values = urllib.parse.urlencode(data)
        url = urllib.parse.urljoin(self.__resource, "?" + url_values)
        request = ImageRequest(self, url, mode, scale, section, size, direction, fov, cams, geometry)
        if self.path_template:
            request.local_file = self.path_template.format(
                recording=self.recording, frame=self.frame, mode=mode if mode else "", 
                scale=scale.id if scale else "", section=section.index if section else "")
        return request

class ImageProvider:
    @dataclass(frozen=True)
    class Result:
        image: io.BytesIO
        fov: Rect
        w: int
        h: int

        def to_pixel_coordinates(self, point):
            """
            the components of thepoint represent two angles (in Grid space)
            """
            px, py = point
            py = (py/py*(py % 90) if py != 0 else 0) + 90
            dy = 180 - (self.fov.y/self.fov.y*(self.fov.y % 90) if self.fov.y != 0 else 0)
            y = (1 + (py - dy)/self.fov.height)*self.h

            px = (px/px*(px % 180) if px != 0 else 0) + 180
            dx = (self.fov.x/self.fov.x*(self.fov.x % 180) if self.fov.x != 0 else 0) + 180
            x = (px - dx)/self.fov.width*self.w

            return Point(math.floor(x),math.floor(y))

    def __init__(self, grid=Grid()):
        self.grid = grid

    def fetch(self, image_request, w = None, h = None):
        return self.Result(io.BytesIO(image_request.result()), 
            Rect(0, 0, w, h) if w and h else Rect(0, 0, 1, 1), w if w else 0, h if h else 0)

    def combine(self, image_requests, w, h):
        rows = set()
        cols = set()
        for req in image_requests:
            if req.section in self.grid:
                rows.add(req.section.y)
                cols.add(req.section.x)

        row_map = self.set_to_map(sorted(rows))
        col_map = self.set_to_map(self.wrap(sorted(cols)))
        row_index_shift = len(rows) - 1

        stitched = Image.new('RGB', (w * len(col_map), h * len(row_map)))
        fov = Rect(math.inf, math.inf, 0, 0)
        fov.width = len(col_map) * self.grid.section_width
        fov.height = len(row_map) * self.grid.section_height

        for req in image_requests:
            r = row_map[req.section.y]
            c = col_map[req.section.x]
            fov.y = min(req.section.ay, fov.y)
            fov.x = min(req.section.ax, fov.x)

            try:
                image = Image.open(io.BytesIO(req.result()))
                stitched.paste(image, (c * w, (row_index_shift - r) * h))
            except Exception as exception:
                logging.error(f"{exception}. Stitching section {req.section} from {req.url}")
        image = io.BytesIO();
        stitched.save(image, format='jpeg', quality=95)
        return self.Result(image, fov, stitched.width, stitched.height)

    @classmethod
    def wrap(cls, cols):
        if len(cols) > 0:
            prev = cols[0]
            list_1 = []
            list_2 = []
            for x in cols:
                if x - prev > 1:
                    list_1, list_2 = (list_2, list_1)
                list_1.append(x)
                prev = x

            return [x for x in chain(list_1, list_2)]
        return cols

    @classmethod
    def set_to_map(cls, my_set):
        size = len(my_set)
        if size > 0:
            mx = min(my_set)
            mp = range(size+1)
            return dict(zip(my_set, mp))
        return {}

class ComputationRequest:
    def __init__(self, builder, resource, size=None, direction=None, fov=None, x=None, y=None):
        self.local_file = None
        self.builder = builder
        self.resource = resource
        self.size = size
        self.direction = direction
        self.fov = fov
        self.url = None
        self.response = None
        self.__result = None

    def set_result(self, value):
        self.__result = value

    def result(self):
        return self.__result

class ComputationRequestBuilder:
    def __init__(self, recording, frame):
        self.path_template = None
        self.recording = recording
        self.frame = frame
        self.__resource = f"./computation/{recording}/{frame}"

    def build(self, size=None, direction=None, fov=None, x=None, y=None):
        data = {}
        if size:
            data["size"] = str(size.width) + 'x' + str(size.height)
        if direction:
            data["yaw"] = direction.yaw
            data["pitch"] = direction.pitch
        if fov:
            data["hor_fov"] = fov
        if x:
            data["x"] = x
        if y:
            data["y"] = y
        url_values = urllib.parse.urlencode(data)
        url = urllib.parse.urljoin(self.__resource, "?" + url_values)
        return ComputationRequest(self, url, size, direction, fov, x, y)

class ComputationProvider:
    @dataclass(frozen=True)
    class Result:
        data: io.BytesIO

    def fetch(self, computation_request):
        try:
            result = self.Result(io.BytesIO(
                computation_request.result())).data.getvalue()
            return json.loads(result)
        except json.decoder.JSONDecodeError as error:
            return {"error": error}
