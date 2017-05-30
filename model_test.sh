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
copy _albion.formation(hole_id, from_, to_, code, comments) from '/home/vmo/albion/niger_data/albion_formation_3.txt' delimiter ';' csv header;

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

# MINERALIZATION

psql -p 55432 -h localhost niger << EOF

create temporary table mineralization(hole_id varchar, from_ real, from_x real, from_y real, from_z real, to_ real, to_x real, to_y real, to_z real, oc real, accu real, grade real);

select 'load devia';
copy mineralization(hole_id, from_, from_x, from_y, from_z, to_, to_x, to_y, to_z, oc, accu, grade) from '/home/vmo/albion/niger_data/mineralisation_tc300_OC1_Ic1_dev.txt' delimiter ';' csv header;

insert into _albion.mineralization(hole_id, from_, to_, oc, accu, grade) select hole_id, from_, to_, oc, accu, grade from mineralization;

update albion.mineralization set geom=albion.hole_piece(from_, to_, hole_id);

EOF

exit 0

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

psql -h localhost -p 55432 niger << EOF
delete from albion.grid;
update albion.metadata set snap_distance=.3;
EOF
ogr2ogr -a_srs "EPSG:32632" -append -f "PostgreSQL" PG:"dbname=niger port=55432 host=localhost" -nln albion.grid niger_data/grid.shp

# GRAPH TEST

psql -h localhost -p 55432 niger -c "delete from albion.graph cascade;"
psql -h localhost -p 55432 niger -c "vaccuum analyse;"
psql -h localhost -p 55432 niger -c "drop schema if exists albion cascade;"
cp albion.sql /tmp/albion.sql
sed -i "s/{srid}/32632/g" /tmp/albion.sql
psql -h localhost -p 55432 niger -f /tmp/albion.sql

psql -p 55432 -h localhost niger << EOF
\\timing


update albion.metadata set snap_distance=.3, correlation_distance=300;

insert into albion.graph(id) values ('test');

insert into albion.node(graph_id, hole_id, geom) select 'test', hole_id, geom from albion.formation
where code=340 and geom is not null;

select albion.auto_graph('test');
--select count(albion.extend_to_interpolated('test', id)) from albion.grid;
--
--refresh materialized  view albion.dense_grid;
--refresh materialized  view albion.cell;
--refresh materialized  view albion.triangle;
--refresh materialized  view albion.projected_edge;
--refresh materialized  view albion.cell_edge;
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='test'" >  /tmp/test_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('test', id)))) from albion.cell" >  /tmp/test_section_surf.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('test')" >  /tmp/test_section.txt

exit 0

# MINERALIZATION GRAPH

psql -h localhost -p 55432 niger -c "delete from albion.graph cascade;"
psql -h localhost -p 55432 niger -c "vaccuum analyse;"

psql -h localhost -p 55432 niger -c "drop schema if exists albion cascade;"
cp albion.sql /tmp/albion.sql
sed -i "s/{srid}/32632/g" /tmp/albion.sql
psql -h localhost -p 55432 niger -f /tmp/albion.sql

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='min_u1'; 
update albion.metadata set snap_distance=.1, correlation_distance=300;
insert into albion.graph(id) values ('min_u1');
insert into albion.node(graph_id, hole_id, geom) 
select 'min_u1', m.hole_id, m.geom 
from albion.mineralization as m
join albion.formation f on f.hole_id=m.hole_id where f.code=310 and .5*(m.from_+m.to_) >= f.from_ and .5*(m.from_+m.to_) < f.to_;
select albion.auto_graph('min_u1');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='min_u1'" >  /tmp/min_u1_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('min_u1')" >  /tmp/min_u1_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='min_u2'; 
update albion.metadata set snap_distance=.3, correlation_distance=300;
insert into albion.graph(id) values ('min_u2');
insert into albion.node(graph_id, hole_id, geom) 
select 'min_u2', m.hole_id, m.geom 
from albion.mineralization as m
join albion.formation f on f.hole_id=m.hole_id where f.code=320 and .5*(m.from_+m.to_) >= f.from_ and .5*(m.from_+m.to_) < f.to_;
select albion.auto_graph('min_u2');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='min_u2'" >  /tmp/min_u2_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('min_u2')" >  /tmp/min_u2_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='min_u3'; 
update albion.metadata set snap_distance=.3, correlation_distance=300;
insert into albion.graph(id) values ('min_u3');
insert into albion.node(graph_id, hole_id, geom) 
select 'min_u3', m.hole_id, m.geom 
from albion.mineralization as m
join albion.formation f on f.hole_id=m.hole_id where f.code=330 and .5*(m.from_+m.to_) >= f.from_ and .5*(m.from_+m.to_) < f.to_;
select albion.auto_graph('min_u3');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='min_u3'" >  /tmp/min_u3_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('min_u3')" >  /tmp/min_u3_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='min_u4'; 
update albion.metadata set snap_distance=.3, correlation_distance=300;
insert into albion.graph(id) values ('min_u4');
insert into albion.node(graph_id, hole_id, geom) 
select 'min_u4', m.hole_id, m.geom 
from albion.mineralization as m
join albion.formation f on f.hole_id=m.hole_id where f.code=340 and .5*(m.from_+m.to_) >= f.from_ and .5*(m.from_+m.to_) < f.to_;
select albion.auto_graph('min_u4');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='min_u4'" >  /tmp/min_u4_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('min_u4')" >  /tmp/min_u4_section.txt


#exit 0


# GRAPHS


#psql -h localhost  -p 55432 niger -c "refresh materialized view albion.cell"

psql -h localhost -p 55432 niger -c "drop schema if exists albion cascade;"
cp albion.sql /tmp/albion.sql
sed -i "s/{srid}/32632/g" /tmp/albion.sql
psql -h localhost -p 55432 niger -f /tmp/albion.sql

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='tarat_u2'; 
insert into albion.graph(id) values ('tarat_u2');
insert into albion.node(graph_id, hole_id, geom) select 'tarat_u2', hole_id, geom from albion.formation
where code=320 and geom is not null;
select albion.auto_graph('tarat_u2');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='tarat_u2'" >  /tmp/tarat_u2_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('tarat_u1')" >  /tmp/tarat_u1_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='tarat_u1'; 
insert into albion.graph(id) values ('tarat_u1');
insert into albion.node(graph_id, hole_id, geom) select 'tarat_u1', hole_id, geom from albion.formation
where code=310 and geom is not null;
select albion.auto_graph('tarat_u1');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='tarat_u1'" >  /tmp/tarat_u1_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('tarat_u2')" >  /tmp/tarat_u2_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='tarat_u3'; 
insert into albion.graph(id) values ('tarat_u3');
insert into albion.node(graph_id, hole_id, geom) select 'tarat_u3', hole_id, geom from albion.formation
where code=330 and geom is not null;
select albion.auto_graph('tarat_u3');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='tarat_u3'" >  /tmp/tarat_u3_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('tarat_u3')" >  /tmp/tarat_u3_section.txt

psql -p 55432 -h localhost niger << EOF
\\timing
delete from albion.graph casacde where id='tarat_u4'; 
insert into albion.graph(id) values ('tarat_u4');
insert into albion.node(graph_id, hole_id, geom) select 'tarat_u4', hole_id, geom from albion.formation
where code=340 and geom is not null;
select albion.auto_graph('tarat_u4');
EOF

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_)))) from albion.edge where graph_id='tarat_u4'" >  /tmp/tarat_u4_section.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.export_polygons('tarat_u4')" >  /tmp/tarat_u4_section.txt

# ceil and wall

psql -p 55432 -h localhost niger << EOF
refresh materialized  view albion.dense_grid;
refresh materialized  view albion.cell;
refresh materialized  view albion.triangle;
refresh materialized  view albion.projected_edge;
refresh materialized  view albion.cell_edge;
EOF


psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('tarat_u1', id)))) from albion.cell" >  /tmp/tarat_u1_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('tarat_u2', id)))) from albion.cell" >  /tmp/tarat_u2_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('tarat_u3', id)))) from albion.cell" >  /tmp/tarat_u3_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('tarat_u4', id)))) from albion.cell" >  /tmp/tarat_u4_surf.obj

psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('min_u1', id)))) from albion.cell" >  /tmp/min_u1_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('min_u2', id)))) from albion.cell" >  /tmp/min_u2_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('min_u3', id)))) from albion.cell" >  /tmp/min_u3_surf.obj
psql -p 55432 -h localhost niger -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.elementary_volume('min_u4', id)))) from albion.cell" >  /tmp/min_u4_surf.obj




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

