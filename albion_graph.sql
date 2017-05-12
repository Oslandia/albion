create view albion.{name}_node as select id, hole_id, geom::geometry('LINESTRINGZ', {srid}) from _albion.{name}_node
;

create or replace view albion.{name}_node_section as
select f.id, f.hole_id, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from albion.{name}_node as f 
join albion.hole as h on h.id=f.hole_id
join albion.grid as g on st_intersects(st_startpoint(h.geom), g.geom)
where g.id = albion.current_section_id()
;

create view albion.{name}_edge as select id, start_, end_, grid_id, geom::geometry('LINESTRINGZ', {srid}) from _albion.{name}_edge
;

create or replace function albion.{name}_snap_edge_to_grid(new_geom geometry, start_ varchar, end_ varchar, grid_id varchar)
returns geometry
language plpgsql
as
$$
    begin
        return (
        with pt as (
            select (t.d).path as p, (t.d).geom as geom from 
                (select st_dumppoints(
                    st_linesubstring(geom, 
                        st_linelocatepoint(geom, (select st_startpoint(h.geom) from albion.hole as h join albion.{name}_node as n on n.hole_id=h.id where n.id=start_)),
                        st_linelocatepoint(geom, (select st_startpoint(h.geom) from albion.hole as h join albion.{name}_node as n on n.hole_id=h.id where n.id=end_))
                    )) as d from albion.grid where id=grid_id) as t
        ),
        snap as (
            select (st_dumppoints(new_geom)).geom as geom
            union all
            select st_setsrid(st_makepoint(st_x(pt.geom), st_y(pt.geom), st_z(st_lineinterpolatepoint(new_geom, st_linelocatepoint(new_geom, pt.geom)))), st_srid(new_geom)) as geom
            from pt
            where pt.p != (select min(p) from pt) 
            and pt.p != (select max(p) from pt)
        ),
        ends as (
            select (st_dumppoints(geom)).geom as geom from _albion.{name}_node as n
            where id in (start_, end_)
        )
        select st_makeline(st_snap(s.geom, n.geom, albion.precision()) order by st_linelocatepoint(g.geom, s.geom))
        from snap as s, albion.grid as g, ends as n
        where g.id=grid_id
    );
    end;
$$
;

create or replace function albion.{name}_edge_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            -- adds points to match the grid nodes
            select albion.{name}_snap_edge_to_grid(new.geom, new.start_, new.end_, new.grid_id) into new.geom;
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.{name}_edge(start_, end_, grid_id, geom) values(new.start_, new.end_, new.grid_id, new.geom) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.{name}_edge set start_=new.start_, end_=new.end_, grid_id=new.grid_id, geom=new.geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.{name}_edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger {name}_edge_instead_trig
    instead of insert or update or delete on albion.{name}_edge
       for each row execute procedure albion.{name}_edge_instead_fct()
;


create or replace view albion.{name}_edge_section as
select f.id, f.start_, f.end_, f.grid_id, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from albion.{name}_edge as f join albion.grid as g on g.id=f.grid_id
where g.id = albion.current_section_id()
;

create or replace function albion.{name}_edge_section_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        edge_geom geometry;
        wall_geom geometry;
        ceil_geom geometry;
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            -- find end nodes from geometry
            select id
            from albion.{name}_node_section as s
            where st_dwithin(s.geom, st_startpoint(new.geom), albion.snap_distance())
            into new.start_;

            select id
            from albion.{name}_node_section as s
            where st_dwithin(s.geom, st_endpoint(new.geom), albion.snap_distance())
            into new.end_;

            select albion.current_section_id() into new.grid_id;

            -- make the 3D edge geometry
            select st_makeline(
                (select st_3dlineinterpolatepoint(geom, .5) from _albion.{name}_node where id=new.start_), 
                (select st_3dlineinterpolatepoint(geom, .5) from _albion.{name}_node where id=new.end_)) into edge_geom;
        end if;

        -- /!\ insert/update the edge view to trigger line splitting at grid points 
        if tg_op = 'INSERT' then
            insert into albion.{name}_edge(start_, end_, grid_id, geom) values(new.start_, new.end_, new.grid_id, edge_geom) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update albion.{name}_edge set start_=new.start_, end_=new.end_, grid_id=new.grid_id, geom=edge_geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from albion.{name}_edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger {name}_edge_section_instead_trig
    instead of insert or update or delete on albion.{name}_edge_section
       for each row execute procedure albion.{name}_edge_section_instead_fct()
;

create or replace view albion.{name}_wall_edge as select id, grid_id, geom::geometry('LINESTRINGZ', {srid}) from _albion.{name}_wall_edge;

create or replace view albion.{name}_wall_edge_section as
select e.id, e.grid_id,albion.to_section(e.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from _albion.{name}_wall_edge as e join albion.grid as g on g.id=e.grid_id
where g.id=albion.current_section_id()
;

create or replace function albion.{name}_wall_edge_section_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        edge_geom geometry;
        start_ varchar;
        end_ varchar;
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            select albion.current_section_id() into new.grid_id;
            select id from albion.{name}_node_section where st_dwithin(geom, st_startpoint(new.geom), albion.snap_distance()) into start_;
            select id from albion.{name}_node_section where st_dwithin(geom, st_endpoint(new.geom), albion.snap_distance()) into start_;
            select albion.{name}_snap_edge_to_grid(
                albion.from_section(
                    new.geom, 
                    (select geom from _albion.grid where id=new.grid_id)),
                start_,
                end_,
                new.grid_id) into edge_geom;
        end if;
            
        if tg_op = 'INSERT' then
            insert into _albion.{name}_wall_edge(grid_id, geom) values (new.grid_id, edge_geom) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.{name}_wall_edge set grid_id=new.grid_id, geom=edge_geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.{name}_wall_edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger {name}_wall_edge_section_instead_trig
    instead of insert or update or delete on albion.{name}_wall_edge_section
       for each row execute procedure albion.{name}_wall_edge_section_instead_fct()
;

create or replace view albion.{name}_ceil_edge as select id, grid_id, geom::geometry('LINESTRINGZ', {srid}) from _albion.{name}_ceil_edge;

create or replace view albion.{name}_ceil_edge_section as
select e.id, e.grid_id, albion.to_section(e.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
from _albion.{name}_ceil_edge as e join albion.grid as g on g.id=e.grid_id
where g.id=albion.current_section_id()
;

create or replace function albion.{name}_ceil_edge_section_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        edge_geom geometry;
        start_ varchar;
        end_ varchar;
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            select albion.current_section_id() into new.grid_id;
            select id from albion.{name}_node_section where st_dwithin(geom, st_startpoint(new.geom), albion.snap_distance()) into start_;
            select id from albion.{name}_node_section where st_dwithin(geom, st_endpoint(new.geom), albion.snap_distance()) into start_;
            select albion.{name}_snap_edge_to_grid(
                albion.from_section(
                    new.geom, 
                    (select geom from _albion.grid where id=new.grid_id)),
                start_,
                end_,
                new.grid_id) into edge_geom;
        end if;
            
        if tg_op = 'INSERT' then
            insert into _albion.{name}_ceil_edge(grid_id, geom) values (new.grid_id, edge_geom) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.{name}_ceil_edge set grid_id=new.grid_id, geom=edge_geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.{name}_ceil_edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger {name}_ceil_edge_section_instead_trig
    instead of insert or update or delete on albion.{name}_ceil_edge_section
       for each row execute procedure albion.{name}_ceil_edge_section_instead_fct()
;


-- view for incomming and outgoing edges

create view albion.{name}_incoming_ceil_edge_section as
select ce.id, ce.grid_id, albion.to_section(st_endpoint(ce.geom), g.geom)::geometry('POINT', {srid}) as geom
from _albion.{name}_ceil_edge as ce
join _albion.{name}_edge as e on e.id=ce.id,
albion.grid as g
where g.id=albion.current_section_id()
and e.end_ in (select id from albion.{name}_node_section)
and ce.grid_id != g.id
;

create view albion.{name}_outgoing_ceil_edge_section as
select ce.id, ce.grid_id, albion.to_section(st_startpoint(ce.geom), g.geom)::geometry('POINT', {srid}) as geom
from _albion.{name}_ceil_edge as ce
join _albion.{name}_edge as e on e.id=ce.id,
albion.grid as g
where g.id=albion.current_section_id()
and e.start_ in (select id from albion.{name}_node_section)
and ce.grid_id != g.id
;

create view albion.{name}_incoming_wall_edge_section as
select ce.id, ce.grid_id, albion.to_section(st_endpoint(ce.geom), g.geom)::geometry('POINT', {srid}) as geom
from _albion.{name}_wall_edge as ce
join _albion.{name}_edge as e on e.id=ce.id,
albion.grid as g
where g.id=albion.current_section_id()
and e.end_ in (select id from albion.{name}_node_section)
and ce.grid_id != g.id
;

create view albion.{name}_outgoing_wall_edge_section as
select ce.id, ce.grid_id, albion.to_section(st_startpoint(ce.geom), g.geom)::geometry('POINT', {srid}) as geom
from _albion.{name}_wall_edge as ce
join _albion.{name}_edge as e on e.id=ce.id,
albion.grid as g
where g.id=albion.current_section_id()
and e.start_ in (select id from albion.{name}_node_section)
and ce.grid_id != g.id
;

-- crossing edges

create view albion.{name}_crossing_ceil_edge_section as
select ce.id, ce.grid_id, albion.to_section(ce.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
    from _albion.{name}_ceil_edge as ce,
    albion.grid as g
    where g.id=albion.current_section_id()
    and st_dwithin(g.geom, ce.geom, albion.snap_distance())
    and ce.id not in (select id from albion.{name}_outgoing_ceil_edge_section union all select id from albion.{name}_incoming_ceil_edge_section)
    and ce.grid_id != g.id
;

create view albion.{name}_crossing_wall_edge_section as
select ce.id, ce.grid_id, albion.to_section(ce.geom, g.geom)::geometry('LINESTRING', {srid}) as geom
    from _albion.{name}_wall_edge as ce,
    albion.grid as g
    where g.id=albion.current_section_id()
    and st_dwithin(g.geom, ce.geom, albion.snap_distance())
    and ce.id not in (select id from albion.{name}_outgoing_wall_edge_section union all select id from albion.{name}_incoming_wall_edge_section)
    and ce.grid_id != g.id
;

