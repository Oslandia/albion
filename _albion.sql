-------------------------------------------------------------------------------
-- PRIVATE SCHEMA TO STORE DATA
-------------------------------------------------------------------------------
create schema _albion
;

create sequence _albion.unique_name_seq
;

create or replace function _albion.unique_id()
returns varchar
language plpgsql volatile
as
$$
    begin
        return nextval('_albion.unique_name_seq')::varchar;
    end
$$
;

create or replace function _albion.current_graph()
returns varchar
language plpgsql stable
as
$$
    begin
        return (select current_graph from _albion.metadata);
    end;
$$
;

create type interpolation_method as enum ('balanced_tangential');

create table _albion.grid(
    id varchar primary key default _albion.unique_id()::varchar,
    geom geometry('LINESTRING', $SRID))
;

create table _albion.graph(
    id varchar primary key default _albion.unique_id()::varchar,
    parent varchar references _albion.graph(id) on delete set null on update cascade)
;

create index grid_geom_idx on _albion.grid using gist(geom)
;

alter table _albion.grid alter column id set default _albion.unique_id()::varchar
;

create table _albion.metadata(
    id integer primary key default 1 check (id=1), -- only one entry in table
    srid integer not null references public.spatial_ref_sys(srid),
    current_section varchar references _albion.grid(id) on delete set null on update cascade,
    current_graph varchar references _albion.graph(id) on delete set null on update cascade,
    snap_distance real not null default 1,
    precision real default .01,
    interpolation interpolation_method default 'balanced_tangential',
    end_distance real default 25,
    correlation_distance real default 200,
    correlation_slope real default 1.0/100)
;

insert into _albion.metadata(srid) select $SRID
;

create table _albion.collar(
    id varchar primary key default _albion.unique_id()::varchar,
    x real,
    y real,
    z real,
    date_ varchar,
    geom geometry('POINTZ', $SRID),
    comments varchar)
;

create index collar_geom_idx on _albion.collar using gist(geom)
;

create table _albion.hole(
    id varchar primary key,
    collar_id varchar unique not null references _albion.collar(id) on delete cascade on update cascade,
    depth_ real,
    geom geometry('LINESTRINGZ', $SRID))
;

create index hole_geom_idx on _albion.hole using gist(geom)
;

create index hole_collar_id_idx on _albion.hole(collar_id)
;


alter table _albion.hole alter column id set default _albion.unique_id()::varchar
;

-------------------------------------------------------------------------------
-- MEASURES
-------------------------------------------------------------------------------

create table _albion.deviation(
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    dip real,
    azimuth real)
;

create index deviation_hole_id_idx on _albion.deviation(hole_id)
;

create table _albion.radiometry(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    gamma real,
    geom geometry('LINESTRINGZ', $SRID))
;

create index radiometry_geom_idx on _albion.radiometry using gist(geom)
;

create index radiometry_hole_id_idx on _albion.radiometry(hole_id)
;

alter table _albion.radiometry alter column id set default _albion.unique_id()::varchar
;

create table _albion.resistivity(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    rho real,
    geom geometry('LINESTRINGZ', $SRID))
;

create index resistivity_geom_idx on _albion.resistivity using gist(geom)
;

create index resistivity_hole_id_idx on _albion.resistivity(hole_id)
;

alter table _albion.resistivity alter column id set default _albion.unique_id()::varchar
;


create table _albion.formation(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

create index formation_geom_idx on _albion.formation using gist(geom)
;

create index  formation_hole_id_idx on _albion.formation(hole_id)
;

alter table _albion.formation alter column id set default _albion.unique_id()::varchar
;

create table _albion.lithology(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

create index lithology_geom_idx on _albion.lithology using gist(geom)
;

create index  lithology_hole_id_idx on _albion.lithology(hole_id)
;

alter table _albion.lithology alter column id set default _albion.unique_id()::varchar
;

create table _albion.facies(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    code integer,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

create index facies_geom_idx on _albion.facies using gist(geom)
;

create index facies_hole_id_idx on _albion.facies(hole_id)
;

alter table _albion.facies alter column id set default _albion.unique_id()::varchar
;

create table _albion.mineralization(
    id varchar primary key,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    to_ real,
    oc real,
    accu real,
    grade real,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

create index mineralization_geom_idx on _albion.mineralization using gist(geom)
;

create index mineralization_hole_id_idx on _albion.mineralization(hole_id)
;


alter table _albion.mineralization alter column id set default _albion.unique_id()::varchar
;

-------------------------------------------------------------------------------
-- GRAPH
-------------------------------------------------------------------------------

create table _albion.node(
    id varchar primary key,
    graph_id varchar references _albion.graph(id) on delete cascade on update cascade,
        unique(id, graph_id),
    hole_id varchar references _albion.hole(id),
    geom geometry('LINESTRINGZ', $SRID) not null check (st_numpoints(geom)=2)
)
;

create index node_geom_idx on _albion.node using gist(geom)
;

create index node_graph_id_idx on _albion.node(graph_id)
;

create index node_hole_id_idx on _albion.node(hole_id)
;

alter table _albion.node alter column id set default _albion.unique_id()::varchar
;

alter table _albion.node alter column graph_id set default _albion.current_graph(); 
;

create table _albion.edge(
    id varchar primary key,
    graph_id varchar not null,
        unique(id, graph_id),
    start_ varchar,
        foreign key (graph_id, start_) references _albion.node(graph_id, id) on delete cascade on update cascade,
    end_ varchar references _albion.node(id) on delete cascade,
        foreign key (graph_id, end_) references _albion.node(graph_id, id) on delete cascade on update cascade,
        unique (start_, end_),
    grid_id varchar references _albion.grid(id) on delete cascade,
    geom geometry('LINESTRINGZ', $SRID) not null check (st_isvalid(geom)),
    ceil_ geometry('LINESTRINGZ', $SRID),
    wall_ geometry('LINESTRINGZ', $SRID)
)
;

create index edge_geom_idx on _albion.edge using gist(geom)
;

create index edge_graph_id_idx on _albion.edge(graph_id)
;

create index edge_grid_id_idx on _albion.edge(grid_id)
;

create index edge_start__idx on _albion.edge(start_)
;

create index edge_end__idx on _albion.edge(end_)
;

alter table _albion.edge alter column id set default _albion.unique_id()::varchar
;

alter table _albion.edge alter column graph_id set default _albion.current_graph(); 
;

