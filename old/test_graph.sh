psql -p 55432 -h localhost test_project -c 'drop schema albion cascade'
cat albion.sql | sed "s/{srid}/32632/g" |psql -p 55432 -h localhost test_project

psql -p 55432 -h localhost test_project -c 'drop table _albion.tarat_u1_node cascade'
psql -p 55432 -h localhost test_project -c 'drop table _albion.tarat_u2_node cascade'
psql -p 55432 -h localhost test_project -c 'drop table _albion.tarat_u3_node cascade'
psql -p 55432 -h localhost test_project -c 'drop table _albion.tchinezogue_node cascade'

cat _albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u1/g"  | psql -p 55432 -h localhost test_project
cat _albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u2/g"  | psql -p 55432 -h localhost test_project
cat _albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u3/g"  | psql -p 55432 -h localhost test_project
cat _albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tchinezogue/g"  | psql -p 55432 -h localhost test_project

cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u1/g"  | psql -p 55432 -h localhost test_project
cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u2/g"  | psql -p 55432 -h localhost test_project
cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tarat_u3/g"  | psql -p 55432 -h localhost test_project
cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/tchinezogue/g"  | psql -p 55432 -h localhost test_project

psql -p 55432 -h localhost test_project << EOF
delete from albion.tarat_u1_node;

insert into albion.tarat_u1_node(id, hole_id, geom) select id, hole_id, geom from albion.formation
where code=310 and geom is not null;

select count(albion.auto_connect('tarat_u1', id)) from albion.grid;
select count(albion.auto_ceil_and_wall('tarat_u1', id)) from albion.grid;

refresh materialized view albion.tarat_u1_inter_edge;
refresh materialized view albion.tarat_u1_fix_me;

select count(albion.fix_column('tarat_u1', geom)) from albion.tarat_u1_fix_me;

refresh materialized view albion.tarat_u1_ceil;
refresh materialized view albion.tarat_u1_wall;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u1_ceil" > /tmp/tarat_u1_ceil.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u1_wall" > /tmp/tarat_u1_wall.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge('tarat_u1', id)))) from albion.tarat_u1_edge" >  /tmp/tarat_u1_section.obj

exit 0





psql -p 55432 -h localhost test_project << EOF
delete from albion.tarat_u2_node;

insert into albion.tarat_u2_node(id, hole_id, geom) select id, hole_id, geom from albion.formation
where code=320 and geom is not null;

select count(albion.auto_connect('tarat_u2', id)) from albion.grid;
select count(albion.auto_ceil_and_wall('tarat_u2', id)) from albion.grid;

refresh materialized view albion.tarat_u2_inter_edge;
refresh materialized view albion.tarat_u2_fix_me;

select count(albion.fix_column('tarat_u2', geom)) from albion.tarat_u2_fix_me;

refresh materialized view albion.tarat_u2_ceil;
refresh materialized view albion.tarat_u2_wall;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u2_ceil" > /tmp/tarat_u2_ceil.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u2_wall" > /tmp/tarat_u2_wall.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge('tarat_u2', id)))) from albion.tarat_u2_edge" >  /tmp/tarat_u2_section.obj


psql -p 55432 -h localhost test_project << EOF
delete from albion.tarat_u3_node;

insert into albion.tarat_u3_node(id, hole_id, geom) select id, hole_id, geom from albion.formation
where code=330 and geom is not null;

select count(albion.auto_connect('tarat_u3', id)) from albion.grid;
select count(albion.auto_ceil_and_wall('tarat_u3', id)) from albion.grid;

refresh materialized view albion.tarat_u3_inter_edge;
refresh materialized view albion.tarat_u3_fix_me;

select count(albion.fix_column('tarat_u3', geom)) from albion.tarat_u3_fix_me;

refresh materialized view albion.tarat_u3_ceil;
refresh materialized view albion.tarat_u3_wall;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u3_ceil" > /tmp/tarat_u3_ceil.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tarat_u3_wall" > /tmp/tarat_u3_wall.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collectionhomogenize(st_collect(albion.triangulate_edge('tarat_u3', id)))) from albion.tarat_u3_edge" >  /tmp/tarat_u3_section.obj


psql -p 55432 -h localhost test_project << EOF
delete from albion.tchinezogue_node;

insert into albion.tchinezogue_node(id, hole_id, geom) select id, hole_id, geom from albion.formation
where code>=400 and code<500 and geom is not null;

select count(albion.auto_connect('tchinezogue', id)) from albion.grid;
select count(albion.auto_ceil_and_wall('tchinezogue', id)) from albion.grid;

refresh materialized view albion.tchinezogue_inter_edge;
refresh materialized view albion.tchinezogue_fix_me;

select count(albion.fix_column('tchinezogue', geom)) from albion.tchinezogue_fix_me;

refresh materialized view albion.tchinezogue_ceil;
refresh materialized view albion.tchinezogue_wall;

EOF

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tchinezogue_ceil" > /tmp/tchinezogue_ceil.obj

psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.tchinezogue_wall" > /tmp/tchinezogue_wall.obj






#cat albion_graph.sql | sed "s/{srid}/32632/g;s/{name}/test_graph/g"  | psql -p 55432 -h localhost test_project
#
#psql -p 55432 -h localhost test_project << EOF
#delete from albion.test_graph_edge;
#select count(albion.auto_connect('test_graph', id)) from albion.grid;
#select count(albion.auto_ceil_and_wall('test_graph', id)) from albion.grid;
#
#refresh materialized view albion.test_graph_inter_edge;
#refresh materialized view albion.test_graph_fix_me;
#
#select count(albion.fix_column('test_graph', geom)) from albion.test_graph_fix_me;
#
#refresh materialized view albion.test_graph_ceil;
#refresh materialized view albion.test_graph_wall;
#
#EOF
#
#psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.test_graph_ceil" > /tmp/ceil.obj
#
#psql -p 55432 -h localhost test_project -tXA -c "select albion.to_obj(st_collect(geom)) from albion.test_graph_wall" > /tmp/wall.obj




