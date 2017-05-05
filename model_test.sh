#!/bin/sh
set -e
#dropdb --if-exists niger
#createdb niger
#psql niger -c 'create extension postgis; create extension "uuid-ossp";'
psql niger -c 'drop schema if exists _albion cascade; drop schema if exists albion cascade;'
cat _albion.sql | sed 's/{srid}/32632/g' |psql niger
cat albion.sql | sed 's/{srid}/32632/g' |psql niger
psql niger -c 'insert into albion.metadata(srid, snap_distance) select 32632, 2;'

time python -m albion.load "dbname=niger" niger_data/albion_collar.txt 
time python -m albion.load "dbname=niger" niger_data/albion_avp.txt 
time python -m albion.load "dbname=niger" niger_data/albion_formation.txt 
time python -m albion.load "dbname=niger" niger_data/albion_resi.txt 
time python -m albion.load "dbname=niger" niger_data/albion_devia.txt

psql niger -c 'select count(1) from albion.deviation'
psql niger -c 'select count(1) from albion.resistivity'
psql niger -c 'select count(1) from albion.mineralization'
psql niger -c 'select count(1) from albion.formation'
psql niger -c 'select count(1) from albion.radiometry'


psql niger -c 'drop schema if exists albion cascade;'
cat albion.sql | sed 's/{srid}/32632/g' |psql niger
psql niger -c 'delete from albion.grid'
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid niger_data/grid.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_1.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_2.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Nord_Grand_Artois_1.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Nord_Grand_Artois_2.shp

psql niger -c 'select albion.update_hole_geom()'
psql niger -c 'refresh materialized view albion.cell'
psql niger -c 'refresh materialized view albion.small_edge'
psql niger -c 'select count(1) from albion.cell'










#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.collar ~/Niger/Collar.shp
