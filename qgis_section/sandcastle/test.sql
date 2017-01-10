create table well(
    id integer primary key,
    name text
);
select AddGeometryColumn('well', 'geom', 2154, 'LINESTRING', 'XYZ'); 

insert into well(name, geom) values ('toto', GeomFromText('LINESTRING Z(0 0 0.1, 0 0 -10, 0 0 -20, 0 0 -30, 0 0 -40)', 2154));
insert into well(name, geom) values ('tata', GeomFromText('LINESTRING Z(10 0 5, 10 0 -10, 10 1 -20, 10 1 -30, 10 1 -60)', 2154));
insert into well(name, geom) values ('titi', GeomFromText('LINESTRING Z(10 10 0, 10 10 -10, 10 10 -20, 10 10 -30, 10 15 -40)', 2154));


create table section(
    id integer primary key
);
select AddGeometryColumn('section', 'geom', 2154, 'LINESTRING', 'XY'); 

insert into section(geom) values (GeomFromText('LINESTRING(0 0.5, 5 -1, 11 1.2 )', 2154));


