-- private schema to store data
create schema _albion
;

create table _albion.grid(
    id serial primary key,
    geom geometry('LINESTRING', {srid}))
;
create index grid_geom_idx on _albion.grid using gist(geom)
;

create table _albion.metadata(
    id integer primary key default 1 check (id=1), -- only one entry in table
    srid integer not null references public.spatial_ref_sys(srid),
    current_section integer references _albion.grid(id),
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
    id varchar primary key,
    collar_id varchar unique not null references _albion.collar(id),
    geom geometry('LINESTRINGZ', {srid}))
;

create table _albion.deviation(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    deep real,
    azimuth real)
;

create table _albion.radiometry(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    to_ real,
    gamma real)
;

create table _albion.resistivity(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    to_ real,
    rho real)
;

create table _albion.formation(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar)
;

create table _albion.lithology(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    to_ real,
    code integer,
    comments varchar)
;

create table _albion.mineralization(
    hole_id varchar unique not null references _albion.hole(id),
    from_ real,
    to_ real,
    oc real,
    accu real,
    grade real)
;

-- public schema for database interface
create schema albion
;

-- create function albion.create_holes()
-- returns boolean
-- language plpgsql
-- $$
--     begin
--         with delta as (
--             select hole_id,
--             0.5*(from_ - coalesce(lag(from_), 0)) * (sin(coalesce(lag(deep), 0)) * cos(coalesce(lag(azimuth), 0))+ sin(deep) * cos(azimuth)) over (partition by hole_id order by from_) as y,
--             0.5*(from_ - coalesce(lag(from_), 0)) * (sin(coalesce(lag(deep), 0)) * sin(coalesce(lag(azimuth), 0))+ sin(deep) * sin(azimuth)) over (partition by hole_id order by from_) as x,
--             0.5*(from_ - coalesce(lag(from_), 0)) * (sin(coalesce(lag(deep), 0)) + cos(deep)) over (partition by hole_id order by from_) as z
--             from _albion.deviation 
--         )
--         select * from delta;
--         return 't'::boolean;
--     end;
-- $$
-- ;

create materialized view albion.cell
as
with collec as (
    select
            (st_dump(
                coalesce(
                    st_split(
                        a.geom,
                        (select st_collect(geom)
                            from _albion.grid as b
                            where a.id!=b.id and st_intersects(a.geom, b.geom)
                            and st_dimension(st_intersection(a.geom, b.geom))=0)),
                    a.geom)
        )).geom as geom
    from _albion.grid as a
),
poly as (
    select (st_dump(st_polygonize(geom))).geom as geom from collec
)
select row_number() over() as id, geom::geometry('POLYGON', {srid}) from poly where geom is not null
;

create view albion.grid as
select id, geom, st_azimuth(st_startpoint(geom), st_endpoint(geom)) as azimuth
from _albion.grid
;

create function albion.grid_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        snap_ real;
    begin
        select  snap_distance from _albion.metadata into snap_;

        -- snap geom to collars (adds points to geom)
        --with nearby_collar as (
        --    select st_collect(st_force2D(geom)) as geom
        --    from  _albion.collar
        --    where st_dwithin(geom, new.geom, snap_)
        --)
        --select coalesce(st_snap(st_removerepeatedpoints(new.geom, snap_), (select geom from nearby_collar), snap_), new.geom) into new.geom; 
        
        -- snap geom to collars and endpoints (adds points to geom)
        --with nearby_collar as (
        --    select st_collect(st_force2D(geom)) as geom
        --    from (
        --        select geom from _albion.collar
        --        where st_dwithin(geom, new.geom, snap_)
        --        union
        --        select (st_dumppoints(geom)).geom from _albion.grid
        --        where st_dwithin(geom, new.geom, snap_)
        --    ) as t
        --)
        --select coalesce(st_snap(st_removerepeatedpoints(new.geom, snap_), (select geom from nearby_collar), snap_), new.geom) into new.geom; 

        --with nearby_grid as (
        --    select st_collect(geom) as geom
        --    from (
        --        select geom from _albion.grid
        --        union
        --        select (st_dumppoints(geom)).geom as geom from _albion.grid
        --    ) as t
        --)
        --select coalesce(st_snap(st_removerepeatedpoints(new.geom, snap_), (select geom from nearby_grid), snap_), new.geom) into new.geom; 

        if tg_op = 'INSERT' then
            insert into _albion.grid(geom) values(new.geom) returning id into new.id;
        elsif tg_op = 'UPDATE' then
            update _albion.grid set geom=new.geom where id=new.id;
        elsif tg_op = 'DELETE' then
            delete from _albion.grid where id=old.id;
        end if;


        -- polygonize domain to create cells
        --refresh materialized view albion.cell;

        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            return new;
        elsif tg_op = 'DELETE' then
            return old;
        end if;
    end;
$$
;

create trigger grid_instead_trig
    instead of insert or update or delete on albion.grid
       for each row execute procedure albion.grid_instead_fct()
;

create view albion.collar as select id, geom, comments from _albion.collar
;

create view albion.close_point as
with ends as (
    select id, st_startpoint(geom) as geom from _albion.grid
    union
    select id, st_endpoint(geom) as geom from _albion.grid
)
select row_number() over() as id, e.geom::geometry('POINT', {srid}) 
from ends as e
where exists (
    select 1 
    from albion.grid as g 
    where st_dwithin(e.geom, g.geom, 2*(select snap_distance from _albion.metadata)) 
    and not st_intersects(e.geom, g.geom))
;

create function albion.fix_topology()
returns boolean
language plpgsql
as
$$
    begin
        with
        collar as (
            select st_force2D(geom) as geom from _albion.collar
        ),
        inter as (
            select st_intersection(a.geom, b.geom) as geom
            from _albion.grid as a, _albion.grid as b
            where st_intersects(new.geom, g.geom)
            and st_dimension(st_intersection(new.geom, g.geom))=0
        ),
        other as (
            select geom from collar
            union
            select geom from inter
            where not exists (select 1 from collar where st_dwithin(collar.geom, geom, snap_))
        ),
        ends as (
            select id, st_startpoint(g.geom) as geom from _albion.grid as g
            where not exists (select 1 from other where st_dwithin(other.geom, st_startpoint(g.geom), snap_))
            and st_dwithin(new.geom, g.geom, snap_)
            union
            select id, st_endpoint(geom) as geom from _albion.grid as g
            where not exists (select 1 from other where st_dwithin(other.geom, st_endpoint(g.geom), snap_))
            and st_dwithin(new.geom, g.geom, snap_)
        ),
        snap as (
            select st_collect(geom) as geom
            from (select geom from other union select geom from ends) as t
        )
        update _albion.grid set geom=coalesce(st_snap(geom, (select geom from snap), snap_), geom)
        where (select geom from snap) is not null;
    end;
$$
;
