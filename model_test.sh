#!/bin/sh
set -e
#dropdb --if-exists niger
#createdb niger
#psql niger -c 'create extension postgis; create extension "uuid-ossp";'
psql niger -c 'drop schema if exists _albion cascade; drop schema if exists albion cascade;'
cat model.sql | sed 's/{srid}/32632/g' |psql niger
psql niger -c 'insert into _albion.metadata(srid, snap_distance) select 32632, 2;'

ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.collar ~/Niger/Collar.shp
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_1.shp
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_2.shp

psql niger -c 'select count(1) from albion.grid'
psql niger -c 'refresh materialized view albion.cell;'

psql niger -c 'select count(1) from albion.cell'
