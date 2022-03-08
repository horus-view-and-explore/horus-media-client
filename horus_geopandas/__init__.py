"""Horus GeoPandas https://geopandas.org/en/stable/

Utilities and Classes build on top of GeoPandas
"""


from horus_gis import SchemaProvider
import horus_gis as hg

try:
    import pandas as pd
    import pandera as pa
    import fiona as fi
    from fiona.crs import from_epsg
    import geopandas as gpd
except ModuleNotFoundError as e:
    print(f"Install module '{e.name}' to use this module.")
    raise e

class HorusGeoDataFrame:

    schema: SchemaProvider.Schema
    dataframe: gpd.GeoDataFrame
    non_geom_schema: pa.DataFrameSchema
    fiona_schema:dict
    crs:str

    fields:None
    def __init__(self,schema:SchemaProvider.Schema):

        self.crs = "EPSG:4326"
        self.schema = schema

        # Convert schema's
        # https://pandera.readthedocs.io/en/latest/dataframe_schemas.html
        the_geom_field = False

        pan_schema = {}
        self.fiona_schema = {'geometry':None, 'properties':{}}
        self.fields=[]
        for field in self.schema.fields:
            is_geom:bool = type(field.type) is hg.SchemaProvider.Geometry

            if is_geom:
                pan_schema[field.name] = pa.Column(pa.engines.pandas_engine.Geometry)
                self.fiona_schema[field.name] = str(field.type)
            else:
                pan_schema[field.name] = pa.Column(field.type)
                self.fiona_schema['properties'][field.name] = \
                    list(fi.FIELD_TYPES_MAP.keys())[list(fi.FIELD_TYPES_MAP.values()).index(field.type)]

            self.fields.append(field.name)
        
        self.non_geom_schema = pa.DataFrameSchema(pan_schema,
            index=pa.Index(int),
            strict=True,
            coerce=True,)

        self.dataframe = gpd.GeoDataFrame(columns = self.fields)
        self.at = self.dataframe.at

    def new_frame(self, geom=None):
        if geom is None:
            geom = gpd.points_from_xy([0], [0],[0])
        return gpd.GeoDataFrame(columns = self.fields, geometry=geom,crs=self.crs)

    def add_frame(self, dataframe, validate=True):
        if validate:
            self.non_geom_schema.validate(dataframe)
        self.dataframe = pd.concat([self.dataframe, dataframe])

    def append_file(self,filename, layer=None,default_values={}):
        dataframe = gpd.read_file(filename,layer=layer, schema=self.fiona_schema)

        for dv in default_values.keys():
            dataframe[dv] = default_values[dv]

        self.non_geom_schema.validate(dataframe)

        self.dataframe = pd.concat([self.dataframe, dataframe])

    def write_shapefile(self, filename):
        self.dataframe.to_file(filename, crs=from_epsg(int(self.crs.split(':')[1])), 
        schema=self.fiona_schema)

    def write_geojson(self, filename):
        self.dataframe.to_file(filename, driver='GeoJSON', crs=from_epsg(int(self.crs.split(':')[1])), 
        schema=self.fiona_schema)
        
    def write_geopackage(self,filename,layer):
        self.dataframe.to_file(filename, layer=layer, driver="GPKG", crs=from_epsg(int(self.crs.split(':')[1])), 
        schema=self.fiona_schema)


