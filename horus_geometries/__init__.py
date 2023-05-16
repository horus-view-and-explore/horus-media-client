import horus_gis as HG
import numpy as NP
import math

try:
    import shapely as SP
    from shapely import geometry
    import pyproj as PP
except ModuleNotFoundError as e:
    print(f"Install module '{e.name}' to use this module.")
    raise e


class Geometry_proj:
    class Projection:
        def __init__(self, model=None, is_enu=None, geometry=None, geod=None) -> None:
            self.model: HG.EnuModel = model
            self.is_enu: bool = is_enu
            self.geometry = geometry
            self.geod: PP.Geod = geod

    def create_projection(self, geom):
        proj = Geometry_proj.Projection()
        proj.geod = PP.Geod(ellps="WGS84")
        proj.is_enu = False

        if geom.geom_type == "Polygon":
            proj.model = HG.EnuModel(geom.exterior.coords[0])
        elif geom.geom_type == "LineString" or geom.geom_type == "Point":
            proj.model = HG.EnuModel(geom.coords[0])
        else:
            raise Exception("Geometry_proj not supported geometry.")

        return proj

    def to_polygon(self, values):
        return SP.geometry.Polygon(values)

    def to_linestring(self, values):
        return SP.geometry.LineString(values)

    def to_point(self, value):
        return SP.geometry.Point(value)

    def geographic_to_polygon(self, geoms: [HG.GeographicLocation]):
        return self.to_polygon([[x.lon, x.lat, x.alt] for x in geoms])

    def geographic_to_linestring(self, geoms: [HG.GeographicLocation]):
        return self.to_linestring([[x.lon, x.lat, x.alt] for x in geoms])

    def geographic_to_point(self, geom: HG.GeographicLocation):
        return self.to_point([geom.lon, geom.lat, geom.alt])

    def to_geographic(self, geometry):
        if geometry.geom_type == "Polygon":
            return [HG.GeographicLocation(*x) for x in geometry.exterior.coords]
        return [HG.GeographicLocation(*x) for x in geometry.coords]

    def bounding_box(self, geometry):
        return SP.geometry.box(*geometry.bounds)

    def rotate(self, geometry, projection, angle):
        return SP.geometry.Polygon(
            [
                projection.model.rotate(p, math.radians(angle))
                for p in geometry.exterior.coords
            ]
        )

    def to_enu(self, geom, projection: Projection = None):
        if projection is None:
            projection = self.create_projection(geom)

        projection.is_enu = True

        if geom.geom_type == "Polygon":
            enu_list = [projection.model.to_enu(e) for e in geom.exterior.coords]
            projection.geometry = SP.geometry.Polygon(enu_list)

        elif geom.geom_type == "LineString":
            enu_list = [projection.model.to_enu(e) for e in geom.coords]
            projection.geometry = SP.geometry.LineString(enu_list)

        elif geom.geom_type == "Point":
            enu_point = projection.model.to_enu(*geom.coords)
            projection.geometry = SP.geometry.Point(enu_point)
        else:
            raise Exception("Geometry_proj not supported geometry.")

        return projection

    def to_geodetic(self, geom, projection: Projection):
        if projection is None:
            raise Exception("Geometry_proj::to_wgs requires a projection.")

        if not projection.is_enu:
            raise Exception("Geometry_proj::to_wgs projection should be in enu.")

        p = Geometry_proj.Projection()
        p.model = projection.model
        p.geod = projection.geod

        if geom.geom_type == "Polygon":
            geo_list = [projection.model.to_geodetic(e) for e in geom.exterior.coords]
            p.geometry = SP.geometry.Polygon(geo_list)
            p.is_enu = False

        elif geom.geom_type == "LineString":
            geo_list = [projection.model.to_geodetic(e) for e in geom.coords]
            p.geometry = SP.geometry.LineString(geo_list)
            p.is_enu = False

        elif geom.geom_type == "Point":
            geo_point = projection.model.to_geodetic(*geom.coords)
            p.geometry = SP.geometry.Point(geo_point)
            p.is_enu = False
        else:
            raise Exception("Geometry_proj not supported geometry.")

        return p

    def split_linestring(self, geometry, max_length: float):
        projection = self.create_projection(geometry)
        projection.geometry = geometry

        return [x.geometry for x in self.split_linestring_proj(projection, max_length)]

    def split_linestring_proj(self, projection: Projection, max_length: float):
        proj = projection
        incomming_is_enu = proj.is_enu

        if not incomming_is_enu:
            proj = self.to_enu(proj.geometry)

        length = proj.geometry.length
        equal_distance = length / math.ceil(length / max_length)

        linestrings = []
        points = []

        geoms = list(proj.geometry.coords)
        while len(geoms) > 0:
            cp = geoms.pop(0)

            if len(points) >= 1:
                linestring = SP.geometry.LineString([*points, cp])

                if linestring.length <= equal_distance:
                    points.append(cp)
                else:
                    split_point = linestring.interpolate(equal_distance)
                    linestring = SP.geometry.LineString([*points, split_point])
                    linestrings.append(linestring)
                    geoms.insert(0, cp)
                    geoms.insert(0, split_point)
                    points = []
            else:
                points.append(cp)

        if len(points) > 1:
            linestring = SP.geometry.LineString(points)
            if linestring.length > 0.01:
                linestrings.append(linestring)

        projections = []
        for l in linestrings:
            p = Geometry_proj.Projection()
            p.geometry = l
            p.is_enu = proj.is_enu
            p.geod = proj.geod
            p.model = proj.model
            projections.append(p)

        if not incomming_is_enu:
            projections = [
                self.to_geodetic(proj.geometry, proj) for proj in projections
            ]

        return projections

    def point_to_square(self, geometry, width: float):
        projection = self.create_projection(geometry)
        projection.geometry = geometry

        return self.point_square_proj(projection, width).geometry

    def point_square_proj(self, projection: Projection, width):
        s = width / 2.0
        square = SP.geometry.Polygon([(s, s, 0), (-s, s, 0), (-s, -s, 0), (s, -s, 0)])
        projection.is_enu = True
        return self.to_geodetic(square, projection)

    def buffer(self, geometry, value):
        projection = self.create_projection(geometry)
        projection.geometry = geometry

        return self.buffer_proj(projection, value).geometry

    def buffer_proj(self, projection, value):
        proj = projection
        incomming_is_enu = proj.is_enu

        if not incomming_is_enu:
            proj = self.to_enu(proj.geometry)

        if proj.geometry.geom_type == "Polygon":
            z = proj.geometry.exterior.coords[0][2]
        elif (
            proj.geometry.geom_type == "LineString"
            or proj.geometry.geom_type == "Point"
        ):
            z = proj.geometry.coords[0][2]
        else:
            raise Exception("Geometry_proj not supported geometry.")

        geom = SP.geometry.Polygon(
            [(*p, z) for p in proj.geometry.buffer(value).exterior.coords]
        )
        return self.to_geodetic(geom, proj)
