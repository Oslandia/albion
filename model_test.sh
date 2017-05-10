#!/bin/sh
set -e
dropdb --if-exists niger
createdb niger
psql niger -c "create extension postgis; create extension \"uuid-ossp\";"
psql niger -c "drop schema if exists _albion cascade; drop schema if exists albion cascade;"
cat _albion.sql | sed "s/{srid}/32632/g" |psql niger
cat albion.sql | sed "s/{srid}/32632/g" |psql niger
psql niger -c "insert into albion.metadata(srid, snap_distance) select 32632, 2;"

time python -m albion.load "dbname=niger" niger_data/albion_collar.txt 
time python -m albion.load "dbname=niger" niger_data/albion_devia.txt

psql niger -c "select albion.update_hole_geom()"

time python -m albion.load "dbname=niger" niger_data/albion_avp.txt 
time python -m albion.load "dbname=niger" niger_data/albion_formation.txt 
time python -m albion.load "dbname=niger" niger_data/albion_resi.txt 



psql niger -c "drop schema if exists albion cascade;"
cat albion.sql | sed "s/{srid}/32632/g" |psql niger
psql niger -c "delete from albion.grid"
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid niger_data/grid.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_1.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Grille_Droite_2.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Nord_Grand_Artois_1.shp
#ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger" -nln albion.grid ~/Niger/Nord_Grand_Artois_2.shp

psql niger -c "refresh materialized view albion.cell"
psql niger -c "refresh materialized view albion.small_edge"


psql niger -c "drop schema if exists albion cascade;"
cat albion.sql | sed "s/{srid}/32632/g" |psql niger
cat _albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/test/g" | psql niger
cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/test/g" | psql niger
psql niger << EOF
insert into albion.test_node(hole_id, geom)
select hole_id, geom 
from albion.formation
where (code=310 or code=330) and geom is not null;

select albion.auto_connect('test', '8c9819bb-b674-4f22-8cca-a360792622b5');

select albion.auto_ceil_and_wall('test', '8c9819bb-b674-4f22-8cca-a360792622b5');

select albion.auto_connect('test', id) from albion.grid;

select albion.auto_ceil_and_wall('test', id) from albion.grid;
EOF


#insert into albion.tarat_u1_node(hole_id, geom)
#select 
#    hole_id, 
#    st_makeline(st_3dlineinterpolatepoint(h.geom, f.from_/st_3dlength(h.geom)),
#    st_3dlineinterpolatepoint(h.geom, least(1,f.to_/st_3dlength(h.geom))))
#from albion.formation as f join albion.hole as h on h.id=f.hole_id
#where f.code=310
#and h.geom is not null
#and f.from_/st_3dlength(h.geom) < 1
#and f.from_ < f.to_;
#
#insert into albion.tarat_u2_node(hole_id, geom)
#select 
#    hole_id, 
#    st_makeline(st_3dlineinterpolatepoint(h.geom, f.from_/st_3dlength(h.geom)),
#    st_3dlineinterpolatepoint(h.geom, least(1,f.to_/st_3dlength(h.geom))))
#from albion.formation as f join albion.hole as h on h.id=f.hole_id
#where f.code=320
#and h.geom is not null
#and f.from_/st_3dlength(h.geom) < 1
#and f.from_ < f.to_;
#
#insert into albion.tarat_u3_node(hole_id, geom)
#select 
#    hole_id, 
#    st_makeline(st_3dlineinterpolatepoint(h.geom, f.from_/st_3dlength(h.geom)),
#    st_3dlineinterpolatepoint(h.geom, least(1,f.to_/st_3dlength(h.geom))))
#from albion.formation as f join albion.hole as h on h.id=f.hole_id
#where f.code=330
#and h.geom is not null
#and f.from_/st_3dlength(h.geom) < 1
#and f.from_ < f.to_;



