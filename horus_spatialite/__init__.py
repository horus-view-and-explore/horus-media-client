"""Horus database"""
# Copyright(C) 2022 Horus View and Explore B.V.

import os
import pathlib
import glob
from xml.etree import ElementTree
from horus_db import Recording, Recordings, Frame, Frames

from typing import NamedTuple

# Dep on the sqlite/spatialite for geosuiteDb
try:
    import spatialite
    from shapely import wkt, wkb
except ModuleNotFoundError as e:
    print(f"Install module '{e.name}' to use module 'horus_spatialite'.")
    raise e


class Spatialite:
    """
    Database used for making annotations using the Horus Geo Suite
    """
    class Field_info(NamedTuple):
        idx: int
        name: str
        type: str

    recordings = {}
    blob_containing_geometry = {}
    recording_field_name: str = None
    frame_index_field_name: str = None
    geometry_field_name = "the_geom"
    table_name: str
    field_info_map: {str, Field_info} = None

    FIELD_INFO_IDX = 0
    FIELD_INFO_NAME = 1
    FIELD_INFO_TYPE = 2
    FIELD_NAME_GEOM = "GEOMETRY"
    FIELD_NAME_BLOB = "BLOB"

    # --- Remote Database
    RD_connection = None
    spatialite_RD_recording_map = {}

    # ------ Recordings On Disk  ------
    ROD_frame_location_guids = []
    ROD_recordings_root_folder: str = None
    spatialite_ROD_recording_map = {}

    def __init__(self, filename):
        self.filename = filename
        self.table_name = self.__table_name_from_file__()

    def set_recordings_on_disk_root_folder(self, path):
        self.ROD_recordings_root_folder = path

    def set_recording_field(self, field_name):
        self.recording_field_name = field_name

    def set_frame_index_field(self, field_name):
        self.frame_index_field_name = field_name

    def set_remote_db_connection(self, connection):
        self.RD_connection = connection

    def open(self):
        self.conn = spatialite.connect(self.filename)

    def close(self):
        self.conn.close()

    def get_cursor(self):
        return self.conn.cursor()

    def check_cursor(self, cursor):
        if cursor is None:
            cursor = self.get_cursor()
            return True, cursor
        return False, cursor

    def version(self):
        return self.conn.execute('SELECT spatialite_version()').fetchone()[0]

    def get_table_name(self):
        return self.table_name

    def set_table_name(self, name):
        self.table_name = name

    def get_field_query(self, cursor):
        cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = '" +
                       self.table_name + "' AND type = 'table'")

    def get_table_info_query(self, cursor):
        cursor.execute("PRAGMA table_info(\""+self.table_name+"\")")

    def get_table_names(self, cursor):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

    def get_recordings(self, cursor):
        cursor.execute("SELECT DISTINCT	" + self.recording_field_name +
                       " FROM \"" + self.table_name + "\";")
    
    def set_geometry_field_name(self, field_name):
        self.geometry_field_name = field_name;

    def blob_contains_geometry(self,field_name):
        self.blob_containing_geometry[field_name] = True

    def get_field_names_map(self, cursor=None) -> {str: Field_info}:
        if not self.field_info_map is None:
            return self.field_info_map

        cleanup, cursor = self.check_cursor(cursor)
        self.get_table_info_query(cursor)
        records = cursor.fetchall()

        data = {row[self.FIELD_INFO_NAME]: Spatialite.Field_info(row[self.FIELD_INFO_IDX],
                                                                 row[self.FIELD_INFO_NAME],
                                                                 row[self.FIELD_INFO_TYPE]) for row in records}
        row_idx = len(data)
        data["rowid"] = Spatialite.Field_info(row_idx, "rowid", "INTEGER")

        if cleanup:
            cursor.close()

        return data

    def query(self, cursor=None, field_names_map=None, order_by_list=[]):
        cleanup, cursor = self.check_cursor(cursor)

        if field_names_map is None:
            if self.field_info_map is None:
                field_info_map = self.get_field_names_map(cursor)
            else:
                field_names_map = self.field_info_map

        fields = []
        for k, field in field_names_map.items():
            if field.type == self.FIELD_NAME_GEOM:
                fields.append("AsText(" + k + ")")
            else:
                fields.append(k)

        myselect = ','.join(fields)

        query_ = "SELECT " + myselect + " FROM \""+self.table_name+"\""

        add = " "
        for x in order_by_list:
            query_ += add + "ORDER BY " + x + " ASC"
            add = ","

        query_ += ";"
        cursor.execute(query_)
        return cursor

    def get_geometry(self, cursor, field_names_map=None):
        if field_names_map == None:
            field_names_map = self.field_info_map
        geoms = {}
        for k, field in field_names_map.items():
            if field.type == self.FIELD_NAME_GEOM:
                if cursor[field.idx] != None:
                    geoms[k] = wkt.loads(cursor[field.idx])
            elif field.type == self.FIELD_NAME_BLOB:                
                if field.name in self.blob_containing_geometry:                    
                    if cursor[field.idx] != None:                        
                        geoms[k] = wkb.loads(cursor[field.idx])                            
        return geoms

    def get_matched_frames_iterator(self):
        cursor = self.get_cursor()
        orderby = []
        if self.recording_field_name in self.field_info_map:
            orderby.append(self.recording_field_name)
        self.query(cursor, self.field_info_map, orderby)
        return FrameMatchedIterator(cursor, self.RD_connection, self)

    def resolve(self):
        # obtain the fields with the table appended with rowid
        cursor = self.get_cursor()
        self.field_info_map = self.get_field_names_map(cursor)

        if self.recording_field_name != None and self.recording_field_name in self.field_info_map:
            # Get all the unique recordings in spatialite
            self.get_recordings(cursor)
            data = [x[0] for x in cursor.fetchall() if x[0] != None]
            for path in data:
                __FIX_ME__ = path.replace("\\", "/")  # windows unix hell
                p = pathlib.PurePath(__FIX_ME__)
                if p.suffix.strip() == ".idx":
                    p = p.parent
                self.recordings[path] = p.name

        # Resolve relation local recording(field) => remote
        if self.recording_field_name != None and self.RD_connection != None:
            self.spatialite_RD_recording_map = self.resolve_remote_recording(
                self.recording_field_name, self.RD_connection, cursor)

        # Resolve relation local recording(field => disk)
        if self.ROD_recordings_root_folder != None:
            self.resolve_on_disk_recording(self.ROD_recordings_root_folder)

    def match_paths(self, r, p, candidates):
        r1 = r.split('\\')
        c1 = [c.split('/') for c in candidates]

        while r1[-1] != p:
            r1.pop()

        try:
            while True:
                r1.pop()
                matched = 0
                index = 0
                idx = 0
                for c in c1:
                    c.pop()
                    if c[-1] == r1[-1]:
                        matched += 1
                        index = idx
                    idx += 1

                if matched == 1:
                    return candidates[index]
        except:
            return None

    def resolve_on_disk_recording(self, recording_folder: str):
        for k, v in self.recordings.items():
            folder = recording_folder+"**/"+v

            candidates = glob.glob(folder, recursive=True)
            matched = self.match_paths(k, v, candidates)
            if matched != None:
                self.spatialite_ROD_recording_map[k] = matched

    def resolve_remote_recording(self, recording_field_name: str, connection, cursor):
        cleanup, cursor = self.check_cursor(cursor)
        resolved = {}

        for k, v in self.recordings.items():
            recordings = Recordings(connection)
            cursor2 = Recording.query(
                recordings, directory_like=v, order_by="id")

            rec = next(cursor2, None)
            recordings.get_setup(rec)

            recs = []
            while (rec) != None:
                recs.append(rec)
                rec = next(cursor2, None)

            while len(recs) != 1:
                raise Exception(
                    "Spatialite::resolve_recording Implement duplicate!")

            resolved[k] = recs[0]

        if cleanup:
            cursor.close()

        return resolved

    def resolve_frames(self, recording_name):
        for k, v in self.spatialite_ROD_recording_map.items():
            if k == recording_name:
                tree = ElementTree.parse(v+"/frames.xml")
                root = tree.getroot()
                a = tree.findall(
                    "./{http://tempuri.org/FramesDataSet.xsd}Location/{http://tempuri.org/FramesDataSet.xsd}GUID")
                frame_location_guids = [x.text for x in a]
                return frame_location_guids

    def __table_name_from_file__(self):
        return os.path.splitext(os.path.basename(self.filename))[0]

    def show_info(self):

        print("\n------- Spatialite --------")
        print("Version: ", self.version())
        print("Table: ", self.get_table_name())
        print("\n")

        print("\n------- Field Info --------")
        for k, field_info in self.field_info_map.items():
            print(field_info.idx, " ", field_info.name, "  ", field_info.type)
        print("\n")

        cursor = self.get_cursor()

        print("\n------- Browse Data --------")
        self.query(cursor, self.field_info_map)

        entries = 4
        for row in cursor:
            if entries > 0:
                entries -= 1
                geoms = self.get_geometry(row, self.field_info_map)                
                print("--------------------")
                for k, field_info in self.field_info_map.items():
                    if k in geoms:
                        print(field_info.idx, ":", geoms[k]) 
                    else:
                        print(field_info.idx, ":", row[field_info.idx])

        print("\n-------  Recordings / Spatialite --------")
        for k, v in self.recordings.items():
            print(k, " -> ", v)

        print("\n-------  Recording / Remote relation --------")
        for k, rec in self.spatialite_RD_recording_map.items():
            print(k, " -> ", rec)

        print("\n-------  Recording / On Disk relation --------")
        for k, v in self.spatialite_ROD_recording_map.items():
            print(k, " -> ", v)


class FrameMatchedIterator:

    class MatchedFrame:
        spatialite_cursor = None
        frame: Frame = None
        recording: Recording = None
        properties = {}
        metadata = {}

        def dump(self):
            print("spatialite_cursor", self.spatialite_cursor)
            print("Frame", self.frame)
            print("Recording", self.recording)
            print("Properties", self.properties)

        def oke(self):
            return self.spatialite_cursor != None and self.frame != None and self.recording != None

    spatialite_db: Spatialite
    current_recording: str = None
    static_recording: Recording = None
    recordings_list: [str, Recording] = {}

    guids: [str] = None

    use_recording_field = False
    use_frame_index_field = False
    use_static_recording = False

    recording_field_idx: int
    frame_index_field_idx: int

    def __init__(self, cursor, connection, spatialite_db: Spatialite):
        self.cursor = cursor
        self.connection = connection
        self.spatialite_db = spatialite_db
        self.frames = Frames(connection)
        self.recordings = Recordings(connection)

        # Can we use the Recording field
        if spatialite_db.recording_field_name != None:
            if self.spatialite_db.recording_field_name in self.spatialite_db.field_info_map:
                self.use_recording_field = True
                self.recording_field_idx = self.spatialite_db.field_info_map[
                    self.spatialite_db.recording_field_name].idx

        # Can we use Frame index field
        if spatialite_db.frame_index_field_name != None:
            if self.spatialite_db.frame_index_field_name in self.spatialite_db.field_info_map:
                self.use_frame_index_field = True
                self.frame_index_field_idx = self.spatialite_db.field_info_map[
                    self.spatialite_db.frame_index_field_name].idx

    def set_static_recording_by_id(self, id):
        recordings = Recordings(self.connection)
        cursor = Recording.query(recordings, id=id)
        recording = next(cursor, None)
        if recording != None:
            recordings.get_setup(recording)
            self.use_static_recording = True
            self.static_recording = recording

    def __iter__(self):
        return self

    def __next__(self):
        frame = next(self.cursor, None)

        while frame != None:

            # Build up the matched frame
            f = self.MatchedFrame()

            use_recording_field = self.use_recording_field
            use_frame_index_field = self.use_frame_index_field
            frame_guid = None
            frame_index = None

            if use_recording_field:
                if frame[self.recording_field_idx] == None:
                    use_recording_field = False
                else:
                    if frame[self.recording_field_idx] != self.current_recording:
                        self.current_recording = frame[self.recording_field_idx]
                        self.guids = self.spatialite_db.resolve_frames(
                            self.current_recording)

            if use_frame_index_field:
                if frame[self.frame_index_field_idx] == None:
                    use_frame_index_field = False
                else:
                    frame_index = int(frame[self.frame_index_field_idx])
                    # Try to be more precise with GUID
                    if self.guids != None and len(self.guids) >= frame_index:
                        frame_guid = self.guids[int(
                            frame[self.frame_index_field_idx])]

            if frame_guid != None:
                f.properties["guid"] = frame_guid

            if frame_index != None:
                f.properties["index"] = frame_index

            # Allow static recordings set_static_recording_by_id(..)
            if self.use_static_recording:
                f.properties["recordingid"] = self.static_recording.id

            elif not self.current_recording is None:
                if not self.spatialite_db.spatialite_RD_recording_map is None:
                    if self.current_recording in self.spatialite_db.spatialite_RD_recording_map:
                        f.properties["recordingid"] = self.spatialite_db.spatialite_RD_recording_map[self.current_recording].id

            has_guid = "guid" in f.properties
            has_frame_index = "index" in f.properties
            has_recording_id = "recordingid" in f.properties

            if (has_recording_id and has_frame_index) or has_guid:
                cursor = self.frames.query(**f.properties)
            else:
                geom = self.spatialite_db.get_geometry(
                    frame)[self.spatialite_db.geometry_field_name]

                distance_min = 5
                distance_max = 10
                cursor = self.frames.query(within=(*geom.centroid.coords, distance_max),
                                           **f.properties,
                                           distance=(*geom.centroid.coords, "> %s",
                                                     distance_min), limit=1)

            f.spatialite_cursor = frame
            f.frame = Frame(cursor)

            if (f.frame == None):
                return f

            if not f.frame.recordingid in self.recordings_list:
                temp_rec = next(Recording.query(
                    self.recordings, id=f.frame.recordingid))
                self.recordings.get_setup(temp_rec)
                self.recordings_list[f.frame.recordingid] = temp_rec

            f.recording = self.recordings_list[f.frame.recordingid]

            self.add_metadata_from_remote_db(f, {"file", "path"})

            return f
        else:
            raise StopIteration

    def add_metadata_from_remote_db(self, f, keys):
        iie_query = "select * from frames,image_index_entries where image_index_entries.frame_id = " + \
            str(f.frame.id) + " and frames.recordingid = " + \
            str(f.recording.id)

        __cursor__ = self.connection.cursor()
        __cursor__.execute(iie_query)

        values = __cursor__.fetchone()
        field_names = [field[0] for field in __cursor__.description]
        row = dict(zip(field_names, values))

        for k in keys:
            if k in row:
                f.metadata["image_index_entries."+k] = row[k]
