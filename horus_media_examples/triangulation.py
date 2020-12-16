# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2
import numpy
import cv2
from typing import NamedTuple
from matplotlib import patches as patches, pyplot as pyplot

from horus_db import Recordings, Recording, Frames, Frame
from horus_media import Client, ImageRequestBuilder, ImageProvider, ComputationRequestBuilder, \
                                ComputationProvider, Size, Direction
from horus_gis import PositionVector, Geographic

# This example shows how to use triangulation to get geographic positions 
# on boxes drawn by the user on 3 consecutive frames

connection = psycopg2.connect("dbname=HorusWebMoviePlayer user=postgres password=horusweb")
client = Client()
image_provider = ImageProvider()
computation_provider = ComputationProvider()

def main():
    no_of_frames = 3
    no_of_points = 4

    # Example parameters
    size = Size(718, 476)
    direction = Direction(0, 0)
    hor_fov = 112.915016

    # Get a frame, see 'get_frame.py' to get a specific frame
    frame = get_frame()

    if frame is None:
        print("No recordings!")
        exit()

    pos_vecs = []

    # Request image, apply detection and request position vector for detection 
    for i in range(no_of_frames):
        # Get the image and apply detection
        request = get_image_request(frame, size, direction, hor_fov)
        box = get_detection(image_provider.fetch(request).image.getvalue())

        # Request position vector for each pixel coordinate
        for pix_coor in box:
            for px in pix_coor:
                pos_vecs.append(get_position_vector(frame, request, px))

        frame = get_next_frame(frame)


    # Triangulate position for each box corner
    positions = []
    for i in range(no_of_points):
        positions.append(Geographic.triangulate([pos_vecs[i], pos_vecs[i + no_of_points], 
                                        pos_vecs[i + (2 * no_of_points)]]))

    plot_results(pos_vecs, positions)


class PixelCoordinate(NamedTuple):
    x: int
    y: int

class BoundingBox(NamedTuple):
    px: PixelCoordinate

def get_frame():
    recordings = Recordings(connection)
    frames = Frames(connection)
    cursor = recordings.all()
    recording = Recording(cursor)
    cursor = frames.query(recordingid=recording.id, index=0)
    return Frame(cursor)

def get_next_frame(frame):
    frames = Frames(connection)
    cursor = frames.query(recordingid=frame.recordingid, index=frame.index + 1)
    return Frame(cursor)

def get_image_request(frame, size, direction, hor_fov):
    request_builder = ImageRequestBuilder(frame.recordingid, frame.uuid)
    return client.fetch(request_builder.build_spherical(size, direction, hor_fov))

def get_position_vector(frame, image_request, px):
    request_builder = ComputationRequestBuilder(frame.recordingid, frame.uuid)
    request = client.fetch(request_builder.build(image_request.size, image_request.direction, 
                                                 image_request.fov, px.x, px.y))
    result = computation_provider.fetch(request)
    return PositionVector(*result.values())

def get_detection(image):
    window_name = 'Draw a box, then escape to exit'
    ix = -1
    iy = -1
    global is_drawing
    global box

    buffer = numpy.frombuffer(image, dtype='uint8')
    img = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    is_drawing = False

    def draw_rectangle(event, x, y, flags, param):
        global is_drawing, ix, iy, box
        if event == cv2.EVENT_LBUTTONDOWN:
            is_drawing = True
            ix = x
            iy = y
        elif event == cv2.EVENT_LBUTTONUP:
            is_drawing = False
            cv2.rectangle(img, (ix, iy), (x, y), (0, 255, 0), -1)
            box = BoundingBox([PixelCoordinate(ix, iy), PixelCoordinate(x, iy),
            PixelCoordinate(x, y), PixelCoordinate(ix, y)])
        elif event == cv2.EVENT_MOUSEMOVE:
            if is_drawing:
                cv2.rectangle(img, (ix, iy), (x, y), (0, 255, 0), -1)

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, draw_rectangle)

    while True:
        cv2.imshow(window_name, img)

        if cv2.waitKey(5) & 0xFF == 27:
            break

    cv2.destroyAllWindows()

    return box

def plot_results(pos_vecs, positions):
    camera_positions = numpy.array(pos_vecs)
    detection_positions = numpy.array(positions)
    pyplot.plot(camera_positions[:,1], camera_positions[:,0], 'ro')
    pyplot.plot(detection_positions[:,1], detection_positions[:,0], 'bo')

    pyplot.legend(handles=[patches.Patch(color='red', label='camera'), 
        patches.Patch(color='blue', label='detection')], loc='lower right')
    pyplot.ticklabel_format(useOffset=False, style='plain')
    pyplot.title('Horus Triangulation Example')
    pyplot.ylabel('Lat')
    pyplot.xlabel('Lon')
    pyplot.show()

main()
