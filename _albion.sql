-- private schema to store data
create schema _albion
;

create table _albion.grid(
    id varchar primary key default uuid_generate_v4()::varchar,
    geom geometry('LINESTRING', {srid}))
;

create index grid_geom_idx on _albion.grid using gist(geom)
;

create table _albion.metadata(
    id integer primary key default 1 check (id=1), -- only one entry in table
    srid integer not null references public.spatial_ref_sys(srid),
    current_section varchar references _albion.grid(id),
    snap_distance real not null default 5,
    origin geometry('POINTZ', {srid}) not null default 'SRID={srid}; POINTZ(0 0 0)'::geometry,
    precision real)
;

create table _albion.collar(
    id varchar primary key default uuid_generate_v4()::varchar,
    geom geometry('POINTZ', {srid}) not null,
    comments varchar)
;
create index collar_geom_idx on _albion.collar using gist(geom)
;

create table _albion.hole(
    id varchar primary key default uuid_generate_v4()::varchar,
    collar_id varchar unique not null references _albion.collar(id),
    geom geometry('LINESTRINGZ', {srid}))
;

create table _albion.deviation(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    deep real,
    azimuth real)
;

--create index deviation_hole_id_idx on _albion.deviation(hole_id)
--;

create table _albion.radiometry(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    gamma real)
;

create table _albion.resistivity(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    rho real)
;

create table _albion.formation(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar)
;

create table _albion.lithology(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar)
;

create table _albion.mineralization(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    oc real,
    accu real,
    grade real)
;

