-- public schema for database interface
create schema albion
;

-- UTILITY FUNCTIONS

create or replace function albion.snap_distance()
returns real
language plpgsql immutable
as
$$
    begin
        return (select snap_distance from _albion.metadata);
    end;
$$
;

create or replace function albion.update_hole_geom()
returns boolean
language plpgsql
as
$$
    begin
        with dz as (
            select 
                hole_id, 
                from_ as md2, coalesce(lag(from_) over w, 0) as md1,
                (deep + 90)*pi()/180 as wd2,  coalesce(lag((deep+90)*pi()/180) over w, 0) as wd1,
                azimuth*pi()/180 as haz2,  coalesce(lag(azimuth*pi()/180) over w, 0) as haz1
            from _albion.deviation 
            where azimuth >= 0 and azimuth <=360 and deep < 0 and deep > -180
            window w AS (partition by hole_id order by from_)
        ),
        pt as (
            select dz.hole_id, md2, wd2, haz2, 
            st_x(c.geom) + sum(0.5 * (md2 - md1) * (sin(wd1) * sin(haz1) + sin(wd2) * sin(haz2))) over w as x,
            st_y(c.geom) + sum(0.5 * (md2 - md1) * (sin(wd1) * cos(haz1) + sin(wd2) * cos(haz2))) over w as y,
            st_z(c.geom) - sum(0.5 * (md2 - md1) * (cos(wd2) + cos(wd1))) over w as z
            from dz join _albion.hole as h on h.id=hole_id join _albion.collar as c on c.id=h.collar_id
            window w AS (partition by hole_id order by md1)
        ),
        line as (
            select hole_id, st_makeline(('SRID={srid}; POINTZ('||x||' '||y||' '||z||')')::geometry order by md2 asc) as geom
            from pt
            group by hole_id
        )
        update _albion.hole as h set geom=(select st_addpoint(geom, (
                select c.geom from _albion.hole as hh join _albion.collar as c on c.id=hh.collar_id
                where hh.id=h.id), 0)
            from line as l where l.hole_id=h.id);
        return 't'::boolean;
    end;
$$
;

create or replace function albion.hole_piece(from_ real, to_ real, hole_id varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            select st_makeline(st_3dlineinterpolatepoint(h.geom, from_/st_3dlength(h.geom)),
                               st_3dlineinterpolatepoint(h.geom, least(1, to_/st_3dlength(h.geom)))) 
            from _albion.hole as h
            where h.id = hole_id
            and st_3dlength(h.geom) > 0
            and from_ < to_
            and from_/st_3dlength(h.geom) < 1);

    end;
$$
;

create or replace function albion.section(linestring geometry, section geometry)
returns geometry
language plpgsql
as
$$
    begin
        return (
            with point as (
                select (t.d).path as p, (t.d).geom as geom from (select st_dumppoints(linestring) as d) as t 
            )
            select st_setsrid(st_makeline(('POINT('||st_linelocatepoint(section, p.geom)*st_length(section)||' '||st_z(p.geom)||')')::geometry order by p), st_srid(linestring))
            from point as p
        );

    end;
$$
;


-- UTILITY VIEWS

create or replace view albion.close_point as
with ends as (
    select id, st_startpoint(geom) as geom from _albion.grid
    union
    select id, st_endpoint(geom) as geom from _albion.grid
)
select row_number() over() as id, e.geom::geometry('POINT', {srid}) 
from ends as e
where exists (
    select 1 
    from _albion.grid as g 
    where st_dwithin(e.geom, g.geom, 2*(select snap_distance from _albion.metadata)) 
    and not st_intersects(e.geom, g.geom))
;

create materialized view albion.small_edge as
with all_points as (
    select distinct (st_dumppoints(geom)).geom as geom from _albion.grid
)
select row_number() over() as id, a.geom::geometry('POINT', {srid}) 
from all_points as a, all_points as b
where st_dwithin(a.geom, b.geom, 2*albion.snap_distance())
and not st_intersects(a.geom, b.geom)
;


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


-- DATABASE INTERFACE (UPDATABE VIEWS)

create or replace view albion.grid as
select id, geom, st_azimuth(st_startpoint(geom), st_endpoint(geom)) as azimuth
from _albion.grid
;

create or replace function albion.grid_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        -- snap geom to collars (adds points to geom)
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            select st_removerepeatedpoints(new.geom, albion.snap_distance()) into new.geom;

            with snap as (
                select st_collect(geom) as geom
                from (
                    select st_force2D(geom) as geom
                    from  _albion.collar
                    where st_dwithin(geom, new.geom, albion.snap_distance())
                    union all
                    select st_closestpoint(geom, new.geom) as geom
                    from _albion.grid as g
                    where st_dwithin(geom, new.geom, albion.snap_distance())
                    and st_distance(st_closestpoint(g.geom, new.geom), (select c.geom from _albion.collar as c order by c.geom <-> st_closestpoint(g.geom, new.geom) limit 1)) > albion.snap_distance()
                ) as t
            )
            select coalesce(st_snap(new.geom, (select geom from snap), albion.snap_distance()), new.geom) into new.geom; 

            with new_points as (
                select st_collect(geom) as geom from (select (st_dumppoints(new.geom)).geom as geom) as t
            ),
            nearby as (
                select id from _albion.grid
                where st_dwithin(geom, new.geom, albion.snap_distance())
            )
            update _albion.grid as g set geom = st_snap(g.geom, (select geom from new_points), albion.snap_distance())
            where id in (select id from nearby);
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.grid(geom) values(new.geom) returning id into new.id;
        elsif tg_op = 'UPDATE' then
            update _albion.grid set geom=new.geom where id=new.id;
        elsif tg_op = 'DELETE' then
            delete from _albion.grid where id=old.id;
        end if;

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

create view albion.metadata as select id, srid, current_section, snap_distance, origin, precision from _albion.metadata
;

create view albion.hole as select id, collar_id, geom, st_3dlength(geom) as len from _albion.hole
;

create view albion.deviation as select hole_id, from_, deep, azimuth from _albion.deviation
;

create view albion.formation as select id, hole_id, from_, to_, code, comments, geom from _albion.formation
;

create or replace function albion.formation_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            select albion.hole_piece(new.from_, new.to_, new.hole_id) into new.geom;
        end if;
            
        if tg_op = 'INSERT' then
            insert into _albion.formation(id, hole_id, from_, to_, code, comments, geom) values(new.id, new.hole_id, new.from_, new.to_, new.code, new.comments, new.geom);
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.formation set hole_id=new.hole_id, from_=new.from_, to_=new.to_, code=new.code, comments=new.comments, geom=new.geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.formation where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger formation_instead_trig
    instead of insert or update or delete on albion.formation
       for each row execute procedure albion.formation_instead_fct()
;


create view albion.resistivity as select id, hole_id, from_, to_, rho, geom from _albion.resistivity
;

create or replace function albion.resistivity_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            select albion.hole_piece(new.from_, new.to_, new.hole_id) into new.geom;
        end if;
            
        if tg_op = 'INSERT' then
            insert into _albion.resistivity(id, hole_id, from_, to_, rho, geom) values(new.id, new.hole_id, new.from_, new.to_, new.rho, new.geom);
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.resistivity set hole_id=new.hole_id, from_=new.from_, to_=new.to_, rho=new.rho, geom=new.geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.resistivity where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger resistivity_instead_trig
    instead of insert or update or delete on albion.resistivity
       for each row execute procedure albion.resistivity_instead_fct()
;


create view albion.radiometry as select id, hole_id, from_, to_, gamma, geom from _albion.radiometry
;

create view albion.lithology as select id, hole_id, from_, to_, code, comments, geom from _albion.lithology
;

create view albion.mineralization as select id, hole_id, from_, to_, oc, accu, grade, geom from _albion.mineralization
;

create or replace function albion.create_graph(name varchar)
returns varchar
language plpgsql
as
$$
    begin
        execute (select replace('
            create table _albion.$name_node(
                id varchar primary key default uuid_generate_v4()::varchar,
                hole_id varchar references _albion.hole(id),
                geom geometry(''LINESTRINGZ'', {srid}) not null check (st_isvalid(geom) and st_numpoints(geom)=2)
            )
            ', '$name', name));
        
        execute (select replace('
            create view albion.$name_node as select id, hole_id, geom from _albion.$name_node
            ', '$name', name));

        execute (select replace('
            create table _albion.$name_link(
                id varchar primary key default uuid_generate_v4()::varchar,
                start_ varchar references _albion.$name_node(id),
                end_ varchar references _albion.$name_node(id),
                grid_id varchar references _albion.grid(id),
                geom geometry(''LINESTRINGZ'', {srid}) not null check (st_isvalid(geom) and st_numpoints(geom)=2)
            )
            ', '$name', name));

        execute (select replace('
                create view albion.$name_link as select id, start_, end_, grid_id, geom from _albion.$name_link
            ', '$name', name));

        return 't'::boolean;
    end;
$$
;


--surface geometry(''TINZ'', {srid})
--create view albion.formation_section as
--with coord as (
--    select ('SRID={srid}; POINT('||st_linelocatepoint(s.geom, p.geom)||' '||st_z(p.geom)||')')::geometry as geom
--    from albion.formation_geom
--
--select hole_id, from_, to_, code, comments

create or replace view albion.formation_section as
select f.id, f.from_, f.to_, f.code, f.comments, albion.section(f.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from albion.formation as f 
join albion.hole as h on h.id=f.hole_id
join albion.grid as g on st_intersects(st_startpoint(h.geom), g.geom)
where g.id = (select current_section from albion.metadata)
;

create or replace view albion.resistivity_section as
select f.id, f.from_, f.to_, f.rho, albion.section(f.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from albion.resistivity as f 
join albion.hole as h on h.id=f.hole_id
join albion.grid as g on st_intersects(st_startpoint(h.geom), g.geom)
where g.id = (select current_section from albion.metadata)
;



