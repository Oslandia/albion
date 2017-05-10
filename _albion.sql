-- private schema to store data
create schema _albion
;

create type interpolation_method as enum ('balanced_tangential');

create table _albion.grid(
    id varchar primary key default uuid_generate_v4()::varchar,
    geom geometry('LINESTRING', {srid}))
;

create index grid_geom_idx on _albion.grid using gist(geom)
;

alter table _albion.grid alter column id set default uuid_generate_v4()::varchar
;

create table _albion.metadata(
    id integer primary key default 1 check (id=1), -- only one entry in table
    srid integer not null references public.spatial_ref_sys(srid),
    current_section varchar references _albion.grid(id) on delete set null on update cascade,
    snap_distance real not null default 5,
    origin geometry('POINTZ', {srid}) not null default 'SRID={srid}; POINTZ(0 0 0)'::geometry,
    precision real,
    interpolation interpolation_method defaut 'balanced_tangential')
;

create table _albion.collar(
    id varchar primary key default uuid_generate_v4()::varchar,
    geom geometry('POINTZ', {srid}) not null,
    comments varchar)
;

create index collar_geom_idx on _albion.collar using gist(geom)
;

create table _albion.hole(
    id varchar primary key,
    collar_id varchar unique not null references _albion.collar(id),
    geom geometry('LINESTRINGZ', {srid}))
;

create index hole_geom_idx on _albion.hole using gist(geom)
;

alter table _albion.hole alter column id set default uuid_generate_v4()::varchar
;


create table _albion.deviation(
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    deep real,
    azimuth real)
;

create index deviation_hole_id_idx on _albion.deviation(hole_id)
;

create table _albion.radiometry(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    gamma real,
    geom geometry('LINESTRINGZ', {srid}))
;

create index radiometry_geom_idx on _albion.radiometry using gist(geom)
;

alter table _albion.radiometry alter column id set default uuid_generate_v4()::varchar
;

create table _albion.resistivity(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    rho real,
    geom geometry('LINESTRINGZ', {srid}))
;

create index resistivity_geom_idx on _albion.resistivity using gist(geom)
;

alter table _albion.resistivity alter column id set default uuid_generate_v4()::varchar
;


create table _albion.formation(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', {srid}))
;

create index formation_geom_idx on _albion.formation using gist(geom)
;

alter table _albion.formation alter column id set default uuid_generate_v4()::varchar
;

create table _albion.lithology(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', {srid}))
;

create index lithology_geom_idx on _albion.lithology using gist(geom)
;

alter table _albion.lithology alter column id set default uuid_generate_v4()::varchar
;

create table _albion.facies(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', {srid}))
;

create index facies_geom_idx on _albion.facies using gist(geom)
;

alter table _albion.facies alter column id set default uuid_generate_v4()::varchar
;

create table _albion.mineralization(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id),
    from_ real,
    to_ real,
    oc real,
    accu real,
    grade real,
    geom geometry('LINESTRINGZ', {srid}))
;

create index mineralization_geom_idx on _albion.mineralization using gist(geom)
;

alter table _albion.mineralization alter column id set default uuid_generate_v4()::varchar
;


