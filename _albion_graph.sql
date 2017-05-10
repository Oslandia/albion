drop table if exists _albion.{name}_ceil_edge cascade;
drop table if exists _albion.{name}_wall_edge cascade;
drop table if exists _albion.{name}_edge cascade;
drop table if exists _albion.{name}_node cascade;

create table _albion.{name}_node(
    id varchar primary key,
    hole_id varchar references _albion.hole(id),
    geom geometry('LINESTRINGZ', {srid}) not null check (st_isvalid(geom) and st_numpoints(geom)=2)
)
;

alter table _albion.{name}_node alter column id set default uuid_generate_v4()::varchar
;

create table _albion.{name}_edge(
    id varchar primary key,
    start_ varchar references _albion.{name}_node(id) on delete cascade,
    end_ varchar references _albion.{name}_node(id) on delete cascade,
        unique (start_, end_),
    grid_id varchar references _albion.grid(id),
    geom geometry('LINESTRINGZ', {srid}) not null check (st_isvalid(geom))
)
;

alter table _albion.{name}_edge alter column id set default uuid_generate_v4()::varchar
;

create table _albion.{name}_wall_edge(
    id varchar primary key references _albion.{name}_edge(id) on delete cascade,
    grid_id varchar references _albion.grid(id),
    geom geometry('LINESTRINGZ', {srid}) not null check (st_isvalid(geom))
)
;

create table _albion.{name}_ceil_edge(
    id varchar primary key references _albion.{name}_edge(id) on delete cascade,
    grid_id varchar references _albion.grid(id),
    geom geometry('LINESTRINGZ', {srid}) not null check (st_isvalid(geom))
)
;


