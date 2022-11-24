import numpy as np
import os
import geopandas as gpd
import pandas as pd
import sys
from PIL import Image, ImageDraw
import io




from horus_gis import SchemaProvider
from horus_geopandas import HorusGeoDataFrame
from horus_camera import SphericalCamera
from horus_db import Frames, Recordings, Frame, Recording
from horus_media import Size
from . import util


# Step 0
# Configuration part
parser = util.create_argument_parser()
util.add_database_arguments(parser)
util.add_server_arguments(parser)
parser.add_argument("-f", "--frame", type=int,nargs=1)
parser.add_argument("-i", "--input", type=str,nargs=1)


args = parser.parse_args()




### Read Data ####
sp = SchemaProvider()
database = HorusGeoDataFrame(sp.single_measurement())

# provide a map of the new 'fields' with their default value
# missing fields will cause a schema exception
single_measurement_path = "output/single_measurement.shp"
if not os.path.exists(single_measurement_path):
    print(f"File '{single_measurement_path}' not found.")
    exit(1)

database.append_file(single_measurement_path)

## Prepare Work,
class Work:
    info = None
    indices:[]

worklist = {}

for index, row in database.dataframe.iterrows(): # Looping over all points
    if row['frame_idx'] == args.frame[0]:
        id = str(row['frame_idx']) + ":" + str(row['cam_width']) + "x" + str(row['cam_height'])
        id += "_[" + str(row['cam_fov']) + "][" + str(row['cam_yaw']) + "][" + str(row['cam_pitch'])+"]"

        if id not in worklist:
            worklist[id] = Work()
            worklist[id].info = row
            worklist[id].indices = [index]
        else:
            worklist[id].indices.append(index)

## Perform Work,



connection = util.get_connection(args)
client = util.get_client(args)
recordings = Recordings(connection)

# Step 1. create and configure spherical camera
sp_camera = SphericalCamera()
sp_camera.set_network_client(client)

# Step 2. Get a recorded frame and place the camera onto that 'frame'
frames = Frames(connection)

df = database.dataframe
cnt = 0
for workid in worklist:
   cnt+=1
   print(cnt,"/", len(worklist),workid)
   job = worklist[workid]

   recording = next(Recording.query(
      recordings, id=job.info["rec_id"]))
   recordings.get_setup(recording)

   results = Frame.query(frames,
       recordingid=job.info["rec_id"],
       index=job.info["frame_idx"], order_by="index",)

   frame = next(results)
   # -- set the camera
   sp_camera.set_frame(recording, frame)
   sp_camera.set_horizontal_fov(job.info['cam_fov'])
   sp_camera.set_yaw(job.info['cam_yaw'])
   sp_camera.set_pitch(job.info['cam_pitch'])

   # -- acquire
   spherical_image = sp_camera.acquire(Size(job.info["cam_width"],job.info["cam_height"]))


   # -- draw our findings

   data = spherical_image.get_image().getvalue()
   stream = io.BytesIO(data)
   img = Image.open(stream)


   draw = ImageDraw.Draw(img)
   spherical_image.get_image().close()

   for row in job.indices:
      #print(row,"/",len(job))
      record = df.loc[[row]]

      if record.iloc[0]['dt_class'] != -1:
         # pil upper left 0,0
         x0 = record.iloc[0]['dt_x']
         y0 = record.iloc[0]['dt_y']
         w = record.iloc[0]['dt_width']
         h = record.iloc[0]['dt_height']

         shape = [ x0, y0, x0 + w , y0 + h]
         draw.rectangle(shape, outline ="red")


         surf_x =  record.iloc[0]['surf_px_x']
         surf_y =  record.iloc[0]['surf_px_y']
         #print(surf_x,surf_y)
         draw.ellipse([surf_x-2, surf_y-2, surf_x+2, surf_y+2], fill = 'blue', outline ='blue')

      draw.text((surf_x + 4, surf_y), record.iloc[0]['dt_name'], fill=None, font=None, anchor=None, spacing=0, align="left")



      img.save('output/' + workid+'.jpeg')





