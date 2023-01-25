# Usage

## Setup
Install Docker Desktop for Windows.

Update data\input\db.conf and data\input\server.conf replacing localhost with your host IP.

Update the PostgreSQL configuration to allow connections by your host IP.


## Start environment
```bash
cd ./snapshots
docker-compose run --rm snapshots
```


```bash
python -m horus_media_examples.snapshots
```

```bash
python -m horus_media_examples.recordings_tool --db-file --s-file
```

```bash
python -m horus_media_examples.snapshots --db-file --s-file --sqlite-db ./rotterdam_360.sqlite
```
