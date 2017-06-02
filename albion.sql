 -------------------------------------------------------------------------------
-- PUBLIC SCHEMA FOR DATABASE INTERFACE
-------------------------------------------------------------------------------

create schema albion
;

-------------------------------------------------------------------------------
-- UTILITY FUNCTIONS
-------------------------------------------------------------------------------

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

create or replace function albion.precision()
returns real
language plpgsql stable
as
$$
    begin
        return (select precision from _albion.metadata);
    end;
$$
;


create or replace function albion.current_section_id()
returns varchar
language plpgsql stable
as
$$
    begin
        return (select current_section from _albion.metadata);
    end;
$$
;

create or replace function albion.current_section_geom()
returns geometry
language plpgsql stable
as
$$
    begin
        return (select g.geom from _albion.grid as g, _albion.metadata as m where g.id=m.current_section);
    end;
$$
;

create or replace function albion.hole_geom(hole_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    declare
        depth_max_ real;
        hole_geom_ geometry;
        collar_id_ varchar;
        collar_geom_ geometry;
    begin
        select collar_id, depth_ from albion.hole where id=hole_id_ into collar_id_, depth_max_;

        select geom from albion.collar where id=collar_id_ into collar_geom_;
        
        with dz as (
            select 
                from_ as md2, coalesce(lag(from_) over w, 0) as md1,
                (dip + 90)*pi()/180 as wd2,  coalesce(lag((dip+90)*pi()/180) over w, 0) as wd1,
                azimuth*pi()/180 as haz2,  coalesce(lag(azimuth*pi()/180) over w, 0) as haz1
            from _albion.deviation 
            where azimuth >= 0 and azimuth <=360 and dip < 0 and dip > -180
            and hole_id=hole_id_
            window w AS (order by from_)
        ),
        pt as (
            select md2, wd2, haz2, 
            st_x(collar_geom_) + sum(0.5 * (md2 - md1) * (sin(wd1) * sin(haz1) + sin(wd2) * sin(haz2))) over w as x,
            st_y(collar_geom_) + sum(0.5 * (md2 - md1) * (sin(wd1) * cos(haz1) + sin(wd2) * cos(haz2))) over w as y,
            st_z(collar_geom_) - sum(0.5 * (md2 - md1) * (cos(wd2) + cos(wd1))) over w as z
            from dz
            window w AS (order by md1)
        ),
        line as (
            select st_makeline(('SRID=$SRID; POINTZ('||x||' '||y||' '||z||')')::geometry order by md2 asc) as geom
            from pt
        )
        select st_addpoint(geom, collar_geom_, 0)
            from line as l 
        into hole_geom_;

        if hole_geom_ is not null and st_3dlength(hole_geom_) < depth_max_ then
            -- holes is not long enough
            with last_segment as (
                select st_pointn(hole_geom_, st_numpoints(hole_geom_)-1) as start_, st_endpoint(hole_geom_) as end_
            ),
            direction as (
                select 
                (st_x(end_) - st_x(start_))/st_3ddistance(end_, start_) as x, 
                (st_y(end_) - st_y(start_))/st_3ddistance(end_, start_) as y, 
                (st_z(end_) - st_z(start_))/st_3ddistance(end_, start_) as z 
                from last_segment
            )
            select st_addpoint(hole_geom_,
                        st_makepoint(
                            st_x(s.end_) + (depth_max_-st_3dlength(hole_geom_))*d.x,
                            st_y(s.end_) + (depth_max_-st_3dlength(hole_geom_))*d.y,
                            st_z(s.end_) + (depth_max_-st_3dlength(hole_geom_))*d.z
                        ), -1)
            from direction as d, last_segment as s
            into hole_geom_;

            -- hole have no deviation
        elsif hole_geom_ is null then
            select st_makeline( collar_geom_, st_translate(collar_geom_, 0, 0, -depth_max_)) into hole_geom_;
        end if;

        return hole_geom_;
    end;
$$
;

create or replace function albion.hole_piece(from_ real, to_ real, hole_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            select st_makeline(
                st_3dlineinterpolatepoint(geom, from_/depth_),
                st_3dlineinterpolatepoint(geom, to_/depth_))
            from albion.hole where id=hole_id_
        );
    end;
$$
;

-- 2D projected geometry from 3D geometry
create or replace function albion.to_section(geom geometry, section geometry)
returns geometry
language plpython3u immutable
as
$$
    from shapely.ops import transform 
    from shapely.geometry import Point
    from shapely import wkb
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    if geom is None:
        return None
    g = wkb.loads(geom, True)
    s = wkb.loads(section, True)
    def tr(x, y, z=None):
        z = z or (0,)*len(x)
        return zip(*((s.project(Point(x_, y_)), z_) 
                for x_, y_, z_ in (zip(x,y,z) if hasattr(x, '__iter__') else zip((s.project(Point(x_, y_)),),(z,)))))
    result = transform(tr, g)
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(g._geom))
    return result.wkb_hex
$$
;

-- 3D geometry from 2D projected geometry
create or replace function albion.from_section(geom geometry, section geometry)
returns geometry
language plpython3u immutable
as
$$
    from shapely.ops import transform 
    from shapely import wkb
    from shapely import geos
    from shapely.geometry import LineString
    geos.WKBWriter.defaults['include_srid'] = True

    if geom is None:
        return None
    g = wkb.loads(geom, True)
    s = wkb.loads(section, True)
    l = s.length
    def tr(x, y):
        return zip(*((tuple(s.interpolate(min(max(x_,0),l)).coords[0][:2])+(y_,))
                for x_, y_ in zip(x,y) )) # if hasattr(x, '__iter__') else zip((s.interpolate(x).coords[0],),(s.interpolate(x).coords[1],),(y,)))))

    result = transform(tr, g)
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(g._geom))
    return result.wkb_hex
$$
;

create or replace function albion.snap_edge_to_grid(new_geom geometry, start_ varchar, end_ varchar, grid_id varchar)
returns geometry
language plpgsql
as
$$
    begin
        if new_geom is null then
            return null;
        end if;

        return (
        with pt as (
            select (t.d).path as p, (t.d).geom as geom from 
                (select st_dumppoints(
                    st_linesubstring(geom, 
                        st_linelocatepoint(geom, coalesce((select st_startpoint(h.geom) from albion.hole as h join albion.node as n on n.hole_id=h.id where n.id=start_), st_startpoint(new_geom))),
                        st_linelocatepoint(geom, coalesce((select st_startpoint(h.geom) from albion.hole as h join albion.node as n on n.hole_id=h.id where n.id=end_), st_endpoint(new_geom)))
                    )) as d from albion.grid where id=grid_id) as t
        ),
        snap as (
            select (st_dumppoints(new_geom)).geom as geom
            union
            select st_setsrid(st_makepoint(st_x(pt.geom), st_y(pt.geom), 
                    st_z(st_lineinterpolatepoint(new_geom, st_linelocatepoint(new_geom, pt.geom)))), st_srid(new_geom)) as geom
            from pt
            where pt.p != (select min(p) from pt) 
            and pt.p != (select max(p) from pt)
        )
        select st_makeline(s.geom order by st_linelocatepoint(g.geom, s.geom))
        from snap as s, albion.grid as g
        where g.id=grid_id
    );
    end;
$$
;

-------------------------------------------------------------------------------
-- UTILITY VIEWS
-------------------------------------------------------------------------------

create or replace view albion.close_point as
with ends as (
    select id, st_startpoint(geom) as geom from _albion.grid
    union
    select id, st_endpoint(geom) as geom from _albion.grid
)
select row_number() over() as id, e.geom::geometry('POINT', $SRID) 
from ends as e
where exists (
    select 1 
    from _albion.grid as g 
    where st_dwithin(e.geom, g.geom, 2*(select snap_distance from _albion.metadata)) 
    and not st_intersects(e.geom, g.geom))
;

create view albion.small_edge as
with all_points as (
    select id, (t.d).path as pth, (t.d).geom as geom 
    from (select id, st_dumppoints(geom) as d from _albion.grid) as t
),
len as (
    select id, geom, st_distance(lag(geom) over (partition by id order by pth), geom ) as d
    from all_points
)
select row_number() over() as id, geom::geometry('POINT', $SRID)
from len
where d < 2*albion.snap_distance() and d > 0
;

create view albion.hole_grid
as
select h.id as hole_id, g.id as grid_id, g.geom
from _albion.hole as h 
join _albion.collar as c on c.id=h.collar_id
join _albion.grid as g on st_intersects(c.geom, g.geom)
;


--------------------------------------------------------------------------------
-- DATABASE INTERFACE (UPDATABE VIEWS)
--------------------------------------------------------------------------------

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
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.grid set geom=new.geom where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.grid where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger grid_instead_trig
    instead of insert or update or delete on albion.grid
       for each row execute procedure albion.grid_instead_fct()
;

create view albion.collar as select id, geom, date_, comments from _albion.collar
;

create view albion.metadata as select id, srid, snap_distance, precision, interpolation, current_section, current_graph, end_distance, correlation_distance, correlation_slope from _albion.metadata
;

create view albion.hole as select id, collar_id, depth_, geom::geometry('LINESTRINGZ', $SRID) from _albion.hole
;

create view albion.deviation as select hole_id, from_, dip, azimuth from _albion.deviation
;

create view albion.formation as select id, hole_id, from_, to_, code, comments, geom::geometry('LINESTRINGZ', $SRID) from _albion.formation
;

create view albion.resistivity as select id, hole_id, from_, to_, rho, geom::geometry('LINESTRINGZ', $SRID) from _albion.resistivity
;

create view albion.radiometry as select id, hole_id, from_, to_, gamma, geom::geometry('LINESTRINGZ', $SRID) from _albion.radiometry
;

create view albion.lithology as select id, hole_id, from_, to_, code, comments, geom::geometry('LINESTRINGZ', $SRID) from _albion.lithology
;

create view albion.facies as select id, hole_id, from_, to_, code, comments, geom::geometry('LINESTRINGZ', $SRID) from _albion.facies
;


create view albion.mineralization as select id, hole_id, from_, to_, oc, accu, grade, geom::geometry('LINESTRINGZ', $SRID) from _albion.mineralization
;

create or replace view albion.graph as
select id, parent from _albion.graph
;

create or replace view albion.node as 
select id, graph_id, hole_id, geom::geometry('LINESTRINGZ', $SRID) 
from _albion.node
;

create or replace view albion.edge as 
select id, graph_id, start_, end_, grid_id, geom::geometry('LINESTRINGZ', $SRID), ceil_::geometry('LINESTRINGZ', $SRID), wall_::geometry('LINESTRINGZ', $SRID) 
from _albion.edge
;

create or replace function albion.edge_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' or tg_op = 'UPDATE' then
            -- find start_ and end_ if null
            if new.graph_id is null then
                select coalesce(new.start_, (select id from albion.node where st_dwithin(geom, st_startpoint(new.geom), albion.precision()) order by st_distance(geom, st_startpoint(new.geom)) limit 1)) into new.start_;
                select coalesce(new.end_, (select id from albion.node where st_dwithin(geom, st_endpoint(new.geom), albion.precision()) order by st_distance(geom, st_endpoint(new.geom)) limit 1)) into new.end_;
            else
                select coalesce(new.start_, (select id from albion.node where st_dwithin(geom, st_startpoint(new.geom), albion.precision()) and graph_id=new.graph_id order by st_distance(geom, st_startpoint(new.geom)) limit 1)) into new.start_;
                select coalesce(new.end_, (select id from albion.node where st_dwithin(geom, st_endpoint(new.geom), albion.precision()) and graph_id=new.graph_id order by st_distance(geom, st_endpoint(new.geom)) limit 1)) into new.end_;
            end if;

            -- find graph_id from nodes
            select coalesce(new.graph_id, 
                (select graph_id from albion.node where id in (new.start_, new.end_) limit 1))
            into new.graph_id;

            -- invert start and end if they are inverted/grid direction
            if (select st_linelocatepoint((select geom from _albion.grid where id=new.grid_id), 
                (select st_3dlineinterpolatepoint(geom, .5) from _albion.node where id=new.start_))) 
                > 
                (select st_linelocatepoint((select geom from _albion.grid where id=new.grid_id), 
                (select st_3dlineinterpolatepoint(geom, .5) from _albion.node where id=new.end_))) then
                    select new.start_, new.end_ into new.end_, new.start_;
            end if;
            -- adds points to match the grid nodes
            select albion.snap_edge_to_grid(new.geom, new.start_, new.end_, new.grid_id) into new.geom;
            select albion.snap_edge_to_grid(new.ceil_, new.start_, new.end_, new.grid_id) into new.ceil_;
            select albion.snap_edge_to_grid(new.wall_, new.start_, new.end_, new.grid_id) into new.wall_;
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.edge(graph_id, start_, end_, grid_id, geom, ceil_, wall_) values(new.graph_id, new.start_, new.end_, new.grid_id, new.geom, new.ceil_, new.wall_) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.edge set start_=new.start_, end_=new.end_, grid_id=new.grid_id, geom=new.geom, ceil_=new.ceil_, wall_=new.wall_ where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger edge_instead_trig
    instead of insert or update or delete on albion.edge
       for each row execute procedure albion.edge_instead_fct()
;


--------------------------------------------------------------------------------
-- SECTION VIEW
--------------------------------------------------------------------------------

create or replace view albion.formation_section as
select f.id, f.hole_id, f.from_, f.to_, f.code, f.comments, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', $SRID) as geom
from albion.formation as f 
join albion.hole_grid as g on g.hole_id=f.hole_id
where g.grid_id = albion.current_section_id()
;

create or replace view albion.resistivity_section as
select f.id, f.hole_id, f.from_, f.to_, f.rho, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', $SRID) as geom
from albion.resistivity as f 
join albion.hole_grid as g on g.hole_id=f.hole_id
where g.grid_id = albion.current_section_id()
;

create or replace view albion.radiometry_section as
select f.id, f.hole_id, f.from_, f.to_, f.gamma, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', $SRID) as geom
from albion.radiometry as f 
join albion.hole_grid as g on g.hole_id=f.hole_id
where g.grid_id = albion.current_section_id()
;

create or replace view albion.collar_section as
select f.id, f.comments, f.date_, albion.to_section(f.geom, albion.current_section_geom())::geometry('POINT', $SRID) as geom
from albion.collar as f 
where st_intersects(f.geom, albion.current_section_geom())
;

create or replace function albion.collar_section_instead_fct()
returns trigger
language plpgsql
as
$$
    begin

        -- /!\ insert/update the edge view to trigger line splitting at grid points 
        if tg_op = 'INSERT' then
            raise notice 'collar cannot be inserted from section';
            return new;
        elsif tg_op = 'UPDATE' then
            raise notice 'collar cannot be updated from section';
            return new;
        elsif tg_op = 'DELETE' then
            delete from albion.collar where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger collar_section_instead_trig
    instead of insert or update or delete on albion.collar_section
       for each row execute procedure albion.collar_section_instead_fct()
;

create or replace view albion.hole_section as
select f.id, f.collar_id, albion.to_section(f.geom, albion.current_section_geom())::geometry('LINESTRING', $SRID) as geom
from albion.hole as f 
where st_intersects(st_startpoint(f.geom), albion.current_section_geom())
;

create or replace view albion.node_section as
select f.id, f.graph_id, f.hole_id, albion.to_section(f.geom, albion.current_section_geom())::geometry('LINESTRING', $SRID) as geom
from albion.node as f
join albion.hole_grid as g on g.hole_id=f.hole_id
where g.grid_id = albion.current_section_id()
;



create or replace view albion.edge_section as
select f.id, f.graph_id, f.start_, f.end_, f.grid_id,
    albion.to_section(f.geom, albion.current_section_geom())::geometry('LINESTRING', $SRID) as geom,
    albion.to_section(f.ceil_, albion.current_section_geom())::geometry('LINESTRING', $SRID) as ceil_,
    albion.to_section(f.wall_, albion.current_section_geom())::geometry('LINESTRING', $SRID) as wall_
from albion.edge as f
where f.grid_id = albion.current_section_id()
;

create or replace function albion.edge_section_instead_fct()
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
            from albion.node_section as s
            where st_dwithin(s.geom, st_startpoint(new.geom), albion.snap_distance())
            into new.start_;

            select id
            from albion.node_section as s
            where st_dwithin(s.geom, st_endpoint(new.geom), albion.snap_distance())
            into new.end_;

            -- find graph_id from nodes
            select coalesce(new.graph_id, 
                (select graph_id from albion.node where id in (new.start_, new.end_) limit 1))
            into new.graph_id;

            select albion.current_section_id() into new.grid_id;

            -- make the 3D edge geometry
            select st_makeline(
                coalesce((select st_3dlineinterpolatepoint(geom, .5) from _albion.node where id=new.start_), albion.from_section(st_startpoint(new.geom), albion.current_section_geom())), 
                coalesce((select st_3dlineinterpolatepoint(geom, .5) from _albion.node where id=new.end_), albion.from_section(st_endpoint(new.geom), albion.current_section_geom()))
                ) into edge_geom;

            select albion.from_section(new.ceil_, albion.current_section_geom()) into ceil_geom;
            select albion.from_section(new.wall_, albion.current_section_geom()) into wall_geom;
        end if;

        -- /!\ insert/update the edge view to trigger line splitting at grid points 
        if tg_op = 'INSERT' then
            insert into albion.edge(graph_id, start_, end_, grid_id, geom, ceil_, wall_) values(new.graph_id, new.start_, new.end_, new.grid_id, edge_geom, ceil_geom, wall_geom) returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update albion.edge set start_=new.start_, end_=new.end_, grid_id=new.grid_id, geom=edge_geom, ceil_=new.ceil_, wall_=new.wall_ where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from albion.edge where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger edge_section_instead_trig
    instead of insert or update or delete on albion.edge_section
       for each row execute procedure albion.edge_section_instead_fct()
;


create or replace view albion.crossing_edge_section as
with outgoing as (
    select f.id, f.graph_id, f.start_, f.end_, f.grid_id,
        albion.to_section(st_startpoint(f.geom), albion.current_section_geom()) as geom,
        albion.to_section(st_startpoint(f.ceil_), albion.current_section_geom()) as ceil_,
        albion.to_section(st_startpoint(f.wall_), albion.current_section_geom()) as wall_
    from albion.edge as f 
    where f.grid_id != albion.current_section_id()
    and f.start_ in (select id from albion.node_section)
),
incomming as (
    select f.id, f.graph_id, f.start_, f.end_, f.grid_id,
        albion.to_section(st_endpoint(f.geom), albion.current_section_geom()) as geom,
        albion.to_section(st_endpoint(f.ceil_), albion.current_section_geom()) as ceil_,
        albion.to_section(st_endpoint(f.wall_), albion.current_section_geom()) as wall_
    from albion.edge as f
    where f.grid_id != albion.current_section_id()
    and f.end_ in (select id from albion.node_section)
),
crossing_edge as (
    select distinct ce.id
    from albion.edge as ce
    where st_intersects(albion.current_section_geom(), ce.geom)
    and ce.grid_id!=albion.current_section_id()
    and ce.id not in (select id from outgoing union all select id from incomming)
),
pt as (
    select distinct * from (
        select ce.id, ce.graph_id, ce.start_, ce.end_, ce.grid_id, (st_dumppoints(ce.geom)).geom as geom
        from crossing_edge as e inner join albion.edge as ce on e.id=ce.id) as t
    where st_intersects(albion.current_section_geom(), geom)
),
pt_wall as (
    select distinct * from (
        select ce.id, ce.graph_id, ce.start_, ce.end_, ce.grid_id, (st_dumppoints(ce.wall_)).geom as geom
        from crossing_edge as e inner join albion.edge as ce on e.id=ce.id) as t
    where st_intersects(albion.current_section_geom(), geom)
),
pt_ceil as (
    select distinct * from (
        select ce.id, ce.graph_id, ce.start_, ce.end_, ce.grid_id, (st_dumppoints(ce.ceil_)).geom as geom
        from crossing_edge as e inner join albion.edge as ce on e.id=ce.id) as t
    where st_intersects(albion.current_section_geom(), geom)
),
crossing as (
    select pt.id, pt.graph_id, pt.start_, pt.end_, pt.grid_id, 
        albion.to_section(pt.geom, albion.current_section_geom()) as geom,
        albion.to_section(pt_ceil.geom, albion.current_section_geom()) as ceil_,
        albion.to_section(pt_wall.geom, albion.current_section_geom()) as wall_
    from pt join pt_wall on pt_wall.id=pt.id join pt_ceil on pt_ceil.id=pt.id
)
select id, graph_id, start_, end_, grid_id, geom::geometry('POINT', 32632), ceil_::geometry('POINT', 32632), wall_::geometry('POINT', 32632), 'incomming' as connection from incomming
union all
select id, graph_id, start_, end_, grid_id, geom::geometry('POINT', 32632), ceil_::geometry('POINT', 32632), wall_::geometry('POINT', 32632), 'outgoing' as connection from outgoing
union all
select id, graph_id, start_, end_, grid_id, geom::geometry('POINT', 32632), ceil_::geometry('POINT', 32632), wall_::geometry('POINT', 32632), 'crossing' as connection from crossing
;



--------------------------------------------------------------------------------
-- AUTO CONNECT
--------------------------------------------------------------------------------

-- create graph edges for the specified grid element
create or replace function albion.auto_connect(graph_id_ varchar, grid_id_ varchar)
returns boolean
language plpgsql
as
$$
    begin
        with node as ( 
            select f.id, f.hole_id, st_3dlineinterpolatepoint(f.geom, .5) as geom
            from albion.node as f join albion.hole_grid as g on f.hole_id=g.hole_id
            where g.grid_id = grid_id_
            and f.graph_id=graph_id_
        ),
        hole_pair as (
            select
                row_number() over() as id,
                h.id as right, 
                lag(h.id) over (order by st_linelocatepoint((select geom from albion.grid where id=grid_id_), st_startpoint(h.geom))) as left
            from albion.hole as h, albion.grid as g 
            where h.geom && g.geom 
            and st_intersects(st_startpoint(h.geom), g.geom)
            and g.id=grid_id_
        ),
        possible_edge as (
            select 
                n1.id as start_, 
                n2.id as end_,
                st_makeline(n1.geom, n2.geom) as geom, 
                abs(st_z(n2.geom) - st_z(n1.geom))/st_distance(n2.geom, n1.geom) angle,
                count(1) over (partition by n1.id) as c1,  
                count(1) over (partition by n2.id) as c2, 
                rank() over (partition by p.id order by abs(st_z(n2.geom) - st_z(n1.geom)) asc) as rk
            from hole_pair as p
            join node as n1 on n1.hole_id=p.left
            join node as n2 on n2.hole_id=p.right, albion.metadata as m
            where st_distance(n1.geom, n2.geom) <  m.correlation_distance
        )
        insert into albion.edge(graph_id, start_, end_, grid_id, geom)
        select graph_id_, e.start_, e.end_, grid_id_, e.geom  from possible_edge as e
        where e.rk <= least(e.c1, e.c2)
        and not exists (select 1 from albion.edge where (start_=e.start_ and end_=e.end_) or (start_=e.end_ and end_=e.start_));

        return 't'::boolean;

    end;
$$
;

-- create graph edges for the specified grid element
create or replace function albion.auto_connect(graph_id_ varchar, grid_id_ varchar, support_graph_id_ varchar)
returns boolean
language plpgsql
as
$$
    begin
        with node as ( 
            select f.id, f.hole_id, st_3dlineinterpolatepoint(f.geom, .5) as geom, st_3dlineinterpolatepoint(s.geom, .5) as s_geom
            from albion.node as f join albion.hole_grid as g on f.hole_id=g.hole_id
            join albion.node as s on s.hole_id=f.hole_id 
            where g.grid_id = grid_id_
            and f.graph_id=graph_id_
            and s.graph_id=support_graph_id_
            and st_z(st_startpoint(s.geom)) >= st_z(st_3dlineinterpolatepoint(f.geom, .5)) 
            and st_z(st_3dlineinterpolatepoint(f.geom, .5)) >  st_z(st_endpoint(s.geom))
        ),
        hole_pair as (
            select
                row_number() over() as id,
                h.id as right, 
                lag(h.id) over (order by st_linelocatepoint((select geom from albion.grid where id=grid_id_), st_startpoint(h.geom))) as left
            from albion.hole as h, albion.grid as g 
            where h.geom && g.geom 
            and st_intersects(st_startpoint(h.geom), g.geom)
            and g.id=grid_id_
        ),
        possible_edge as (
            select 
                n1.id as start_, 
                n2.id as end_,
                st_makeline(n1.geom, n2.geom) as geom, 
                abs(st_z(n2.geom) - st_z(n1.geom))/st_distance(n2.geom, n1.geom) angle,
                count(1) over (partition by n1.id) as c1,  
                count(1) over (partition by n2.id) as c2, 
                rank() over (partition by p.id order by abs((st_z(n2.geom) - st_z(n1.geom))/st_distance(n1.geom, n2.geom) 
                    - (st_z(n2.s_geom) - st_z(n1.s_geom))/st_distance(n1.s_geom, n2.s_geom)) asc) as rk
            from hole_pair as p
            join node as n1 on n1.hole_id=p.left
            join node as n2 on n2.hole_id=p.right, albion.metadata as m
            where st_distance(n1.geom, n2.geom) <  m.correlation_distance
            and (abs((st_z(n2.geom) - st_z(n1.geom))/st_distance(n1.geom, n2.geom) 
                    - (st_z(n2.s_geom) - st_z(n1.s_geom))/st_distance(n1.s_geom, n2.s_geom)) < m.correlation_slope
                )
        )
        insert into albion.edge(graph_id, start_, end_, grid_id, geom)
        select graph_id_, e.start_, e.end_, grid_id_, e.geom  from possible_edge as e
        where /*e.rk <= least(e.c1, e.c2)
        and*/ not exists (select 1 from albion.edge where (start_=e.start_ and end_=e.end_) or (start_=e.end_ and end_=e.start_));

        return 't'::boolean;

    end;
$$
;

create or replace function albion.inv(x double precision)
returns double precision
language plpgsql immutable
as
$$
    begin
        if abs(x) > 0 then
            return 1/x;
        else
            return null;
        end if;
    end;
$$
;



create or replace function albion.auto_ceil_and_wall(graph_id_ varchar, grid_id_ varchar)
returns boolean
language plpgsql
as
$$
    begin
        update albion.edge as e set wall_ =  (
            select st_makeline(
                st_3dlineinterpolatepoint(n1.geom, least(
                     (select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n2.hole_id 
                        and exists (select 1 from albion.edge where start_=n1.id and end_=o.id) 
                        and st_z(st_3dlineinterpolatepoint(o.geom, .5)) >= st_z(st_3dlineinterpolatepoint(n2.geom, .5)))
                    *albion.inv((select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n2.hole_id 
                        and exists (select 1 from albion.edge where start_=n1.id and end_=o.id)))
                , 1)), 
                st_3dlineinterpolatepoint(n2.geom, least(
                     (select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n1.hole_id 
                        and exists (select 1 from albion.edge where start_=o.id and end_=n2.id) 
                        and st_z(st_3dlineinterpolatepoint(o.geom, .5)) >= st_z(st_3dlineinterpolatepoint(n1.geom, .5))) 
                    *albion.inv((select sum(st_3dlength(o.geom)) from albion.node as o
                        where o.hole_id=n1.hole_id 
                        and exists (select 1 from albion.edge where start_=o.id and end_=n2.id)))
                , 1))
            )
            from albion.node as n1, albion.node as n2
            where n2.id=e.end_ and n1.id=e.start_
        )
        where e.grid_id=grid_id_ and wall_ is null and e.graph_id=graph_id_;

        update albion.edge as e set ceil_ =  (
            select st_makeline(
                st_3dlineinterpolatepoint(n1.geom, greatest(
                     (select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n2.hole_id 
                        and exists (select 1 from albion.edge where start_=n1.id and end_=o.id) 
                        and st_z(st_3dlineinterpolatepoint(o.geom, .5)) > st_z(st_3dlineinterpolatepoint(n2.geom, .5)))
                    *albion.inv((select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n2.hole_id 
                        and exists (select 1 from albion.edge where start_=n1.id and end_=o.id)))
                , 0)), 
                st_3dlineinterpolatepoint(n2.geom, greatest(
                     (select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n1.hole_id 
                        and exists (select 1 from albion.edge where start_=o.id and end_=n2.id) 
                        and st_z(st_3dlineinterpolatepoint(o.geom, .5)) > st_z(st_3dlineinterpolatepoint(n1.geom, .5))) 
                    *albion.inv((select sum(st_3dlength(o.geom)) from albion.node as o 
                        where o.hole_id=n1.hole_id 
                        and exists (select 1 from albion.edge where start_=o.id and end_=n2.id)))
                , 0))
            )
            from  albion.node as n1, albion.node as n2 
            where n2.id=e.end_ and n1.id=e.start_
        )
        where e.grid_id=grid_id_ and ceil_ is null and e.graph_id=graph_id_;

        return 't'::boolean;
    end;
$$
;

create or replace function albion.next_section(linestring geometry default albion.current_section_geom())
returns varchar
language plpgsql stable
as
$$
    begin
        return (
            with direction as (
                select st_rotate( linestring, pi()/2, st_centroid(linestring)) as geom
            ),
            half_direction as (
                select st_linesubstring(
                    geom, 
                    st_linelocatepoint(geom, st_centroid(
                    st_intersection(geom, linestring))), 1) as geom
                from direction
            )
            select id
            from albion.grid as g, half_direction as h
            where not st_intersects(g.geom, linestring)
            and st_intersects(g.geom, h.geom)
            order by st_linelocatepoint(h.geom, st_centroid(st_intersection(h.geom, g.geom)))
            limit 1
        );
    end;
$$
;

create or replace function albion.previous_section(linestring geometry default albion.current_section_geom())
returns varchar
language plpgsql stable
as
$$
    begin
        return (
            with direction as (
                select
                    st_rotate(
                        linestring,
                        -pi()/2, 
                        st_centroid(linestring)) as geom
            ),
            half_direction as (
                select st_linesubstring(
                    geom, 
                    st_linelocatepoint(geom, st_centroid(
                    st_intersection(geom, linestring))), 1) as geom
                from direction
            )
            select id
            from albion.grid as g, half_direction as h
            where not st_intersects(g.geom, linestring)
            and st_intersects(g.geom, h.geom)
            order by st_linelocatepoint(h.geom, st_centroid(st_intersection(h.geom, g.geom)))
            limit 1
        );
    end;
$$
;

create or replace function albion.set_line_z_at(line geometry, point geometry, z real)
returns geometry
language plpgsql immutable
as
$$
    begin
        return (
            with pt as (
                select (t.d).geom as geom, st_linelocatepoint(line, (t.d).geom) as alpha
                from (select st_dumppoints(line) as d) as t
                where not st_dwithin((t.d).geom, point, albion.snap_distance())
                union
                select st_setsrid(
                    st_makepoint(
                        st_x(point),
                        st_y(point),
                        z
                    ), $SRID) as geom, st_linelocatepoint(line, point) as alpha
            )
            select st_makeline(geom order by alpha) from pt
        );
    end;
$$
;

create or replace function albion.fix_column(graph_id varchar, point geometry)
returns varchar
language plpython3u
as
$$
    import numpy
    results = plpy.execute("""
        select 
            e.id, 
            st_z(st_lineinterpolatepoint(e.ceil_, st_linelocatepoint(e.ceil_, '{point}'::geometry))) as start_, 
            st_z(st_lineinterpolatepoint(e.wall_, st_linelocatepoint(e.wall_, '{point}'::geometry))) as end_,
            st_length(e.geom)*m.correlation_slope as snap_distance
        from albion.edge as e, albion.metadata as m
        where st_intersects(e.geom, '{point}'::geometry)
        and e.graph_id='{graph_id}'
        order by start_ desc
        """.format(graph_id=graph_id, point=point))


    if len(results) < 2:
        return 'noting to do'

    snap_distance = numpy.mean([res['snap_distance'] for res in results])

    last_start, last_end = results[0]['start_'], results[0]['end_']
    columns = [[dict(results[0])]]
    for res in results[1:]:
        if res['start_'] < last_end - snap_distance:
            # save column
            columns.append([dict(res)])
            last_start, last_end = res['start_'], res['end_']
        else:
            # append to 
            columns[-1].append(dict(res))
            last_end = res['end_']

    for col in columns:
        if len(col) == 1:
            return 'noting to do'
        elif len(col) == 2:
            start_ = .5*(col[0]['start_'] + col[1]['start_'])
            end_ = .5*(col[0]['end_'] + col[1]['end_'])
            plpy.execute("""
                update _albion.edge
                set ceil_=albion.set_line_z_at(ceil_, '{point}'::geometry, {start_}) ,
                    wall_=albion.set_line_z_at(wall_, '{point}'::geometry, {end_})
                where id in ('{e1}', '{e2}')
                """.format(point=point, e1=col[0]['id'], e2=col[1]['id'], start_=start_, end_=end_))
            return 'fixed'+str(columns)
        else:
            return 'not handled'+str(columns)

    return str(columns)
$$
;


create or replace function albion.triangulate(poly geometry)
returns geometry
language plpython3u immutable
as
$$
    import os
    from collections import defaultdict
    import math
    import re
    from subprocess import Popen, PIPE
    import numpy
    import tempfile
    from shapely import wkb
    from shapely.geometry import MultiPolygon, Polygon, Point 
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    if poly is None:
        return None

    polygons = wkb.loads(poly, True)
    if not isinstance(polygons, MultiPolygon):
        polygons = MultiPolygon([polygons])
    node_map = {}
    current_id = 0
    tempdir = tempfile.mkdtemp()
    tmp_in_file = os.path.join(tempdir, 'tmp_mesh.geo')
    result = []
    altitudes={}
    with open(tmp_in_file, "w") as geo:
        for polygon in polygons:
            if len(polygon.exterior.coords) == 4:
                result.append(polygon)
                continue
            #elif len(polygon.exterior.coords) == 5:
            #    result.append(Polygon(polygon.exterior.coords[:3]))
            #    result.append(Polygon(polygon.exterior.coords[2:]))
            #    continue

            surface_idx = []
            for ring in [polygon.exterior] + list(polygon.interiors):
                ring_idx = []
                for coord in ring.coords:
                    sc = "%.2f %.2f"%(coord[0], coord[1])
                    altitudes[sc] = coord[2] if len(coord) == 3 else 0
                    if sc in node_map:
                        ring_idx.append(node_map[sc])
                    else:
                        current_id += 1
                        ring_idx.append(current_id)
                        node_map[sc] = current_id
                        geo.write("Point(%d) = {%f, %f, %f, 9999};\n"%(current_id, coord[0], coord[1], 0))

                loop_idx = []
                for i, j in zip(ring_idx[:-1], ring_idx[1:]):
                    current_id += 1
                    geo.write("Line(%d) = {%d, %d};\n"%(current_id, i, j))
                    loop_idx.append(current_id)
                current_id += 1
                geo.write("Line Loop(%d) = {%s};\n"%(current_id, ", ".join((str(i) for i in loop_idx))))
                surface_idx.append(current_id)
            current_id += 1
            geo.write("Plane Surface(%d) = {%s};\n"%(current_id, ", ".join((str(i) for i in surface_idx))))
        
    tmp_out_file = os.path.join(tempdir, 'tmp_mesh.msh')
    cmd = ['gmsh', '-2', '-algo', 'del2d', tmp_in_file, '-o', tmp_out_file ]
    #plpy.notice("running "+' '.join(cmd))
    if os.name == 'posix':
        out, err = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
    else:
        out, err = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE).communicate()

    for e in err.split(b"\n"):
        if len(e):
            plpy.notice(e)

    with open(tmp_out_file) as out:
        while not re.match("^\$Nodes", out.readline()):
            pass
        nb_nodes = int(out.readline())
        nodes = numpy.zeros((nb_nodes, 3), dtype=numpy.float64)
        for i in range(nb_nodes):
            id_, x, y, z = out.readline().split()
            nodes[int(id_)-1, :] = float(x), float(y), 9999
        assert re.match("^\$EndNodes", out.readline())
        assert re.match("^\$Elements", out.readline())


        #with open('/tmp/debug_alti.txt', 'w') as dbg:
        #    for k, v in altitudes.items():
        #        dbg.write("{} {}\n".format(k, v))

        ## set node altitude
        #for i in range(len(nodes)):
        #    nodes[i,2] = altitudes.get("%.2f %.2f"%(nodes[i,0], nodes[i,1]), 9999)

        elements = []
        #neighbors = defaultdict(set)
        nb_elem = int(out.readline())
        for i in range(nb_elem):
            spl = out.readline().split()
            if spl[1] == '2':
                elements.append([int(n) - 1 for n in spl[-3:]])
                #neighbors[elements[-1][0]]|= set((elements[-1][1], elements[-1][2]))
                #neighbors[elements[-1][1]]|= set((elements[-1][2], elements[-1][0]))
                #neighbors[elements[-1][2]]|= set((elements[-1][0], elements[-1][1]))

        #with open('/tmp/debug_neigh.txt', 'w') as dbg:
        #    for k, v in neighbors.items():
        #        dbg.write("{} {}\n".format(k, v))


        #for l in range(4):
        #    cont = False
        #    #plpy.notice("fixing {} altitudes".format(len([i for i, in numpy.argwhere(nodes[:,2]==9999)])))
        #    for i, in numpy.argwhere(nodes[:,2]==9999):
        #        z =[nodes[n,2] for n in neighbors[i] if nodes[n,2] != 9999]
        #        if len(z):
        #            #plpy.notice("set altitude of node %.2f %.2f"%(nodes[i,0], nodes[i,1]), z)
        #            nodes[i,2] = numpy.mean(z) 
        #        else:
        #            cont = True
        #            #plpy.notice("cannot find altitude of node %.2f %.2f"%(nodes[i,0], nodes[i,1]),
        #            #    "with neighbors:", " ".join(["%.2f %.2f"%(nodes[n,0], nodes[n,1]) for n in neighbors[i]]))
        #    if not cont:
        #        break
        #plpy.notice("z in range %.2f %.2f"%(numpy.min(nodes[:,2]), numpy.max(nodes[:,2])))
            
        for element in elements:
            result.append(Polygon([(coord[0], coord[1])
                    for coord in reversed(nodes[element])]))
    result = MultiPolygon(result)
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(polygons._geom))
    return result.wkb_hex
$$
;

-- multipoly must be a tin
create or replace function albion.to_obj(multipoly geometry)
returns varchar
language plpython3u immutable
as
$$
    from shapely import wkb
    if multipoly is None:
        return ''
    m = wkb.loads(multipoly, True)
    res = ""
    node_map = {}
    elem = []
    n = 0
    for p in m:
        elem.append([])
        for c in p.exterior.coords[:-1]:
            sc = "%f %f %f" % (tuple(c))
            if sc not in node_map:
                res += "v {}\n".format(sc)
                n += 1
                node_map[sc] = n
                elem[-1].append(str(n))
            else:
                elem[-1].append(str(node_map[sc]))
    for e in elem:
        res += "f {}\n".format(" ".join(e))
    return res
$$
;

create or replace function albion.to_vtk(multiline geometry)
returns varchar
language plpython3u immutable
as
$$
    from shapely import wkb
    if multiline is None:
        return ''
    m = wkb.loads(multiline, True)
    res = "# vtk DataFile Version 4.0\nvtk output\nASCII\nDATASET POLYDATA\n"
    node_map = {}
    nodes = ""
    elem = []
    n = 0
    for l in m:
        elem.append([])
        for c in l.coords:
            sc = "%f %f %f" % (tuple(c))
            nodes += sc+"\n"
            if sc not in node_map:
                node_map[sc] = n
                elem[-1].append(str(n))
                n += 1
            else:
                elem[-1].append(str(node_map[sc]))

    res += "POINTS {} float\n".format(len(node_map))
    res += nodes

    res += "\n"
    res += "LINES {} {}\n".format(len(elem), sum([len(e)+1 for e in elem]))

    for e in elem:
        res += "{} {}\n".format(len(e), " ".join(e))
    return res
$$
;

-- triangle strip between two linestring
create or replace function albion.triangulate_edge(ceil_ geometry, wall_ geometry)
returns geometry
language plpython3u stable
as
$$
    from shapely import wkb
    from shapely.geometry import MultiPolygon, Polygon, Point
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    if ceil_ is None or wall_ is None:
        return None

    c = wkb.loads(ceil_, True)
    w = wkb.loads(wall_, True)
    ci, wi = 0, 0
    triangles = []
    while ci < (len(c.coords)-1) or wi < (len(w.coords)-1):
        if c.project(Point(c.coords[ci])) > w.project(Point(w.coords[wi])) and wi<(len(w.coords)-1): # wall forward

            triangles.append(Polygon([c.coords[ci], w.coords[wi], w.coords[wi+1]]))
            wi += 1
        else: # ceil forward
            triangles.append(Polygon([w.coords[wi], c.coords[ci+1], c.coords[ci]]))
            ci += 1
    return MultiPolygon(triangles).wkb_hex
$$
;

-- returns polygons 
create or replace function albion.section_polygons(graph_id_ varchar, grid_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    declare
        res geometry;
    begin
        with section as (
            select geom from albion.grid where id = grid_id_
        ),
        line as (
            select albion.to_section(e.ceil_, s.geom) as geom 
            from section as s, albion.edge as e
            where e.grid_id=grid_id_
            and e.graph_id=graph_id_
            union all
            select albion.to_section(e.wall_, s.geom) as geom 
            from section as s, albion.edge as e
            where e.grid_id=grid_id_
            and e.graph_id=graph_id_
            union all
            select albion.to_section(n.geom, s.geom) as geom
            from section as s,
            albion.node as n 
            join albion.hole as h on h.id=n.hole_id
            where st_intersects(st_startpoint(h.geom), s.geom)
            and n.graph_id=graph_id_

        ),
        poly as (
            select st_polygonize(geom) as geom from line
        )
        select geom from poly where not st_isempty(geom) into res;

        return (select albion.from_section(st_unaryunion(res), (select geom from albion.grid where id = grid_id_)));
    end;
$$
;

create or replace function albion.export_polygons(graph varchar)
returns varchar
language plpgsql stable
as
$$
    begin
        return (
            with poly as (
                select row_number() over() as id, (t.d).geom as geom
                from (select st_dump(albion.section_polygons(graph, id)) as d from albion.grid) as t
            ),
            pt as (
                select id, (st_dumppoints(geom)).geom as geom from poly
            )
            select string_agg(id::varchar||';'||st_x(geom)||';'||st_y(geom)||';'||st_z(geom), E'\n')
            from pt
        );
    end;
$$
;

create or replace view albion.node_section as
select f.id, f.graph_id, f.hole_id, albion.to_section(f.geom, g.geom)::geometry('LINESTRING', $SRID) as geom
from albion.node as f 
join albion.hole_grid as g on g.hole_id=f.hole_id
where g.grid_id = albion.current_section_id()
;



create or replace function albion.auto_graph(graph_id_ varchar, support_graph_id_ varchar default null)
returns boolean
language plpgsql volatile
as
$$
    begin
        raise notice 'start auto_connect';
        if support_graph_id_ is null then
            perform count(albion.auto_connect(graph_id_, id)) from albion.grid;
        else
            perform count(albion.auto_connect(graph_id_, id, support_graph_id_)) from albion.grid;
        end if;

        raise notice 'start auto_ceil_and_wall';

        perform count(albion.auto_ceil_and_wall(graph_id_, id)) from albion.grid;

        raise notice 'start fix';
        perform albion.fix_column(graph_id_, geom)
        from (
            select (st_dumppoints(st_force2d(geom))).geom as geom
            from albion.grid
        ) as t
        where not exists (select 1 from albion.collar as c where st_intersects(c.geom, t.geom))
        ;

        return 't';
    end;
$$
;


create materialized view albion.dense_grid as
with all_pt as (
    select id, grid_id, st_dumppoints(ceil_) as d from albion.edge
),
all_but_end as (
    select p.grid_id, st_collect((p.d).geom) as geom from all_pt as p
    where (p.d).path != (select max((t.d).path) from all_pt as t where t.id=p.id)
    and (p.d).path != (select min((t.d).path) from all_pt as t where t.id=p.id)
    group by p.grid_id
)
select id, coalesce(st_snap(g.geom, a.geom, albion.precision()), g.geom)::geometry('LINESTRING', $SRID) as geom
from all_but_end as a right join albion.grid as g on g.id=a.grid_id
;

create index dense_grid_geom_idx on albion.dense_grid using gist(geom)
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
    from albion.dense_grid as a
),
poly as (
    select (st_dump(st_polygonize(geom))).geom as geom from collec
)
select _albion.unique_id()::varchar as id, geom::geometry('POLYGON', $SRID) from poly where geom is not null
;

create index cell_geom_idx on albion.cell using gist(geom)
;

create materialized view albion.triangle
as
with mesh as (
    select albion.triangulate(st_collect(geom)) as geom from albion.cell
),
tri as (
    select (st_dump(st_force2d(geom))).geom from mesh
)
select _albion.unique_id()::varchar as id, cell.id cell_id, st_snap(tri.geom, cell.geom, m.precision)::geometry('POLYGON', $SRID) as geom
from tri join albion.cell on st_intersects(st_centroid(tri.geom), cell.geom), albion.metadata as m
;

create index triangle_geom_idx on albion.triangle using gist(geom)
;

-- edge ends are projected on hole start if any
-- edge intermediates points are projected vertically
create or replace function albion.project_edge(edge_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (select st_setpoint(st_setpoint(st_force2d(e.geom), 0, st_force2d(coalesce(st_startpoint(hs.geom), st_startpoint(e.geom)))),  -1, st_force2d(coalesce(st_startpoint(he.geom), st_endpoint(e.geom))))
            from albion.edge as e left join albion.node as ns on ns.id=e.start_ left join albion.node as ne on ne.id=e.end_
            left join albion.hole as he on he.id=ne.hole_id left join albion.hole as hs on hs.id=ns.hole_id
            where e.id=edge_id_
        );
    end;
$$
;

create or replace function albion.project_ceil(edge_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (select st_setpoint(st_setpoint(st_force2d(e.ceil_), 0, st_force2d(coalesce(st_startpoint(hs.geom), st_startpoint(e.ceil_)))),  -1, st_force2d(coalesce(st_startpoint(he.geom), st_endpoint(e.ceil_))))
            from albion.edge as e left join albion.node as ns on ns.id=e.start_ left join albion.node as ne on ne.id=e.end_
            left join albion.hole as he on he.id=ne.hole_id left join albion.hole as hs on hs.id=ns.hole_id
            where e.id=edge_id_
        );
    end;
$$
;

create or replace function albion.project_wall(edge_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (select st_setpoint(st_setpoint(st_force2d(e.wall_), 0, st_force2d(coalesce(st_startpoint(hs.geom), st_startpoint(e.wall_)))),  -1, st_force2d(coalesce(st_startpoint(he.geom), st_endpoint(e.wall_))))
            from albion.edge as e left join albion.node as ns on ns.id=e.start_ left join albion.node as ne on ne.id=e.end_
            left join albion.hole as he on he.id=ne.hole_id left join albion.hole as hs on hs.id=ns.hole_id
            where e.id=edge_id_
        );
    end;
$$
;


-- point projection
-- the point either lies on a grid point or is the end 

-- edge piece in cell
create or replace function albion.ceil_piece(edge_id_ varchar, cell_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            with p as (
                select (t.d).path as pth
                from (select st_dumppoints(albion.project_ceil(edge_id_)) as d) as t, albion.cell as c
                where st_intersects((t.d).geom, c.geom)
                and c.id=cell_id_
            )
            select st_makeline((t.d).geom)
            from (select st_dumppoints(ceil_) as d from albion.edge where id=edge_id_) as t
            where (t.d).path in (select pth from p)
        );
    end;
$$
;

create or replace function albion.wall_piece(edge_id_ varchar, cell_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            with p as (
                select (t.d).path as pth
                from (select st_dumppoints(albion.project_wall(edge_id_)) as d) as t, albion.cell as c
                where st_intersects((t.d).geom, c.geom)
                and c.id=cell_id_
            )
            select st_makeline((t.d).geom)
            from (select st_dumppoints(wall_) as d from albion.edge where id=edge_id_) as t
            where (t.d).path in (select pth from p)
        );
    end;
$$
;

create materialized view albion.projected_edge
as
select id, albion.project_edge(id) as geom, albion.project_ceil(id) as ceil_, albion.project_wall(id) as wall_
from albion.edge
;

create index project_edge_geom_idx on albion.projected_edge using gist(geom)
;

create index project_edge_id_idx on albion.projected_edge(id)
;

create materialized view albion.cell_edge
as
select _albion.unique_id()::varchar as id, c.id as cell_id, e.graph_id, e.id as edge_id, albion.ceil_piece(e.id, c.id)::geometry('LINESTRINGZ', 32632) as piece_ceil_, albion.wall_piece(e.id, c.id)::geometry('LINESTRINGZ', 32632) as piece_wall_,
p.ceil_ as proj_ceil_, p.wall_ as proj_wall_, e.ceil_, e.wall_
from albion.cell as c, albion.projected_edge as p join albion.edge as e on e.id=p.id
where st_intersects(p.geom, c.geom)
and st_dimension(st_intersection(p.geom, c.geom))=1
;

create index cell_edge_id_idx on albion.cell_edge(edge_id)
;


create or replace function albion.elementary_volume(graph_id_ varchar, cell_id_ varchar)
returns geometry
language plpython3u stable
as
$$
    from shapely import wkb
    from shapely.ops import linemerge
    from shapely.geometry import Point, Polygon, MultiPolygon, MultiLineString
    import numpy
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    output = []

    # get triangles
    precision = plpy.execute("""select albion.precision() as p""")[0]['p']
    res = plpy.execute("""
        select id, geom
        from albion.triangle
        where cell_id='{cell_id_}'
        """.format(cell_id_=cell_id_))
    triangles = [wkb.loads(r['geom'], True) for r in res]
    nodes = list(set((c for t in triangles for c in t.exterior.coords[:-1] )))
    node_map = {n:i for i, n in enumerate(nodes)}
    elements = [(node_map[t.exterior.coords[0]], node_map[t.exterior.coords[1]], node_map[t.exterior.coords[2]])
        for t in triangles]
    nodes = numpy.array([(c[0], c[1], 9999) for c in nodes])

    # get edges that are connected to holes that are touching the cell
    res = plpy.execute("""
        select edge_id, piece_wall_, piece_ceil_, proj_ceil_, proj_wall_, ceil_, wall_
        from albion.cell_edge
        where cell_id='{cell_id_}'
        and graph_id='{graph_id_}'
        """.format(cell_id_=cell_id_, graph_id_=graph_id_))
    if not res:
        return None

    for side in ['ceil_', 'wall_']:
        edges = [wkb.loads(r['piece_'+side], True) for r in res]
        prj_edges = {r['edge_id']:wkb.loads(r['proj_'+side], True) for r in res}
        m_edges = {r['edge_id']:wkb.loads(r[side], True) for r in res}
        edges_id = [r['edge_id'] for r in res]

        # find loops
        loop_ = []
        current_ = edges.pop()
        id_loop = [[edges_id.pop()]]
        while True:
            cont = False
            for i in range(len(edges)):
                if set((edges[i].coords[0], edges[i].coords[-1])).intersection(set((current_.coords[0], current_.coords[-1]))):
                    current_ = linemerge([current_, edges.pop(i)])
                    if isinstance(current_, MultiLineString):
                        plpy.warning('topology issue at {}'.format(current_.wkt))
                        return None
                    id_loop[-1].append(edges_id.pop())
                    cont = True
                    break
            if not cont:
                loop_.append(current_)
                if len(edges):
                    current_ = edges.pop()
                    id_loop.append([edges_id.pop()])
                else:
                    break

        # find rings
        rings = [id_ for l, id_ in zip(loop_, id_loop) if l.is_ring]

        if not rings:
            return None
        
        # set nodes altitudes
        for ring in rings:
            new_nodes = numpy.array(nodes)
            for n in range(len(nodes)):
                for edge in ring:
                    pt = Point(nodes[n][:2])
                    if pt.intersects(prj_edges[edge]):
                        idx = [i for i, c in enumerate(prj_edges[edge].coords) if pt.coords[0]==c]
                        new_nodes[n] = m_edges[edge].coords[idx[0]]
                        break
            # average z with inverse-squared distance
            without_alti = numpy.argwhere(new_nodes[:,2]==9999)
            with_alti = numpy.argwhere(new_nodes[:,2]!=9999)
            for i, in without_alti:
                dist = numpy.array([Point(new_nodes[i,:2]).distance(Point(new_nodes[o,:2])) for o, in with_alti])
                z = numpy.array([new_nodes[o,2] for o, in with_alti])
                weight = 1/dist
                new_nodes[i,2] = numpy.sum(z*weight)/numpy.sum(weight)

            if side == 'ceil_':
                output += [Polygon([new_nodes[e[0]], new_nodes[e[1]], new_nodes[e[2]]]) for e in elements]
            else:
                output += [Polygon([new_nodes[e[2]], new_nodes[e[1]], new_nodes[e[0]]]) for e in elements]

    output = MultiPolygon(output)
    geos.lgeos.GEOSSetSRID(output._geom, $SRID)

    return output.wkb_hex
$$
;

create view albion.double_edge
as
select _albion.unique_id()::varchar as id, c.geom::geometry('POLYGON', 32632) 
from albion.cell as c, albion.collar as g 
where st_intersects(c.geom, g.geom) and not st_intersects(st_exteriorring(c.geom), g.geom)
;

-- extend the graph to the next interpolated value
create or replace function albion.extend_to_interpolated(graph_id_ varchar, grid_id_ varchar)
returns boolean
language plpgsql volatile
as
$$
    begin
        with extreme as (
            select a.id, 
            not exists (
                select 1 
                from albion.edge as b 
                where st_startpoint(a.geom) in (st_startpoint(b.geom), st_endpoint(b.geom)) 
                and b.graph_id=a.graph_id 
                and b.grid_id=a.grid_id
                and b.id!=a.id) as extreme_start,
            not exists (
                select 1 
                from albion.edge as b 
                where st_endpoint(a.geom) in (st_startpoint(b.geom), st_endpoint(b.geom)) 
                and b.graph_id=a.graph_id 
                and b.grid_id=a.grid_id
                and b.id!=a.id) as extreme_end,
            albion.to_section(albion.project_edge(a.id), g.geom) as prj_geom, a.geom, a.ceil_, a.wall_
            from albion.edge as a, albion.grid as g
            where a.graph_id=graph_id_
            and a.grid_id=grid_id_
            and g.id=grid_id_
        ),
        extreme_dir as (
            select sign(st_x(st_endpoint(prj_geom))-st_x(st_startpoint(prj_geom)))*(case when extreme_start then -1 else 1 end) as dir, 
            (case when extreme_start then st_startpoint(geom) else st_endpoint(geom) end) as geom,
            (case when extreme_start then st_startpoint(ceil_) else st_endpoint(ceil_) end) as ceil_,
            (case when extreme_start then st_startpoint(wall_) else st_endpoint(wall_) end) as wall_,
            (case when extreme_start then st_startpoint(prj_geom) else st_endpoint(prj_geom) end) as prj_geom,
            id
            from extreme
            where extreme_start or extreme_end
        ),
        crossing_grid as (
            select albion.to_section(st_intersection(g.geom, cs.geom), cs.geom) as prj_geom, 
            st_intersection(g.geom, cs.geom) as geom
            from albion.grid as g, albion.grid as cs
            where g.id!=grid_id_
            and g.geom && cs.geom
            and cs.id=grid_id_
            and st_intersects(g.geom, cs.geom)
            and st_dimension(st_intersection(g.geom, cs.geom)) = 0
        ),
        extension as (
            select t.* from
            (
                select ed.id, ed.dir, ed.geom, ed.ceil_, ed.wall_, cg.geom as next, rank() over (partition by ed.id
                    order by ed.dir*(st_x(cg.prj_geom) - st_x(ed.prj_geom)) asc) as rk 
                from extreme_dir as ed, crossing_grid as cg
                where ed.dir*(st_x(cg.prj_geom) - st_x(ed.prj_geom)) > 0
            ) as t
            where t.rk=1
        ),
        next as (
            select 
            case when ex.dir > 0 then
                st_makeline(
                    ex.geom,
                    st_lineinterpolatepoint(e.geom, st_linelocatepoint(e.geom, st_intersection(e.geom, ex.next)))
                ) 
            else
                st_makeline(
                    st_lineinterpolatepoint(e.geom, st_linelocatepoint(e.geom, st_intersection(e.geom, ex.next))),
                    ex.geom
                ) 
            end as geom,
            case when ex.dir > 0 then
                st_makeline(
                    ex.ceil_,
                    st_lineinterpolatepoint(e.ceil_, st_linelocatepoint(e.ceil_, st_intersection(e.ceil_, ex.next)))
                ) 
            else
                st_makeline(
                    st_lineinterpolatepoint(e.ceil_, st_linelocatepoint(e.ceil_, st_intersection(e.ceil_, ex.next))),
                    ex.ceil_
                ) 
            end as ceil_,
            case when ex.dir > 0 then
                st_makeline(
                    ex.wall_,
                    st_lineinterpolatepoint(e.wall_, st_linelocatepoint(e.wall_, st_intersection(e.wall_, ex.next)))
                ) 
            else
                st_makeline(
                    st_lineinterpolatepoint(e.wall_, st_linelocatepoint(e.wall_, st_intersection(e.wall_, ex.next))),
                    ex.wall_
                ) 
            end as wall_
            from extension as ex, albion.edge as e
            where st_intersects(e.geom, ex.next)
            and e.graph_id=graph_id_
        )
        insert into albion.edge(geom, ceil_, wall_, graph_id, grid_id) 
        select distinct geom, ceil_, wall_, graph_id_, grid_id_ from next;

        perform albion.fix_column(graph_id_, geom) 
        from (
            select (st_dumppoints(st_force2d(geom))).geom as geom
            from albion.grid
            where id=grid_id_
        ) as t
        where not exists (select 1 from albion.collar as c where st_intersects(c.geom, t.geom))
        ;

        return 't';
    end;
$$
;

/*
with node as ( 
    select f.id, f.hole_id, st_3dlineinterpolatepoint(f.geom, .5) as geom, st_3dlineinterpolatepoint(s.geom, .5) as s_geom
    from albion.node as f join albion.hole_grid as g on f.hole_id=g.hole_id
    join albion.node as s on s.hole_id=f.hole_id 
    where g.grid_id = albion.current_section_id()
    and f.graph_id='min_u1'
    and s.graph_id='tarat_u1'
    and st_z(st_startpoint(s.geom)) >= st_z(st_3dlineinterpolatepoint(f.geom, .5)) 
    and st_z(st_3dlineinterpolatepoint(f.geom, .5)) >  st_z(st_endpoint(s.geom))
    and f.hole_id in ('GART_0845_1', 'GART_0828_1')
),
hole_pair as (
    select
        row_number() over() as id,
        h.id as right, 
        lag(h.id) over (order by st_linelocatepoint((select geom from albion.grid where id=albion.current_section_id()), st_startpoint(h.geom))) as left
    from albion.hole as h, albion.grid as g 
    where h.geom && g.geom 
    and st_intersects(st_startpoint(h.geom), g.geom)
    and g.id=albion.current_section_id()
),
possible_edge as (
    select 
        n1.id as start_, 
        n2.id as end_,
        st_makeline(n1.geom, n2.geom) as geom, 
        abs(st_z(n2.geom) - st_z(n1.geom))/st_distance(n2.geom, n1.geom) angle,
        count(1) over (partition by n1.id) as c1,  
        count(1) over (partition by n2.id) as c2, 
        rank() over (partition by p.id order by abs((st_z(n2.geom) - st_z(n1.geom))/st_distance(n1.geom, n2.geom) 
            - (st_z(n2.s_geom) - st_z(n1.s_geom))/st_distance(n1.s_geom, n2.s_geom)) asc) as rk,
         abs((st_z(n2.geom) - st_z(n1.geom))/st_distance(n1.geom, n2.geom) 
            - (st_z(n2.s_geom) - st_z(n1.s_geom))/st_distance(n1.s_geom, n2.s_geom)) as dslope
    from hole_pair as p
    join node as n1 on n1.hole_id=p.left
    join node as n2 on n2.hole_id=p.right, albion.metadata as m
    where st_distance(n1.geom, n2.geom) <  m.correlation_distance
)
select * from possible_edge;
*/
