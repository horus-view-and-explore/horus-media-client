"""Horus database"""
# Copyright(C) 2019, 2020, 2021 Horus View and Explore B.V.

import logging

class Table:
    attributes = {}
    repr_attributes = ["id"]

    def __new__(cls, cursor):
        self = cls._instance = object.__new__(cls)
        self.__result = cursor.fetchone()
        if not self.__result:
            return None

        for key, value in zip(cursor.description, self.__result):
            setattr(self, key.name, value)
        return self

    def __getattr__(self, name):
        if name in type(self).attributes:
            return self.__dict__[type(self).attributes[name]]
        raise Exception(f"No attribute {name}")

    @classmethod
    def query(cls, model, **kwargs):
        cursor = model.query(**kwargs)
        return cls.iter(cursor)

    @classmethod
    def iter(cls, cursor):
        item = cls(cursor)
        while item:
            yield item
            item = cls(cursor)

    def __repr__(self):
        cls = type(self)
        attrs = ', '.join('{}={}'.format(attr, getattr(self, attr))
                          for attr in type(self).repr_attributes)
        return f"{cls.__name__}({attrs})"


class Recording(Table):
    attributes = {
        "directory": "recordingdirectory",
        "bounding_box": "boundingbox",
        "file_format": "fileformat",
    }
    repr_attributes = ["id", "boundingbox"]

class Frame(Table):
    attributes = {
        "heading": "azimuth",
        "timestamp": "stamp",
        "uuid": "guid"
    }
    repr_attributes = ["id", "recordingid", "index"]

    def get_location(self):
        return (
            self.longitude,
            self.latitude,
            self.altitude)


class Recordings:
    def __init__(self, connection):
        self.__connection = connection

    def get(self, id):
        cursor = self.__connection.cursor()
        cursor.execute("""SELECT id, recordingdirectory, boundingbox, fileformat
FROM recordings WHERE id = %s;""", (id,))
        return cursor

    def all(self):
        cursor = self.__connection.cursor()
        cursor.execute("""SELECT id, recordingdirectory, boundingbox, fileformat
FROM recordings""")
        return cursor

    def query(self, **kwargs):
        select_clause = {
            "id",
            "recordingdirectory",
            "boundingbox",
            "fileformat",
        }
        where_clause = []
        orderby_clause = []
        params = []
        tail = []

        for arg, value in kwargs.items():
            if value == None:
                continue
            if arg in select_clause:
                if type(value) != tuple:
                    value = (value,)
                where_clause.append(f"{arg}" + " IN %s")
                params.append(value)
                continue
            if arg == "limit":
                tail.append("limit %s")
                params.append(value)
                if "offset" in kwargs:
                    tail.append("offset %s")
                    params.append(kwargs["offset"])
                continue
            if arg == "offset":
                continue
            if arg == "order_by":
                if type(value) != tuple:
                    value = (value,)
                orderby_clause += value
                continue

            logging.warning(
                f'Recordings query unknown argument "{arg}" skipped')

        sql = "SELECT " + ", ".join(select_clause) + " FROM recordings"

        if len(where_clause) > 0:
            sql += " WHERE " + " AND ".join(where_clause)

        if len(orderby_clause) > 0:
            orderby_clause.append("id")
            sql += " ORDER BY  " + ", ".join(orderby_clause)

        if len(tail) > 0:
            sql += " " + " ".join(tail) + ";"

        cursor = self.__connection.cursor()
        cursor.execute(sql, params)
        return cursor


class Frames:
    def __init__(self, connection):
        self.__connection = connection

    def query(self, **kwargs):
        select_clause = {
            "id",
            "recordingid",
            "guid",
            "latitude",
            "longitude",
            "altitude",
            "roll",
            "pitch",
            "azimuth",
            "stamp",
            "index"
        }
        where_clause = []
        orderby_clause = []
        params = []
        tail = []

        for arg, value in kwargs.items():
            if value == None:
                continue
            if arg == "within":
                point, distance = value
                st_point = f"ST_SetSRID(ST_Point({point[0]}, {point[1]}), 4326)"
                select_clause.add(
                    f"ST_Distance(geom::geography, {st_point}::geography) as distance")
                orderby_clause.append("distance")
                where_clause.append(
                    f"ST_DWithin(geom::geography, {st_point}::geography, {distance})")
                continue
            if arg in select_clause:
                if type(value) != tuple:
                    value = (value,)
                where_clause.append(f"{arg}" + " IN %s")
                params.append(value)
                continue
            if arg == "limit":
                tail.append("limit %s")
                params.append(value)
                if "offset" in kwargs:
                    tail.append("offset %s")
                    params.append(kwargs["offset"])
                continue
            if arg == "offset":
                continue
            if arg == "order_by":
                if type(value) != tuple:
                    value = (value,)
                orderby_clause += value
                continue

            logging.warning(f'Frames query unknown argument "{arg}" skipped')

        sql = "SELECT " + ", ".join(select_clause) + " FROM frames"

        if len(where_clause) > 0:
            sql += " WHERE " + " AND ".join(where_clause)

        orderby_clause.append("id")
        if len(orderby_clause) > 0:
            sql += " ORDER BY  " + ", ".join(orderby_clause)

        if len(tail) > 0:
            sql += " " + " ".join(tail) + ";"

        cursor = self.__connection.cursor()
        cursor.execute(sql, params)
        return cursor


def Iterator(cursor):
    item = cursor.fetchone()
    while item:
        yield item
        item = cursor.fetchone()


def print_all_results(cursor):
    """
    Iterates over a cursor, printing each results.
    The cursor will be consumed.
    """
    print(cursor.rowcount, "results")
    for result in Iterator(cursor):
        print("\n")
        for key, value in zip((column.name for column in cursor.description), result):
            print("  ", key, ":", value)
