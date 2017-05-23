#!/bin/sh
set -e

python -c "from pglite import start_cluster;start_cluster()"

dropdb -h localhost -p 55432 --if-exists niger
createdb -h localhost -p 55432 niger
psql -h localhost -p 55432 niger << EOF
create extension postgis;
create extension "uuid-ossp"; 
create extension plpython3u;
EOF

cp _albion.sql /tmp/_albion.sql
sed -i "s/{srid}/32632/g" /tmp/_albion.sql
psql -h localhost -p 55432 -tXA niger -f /tmp/_albion.sql

psql -h localhost -tXA -p 55432 niger << EOF
\\timing

select 'load collar';
copy _albion.collar(id, x, y, z, comments) from '/home/vmo/albion/niger_data/albion_collar.txt' delimiter ';' csv header;
update _albion.collar set geom=format('SRID=32632;POINTZ(%s %s %s)', x, y, z)::geometry;

select 'create hole';
insert into _albion.hole(id, collar_id) select id, id from _albion.collar;

select 'load devia';
copy _albion.deviation(hole_id, from_, deep, azimuth) from '/home/vmo/albion/niger_data/albion_devia.txt' delimiter ';' csv header;

select 'load avp';
copy _albion.radiometry(hole_id, from_, to_, gamma) from '/home/vmo/albion/niger_data/albion_avp.txt' delimiter ';' csv header;

select 'load formation';
copy _albion.formation(hole_id, from_, to_, code, comments) from '/home/vmo/albion/niger_data/albion_formation.txt' delimiter ';' csv header;

select 'load resi';
copy _albion.resistivity(hole_id, from_, to_, rho) from '/home/vmo/albion/niger_data/albion_resi.txt' delimiter ';' csv header;

select 'set hole depth';
with dep as (
    select hole_id, max(to_) as mx
        from (
            select hole_id, max(to_) as to_ from _albion.radiometry group by hole_id
            union all
            select hole_id, max(to_) as to_ from _albion.resistivity group by hole_id
            union all
            select hole_id, max(to_) as to_ from _albion.formation group by hole_id
            union all
            select hole_id, max(to_) as to_ from _albion.lithology group by hole_id
            union all
            select hole_id, max(to_) as to_ from _albion.facies group by hole_id
            union all
            select hole_id, max(to_) as to_ from _albion.mineralization group by hole_id
                ) as t
    group by hole_id
)
update _albion.hole as h set depth_=d.mx
from dep as d where h.id=d.hole_id
;

EOF

psql -h localhost -p 55432 niger -c "drop schema if exists albion cascade;"
cp albion.sql /tmp/albion.sql
sed -i "s/{srid}/32632/g" /tmp/albion.sql
psql -h localhost -p 55432 niger -f /tmp/albion.sql

psql -h localhost -p 55432 niger << EOF
\\timing
select 'compute hole geom';
update albion.hole set geom=albion.hole_geom(id);
select 'compute resistivity geom';
update albion.resistivity set geom=albion.hole_piece(from_, to_, hole_id);
select 'compute formation geom';
update albion.formation set geom=albion.hole_piece(from_, to_, hole_id);
select 'compute radiometry geom';
update albion.radiometry set geom=albion.hole_piece(from_, to_, hole_id);
EOF

exit 0


# GRAPH TEST

psql -h localhost -p 55432 niger << EOF
delete from albion.grid;
update albion.metadata set snap_distance=1;
EOF
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger port=55432 host=localhost" -nln albion.grid niger_data/grid.shp

#psql -h localhost  -p 55432 niger -c "refresh materialized view albion.cell"


psql -h localhost -p 55432 niger -c "drop schema if exists albion cascade;"
cp albion.sql /tmp/albion.sql
sed -i "s/{srid}/32632/g" /tmp/albion.sql
psql -h localhost -p 55432 niger -f /tmp/albion.sql

psql -p 55432 -h localhost niger << EOF
\\timing

--update albion.metadata set current_section='26e91cb5-e286-4724-8e97-49e9614caa65';

delete from albion.graph cascade;

insert into albion.graph(id) values ('tarat_u1');

insert into albion.node(graph_id, hole_id, geom) select 'tarat_u1', hole_id, geom from albion.formation
where code=310 and geom is not null;

select count(albion.auto_connect('tarat_u1', id)) from albion.grid;

select count(albion.auto_ceil_and_wall('tarat_u1', id)) from albion.grid;

    select count(albion.fix_column('tarat_u1', geom)) 
from (
    select (st_dumppoints(st_force2d(geom))).geom as geom
    from albion.grid
) as t
where not exists (select 1 from albion.collar as c where st_intersects(c.geom, t.geom))
;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge('tarat_u1', ceil_, wall_)))) from albion.edge where graph_id='tarat_u1'" >  /tmp/tarat_u1_section.obj

psql -p 55432 -h localhost niger << EOF
\\timing

insert into albion.graph(id) values ('tarat_u2');
insert into albion.node(graph_id, hole_id, geom) select 'tarat_u2', hole_id, geom from albion.formation
where code=310 and geom is not null;
select count(albion.auto_connect('tarat_u2', id)) from albion.grid;
select count(albion.auto_ceil_and_wall('tarat_u2', id)) from albion.grid;
    select count(albion.fix_column('tarat_u2', geom)) 
from (
    select (st_dumppoints(st_force2d(geom))).geom as geom
    from albion.grid
) as t
where not exists (select 1 from albion.collar as c where st_intersects(c.geom, t.geom))
;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge('tarat_u2', ceil_, wall_)))) from albion.edge where graph_id='tarat_u2'" >  /tmp/tarat_u2_section.obj


exit 0

#python -c "from pglite import stop_cluster;stop_cluster()"



#with to_merge as (
#select first_value(id) over w as first_id, lag(to_) over w as merge_to, id as merge_id, abs(lag(to_)over w -from_) < .1 as overlap
#    from albion.formation
#    window w as (partition by hole_id, code order by from_)
#)
#update albion.formation as f set to_=greatest(merge_to, f.to_)
#from to_merge as m
#where f.id=m.first_id and m.merge_id!=f.id
#and overlap
#;
#update albion.formation set geom=albion.hole_piece(from_, to_, hole_id);

