FROM python:3.9-bullseye

ENV PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /data/

RUN apt-get update
RUN pip install horus-media-client

RUN apt install -y apt-utils
RUN pip install --upgrade pip
RUN apt install -y python3-geopandas
RUN apt install -y libsqlite3-mod-spatialite
RUN apt install -y python3-pyproj
RUN apt install -y python3-shapely
RUN apt install -y python3-pymap3d

CMD ["bash"]
