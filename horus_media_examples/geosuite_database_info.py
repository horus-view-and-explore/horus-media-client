import sys
import horus_spatialite
from os import path

sqlite_file = "path_to_your_sqlite_database"

if len(sys.argv) > 1:
    sqlite_file = sys.argv[1]


if not path.exists(sqlite_file):
    print("Database file: [", sqlite_file, "] could not be found.")
    exit()

db = horus_spatialite.Spatialite(sqlite_file)

db.open()
db.resolve()
db.show_info()

# Iterate over data
for row in db.query():
    for fieldname, info in db.get_field_names_map().items():
        # print(row[info.idx])
        pass


db.close()
