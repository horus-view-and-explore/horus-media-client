FROM debian:11

WORKDIR /data/

RUN apt-get update

RUN apt install -y apt-utils
RUN apt install -y python3-geopandas
RUN apt install -y libsqlite3-mod-spatialite
RUN apt install -y python3-pyproj
RUN apt install -y python3-shapely
RUN apt install -y python3-pymap3d
RUN apt install -y python-is-python3

RUN pip install horus-media-client==0.9.3
RUN pip install spatialite

CMD ["bash"]
