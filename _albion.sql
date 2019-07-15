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

create type interpolation_method as enum ('balanced_tangential');

create table _albion.graph(
    id varchar primary key default _albion.unique_id()::varchar,
    parent varchar references _albion.graph(id) on delete set null on update cascade)
;

create table _albion.metadata(
    id integer primary key default 1 check (id=1), -- only one entry in table
    srid integer not null references public.spatial_ref_sys(srid),
    close_collar_distance real not null default 10,
    snap_distance real not null default 1,
    precision real default .01,
    interpolation interpolation_method default 'balanced_tangential',
    end_angle real default 5.0,
    correlation_distance real default 200,
    correlation_angle real default 5.0,
    parent_correlation_angle real default 1.0,
    end_node_relative_distance real default .3)
    end_node_thickness real default 1)
;

insert into _albion.metadata(srid) select $SRID
;

create table _albion.hole(
    id varchar primary key default _albion.unique_id()::varchar,
    date_ varchar,
    depth_ real not null,
        check(depth_ > 0),
    x double precision not null,
    y double precision not null,
    z double precision not null,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

alter table _albion.hole add constraint hole_geom_length_chk check (geom is null or abs(st_3dlength(geom) - depth_) <= 1e-3)
;

create index hole_geom_idx on _albion.hole using gist(geom)
;

create table _albion.deviation(
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real,
    dip real,
    azimuth real)
;


-------------------------------------------------------------------------------
-- GRAPH
-------------------------------------------------------------------------------

create table _albion.node(
    id varchar primary key,
    graph_id varchar not null references _albion.graph(id) on delete cascade on update cascade,
        unique(id, graph_id),
    hole_id varchar references _albion.hole(id) on delete cascade,
    from_ real,
    to_ real,
    geom geometry('LINESTRINGZ', $SRID) not null check (st_numpoints(geom)=2),
    parent varchar references _albion.node(id) on delete set null on update cascade
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

create table _albion.edge(
    id varchar primary key,
    start_ varchar not null ,
        foreign key (graph_id, start_) references _albion.node(graph_id, id) on delete cascade on update cascade,
    end_ varchar not null,
        foreign key (graph_id, end_) references _albion.node(graph_id, id) on delete cascade on update cascade,
        unique (start_, end_),
        check (start_ < end_),
    graph_id varchar references _albion.graph(id) on delete cascade,
    geom geometry('LINESTRINGZ', $SRID) not null check (st_isvalid(geom))
)
;

create index edge_geom_idx on _albion.edge using gist(geom)
;

create index edge_graph_id_idx on _albion.edge(graph_id)
;

create index edge_start__idx on _albion.edge(start_)
;

create index edge_end__idx on _albion.edge(end_)
;

alter table _albion.edge alter column id set default _albion.unique_id()::varchar
;

create table _albion.cell(
    id varchar primary key,
    a varchar not null references _albion.hole(id) on delete cascade on update cascade,
    b varchar not null references _albion.hole(id) on delete cascade on update cascade,
    c varchar not null references _albion.hole(id) on delete cascade on update cascade,
    geom geometry('POLYGON', $SRID) not null check(st_isvalid(geom) and st_numpoints(geom)=4)
)
;

create index cell_geom_idx on _albion.cell using gist(geom)
;

create index volume_cell_a_idx on _albion.cell(a)
;

create index volume_cell_b_idx on _albion.cell(b)
;

create index volume_cell_c_idx on _albion.cell(c)
;

alter table _albion.cell alter column id set default _albion.unique_id()::varchar
;

create table _albion.group(
    id integer primary key
)
;

create table _albion.section(
    id varchar primary key,
    anchor geometry('LINESTRING', $SRID) not null check(st_numpoints(anchor)=2),
    geom geometry('LINESTRING', $SRID) not null,
    scale real not null default 1,
    group_id integer references _albion.group(id) on delete set null on update cascade
)
;

alter table _albion.section alter column id set default _albion.unique_id()::varchar
;

create table _albion.volume(
    id varchar primary key,
    graph_id varchar not null references _albion.graph(id) on delete cascade on update cascade,
    cell_id varchar not null references _albion.cell(id) on delete cascade on update cascade,
    triangulation geometry('MULTIPOLYGONZ', $SRID) not null
);

create index volume_graph_id_idx on _albion.volume(graph_id)
;

create index volume_cell_id_idx on _albion.volume(cell_id)
;

alter table _albion.volume alter column id set default _albion.unique_id()::varchar
;

create table _albion.group_cell(
    group_id integer not null references _albion.group(id) on delete cascade on update cascade,
    cell_id varchar not null references _albion.cell(id) on delete cascade on update cascade,
    section_id varchar not null references _albion.section(id) on delete cascade on update cascade,
    unique(section_id, cell_id)
)
;

create index group_cell_cell_id_idx on _albion.group_cell(cell_id)
;

create index group_cell_groupe_id_idx on _albion.group_cell(group_id)
;


create table _albion.end_node(
    id varchar primary key,
    geom geometry('LINESTRINGZ', $SRID) not null check (st_numpoints(geom)=2),
    node_id varchar not null references _albion.node(id) on delete cascade on update cascade,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    graph_id varchar references _albion.graph(id) on delete cascade
)
;

create index end_node_geom_idx on _albion.end_node using gist(geom)
;

alter table _albion.end_node alter column id set default _albion.unique_id()::varchar
;

