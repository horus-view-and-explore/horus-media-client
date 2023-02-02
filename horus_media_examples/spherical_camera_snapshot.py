# Copyright(C) 2020 Horus View and Explore B.V.

import psycopg2
import os

from horus_db import Frames, Frame, Recordings, Recording
from horus_media import Client, ImageRequestBuilder, ImageProvider, Mode, Direction, Size
from horus_camera import SphericalCamera
from horus_gis import GeographicLocation

from . import util


# Create output directory
output_dir = os.path.join(os.getcwd(), 'output')

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# This example shows how to create snapshots based on geometry


# Command line input handling
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)

parser.add_argument("--path", type=str, help="path to output location")

args = parser.parse_args()

# This example shows how to request a spherical image
output_path = args.path

connection = util.get_connection(args)
client = util.get_client(args)
frames = Frames(connection)
image_provider = ImageProvider()


# Step 1. create and configure spherical camera
sp_camera = SphericalCamera()
sp_camera.set_network_client(client)




def take_shaphost(nr,recording:Recording, frame:Frame, positions):
    sp_camera.set_frame(recording, frame)
    size = sp_camera.look_at_all(positions,1024)

    spherical_image = sp_camera.crop_to_geometry(sp_camera.acquire(size), positions, True)

    with open(output_dir + '/snapshot'+ str(nr) + '.jpeg', 'wb') as image_file:
        image_file.write(spherical_image.get_image().getvalue())
        spherical_image.get_image().close()




snapshot_1 = ["DemoData\Rotterdam360\Ladybug5plus" , 16, [
    GeographicLocation (4.4883159319642543,51.908492027690912, 53.361715),
    GeographicLocation (4.4884184967537415,51.908456244872745, 53.361715),
    GeographicLocation (4.48847610048205,51.908519406825874, 53.361715),
    GeographicLocation (4.4883735356838885,51.90855518966265, 53.361715)
    ]]


snapshot_2 = ["DemoData\Rotterdam360\Ladybug5plus" , 981, [
    GeographicLocation (4.4643636161038245,51.910632575408812,47.090053),
    GeographicLocation (4.4644063962677194,51.910582531617663,47.090053),
    GeographicLocation ( 4.46443096611172,51.910590565679584,47.090053),
    GeographicLocation (4.464388185974328,51.9106406094716,47.090053)
    ]]


snapshot_3 = ["DemoData\Rotterdam360\Ladybug5plus" , 981, [
    GeographicLocation (4.4644173663344944,51.910644188474507,47.090053),
    GeographicLocation (4.464431966331305,51.910622670221294,47.090053),
    GeographicLocation (4.4644493531869944,51.910627182612672,47.090053),
    GeographicLocation (4.4644347531983941,51.910648700866034,47.090053)
]]

snapshots = [snapshot_1,snapshot_2,snapshot_3]



recordings = Recordings(connection)
cursor = recordings.all()
recording = Recording(cursor)
while recording is not None:
    if snapshot_1[0] in recording.directory:
        recordings.get_setup(recording)

        nr = 0
        for snapshot in snapshots:
            results = Frame.query(frames, recordingid=recording.id,
                              index=snapshot[1],)
            frame = next(results)
            take_shaphost(nr,recording,frame,snapshot[2])
            nr += 1

    # next recording
    recording = Recording(cursor)


print("done")