-------------------------------------------------------------------------------
-- PUBLIC SCHEMA FOR DATABASE INTERFACE
-------------------------------------------------------------------------------

create schema albion
;

-------------------------------------------------------------------------------
-- UTILITY FUNCTIONS
-------------------------------------------------------------------------------

--create or replace function albion.srid()
--returns integer
--language plpgsql stable
--as
--$$
--    begin
--        return select (srid from _albion.metadata);
--    end;
--$$
--;

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

create view albion.collar as select id, geom, date_, comments from _albion.collar
;

create view albion.metadata as select id, srid, close_collar_distance, snap_distance, precision, interpolation, end_distance, end_angle, correlation_distance, correlation_angle from _albion.metadata
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


create view albion.mineralization as select id, hole_id, level_, from_, to_, oc, accu, grade, geom::geometry('LINESTRINGZ', $SRID) from _albion.mineralization
;

create or replace view albion.graph as
select id, parent from _albion.graph
;

create or replace view albion.node as 
select id, graph_id, hole_id, from_, to_, parent, geom::geometry('LINESTRINGZ', $SRID) 
from _albion.node
;

alter view albion.node alter column id set default _albion.unique_id()::varchar
;

create or replace function albion.node_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            if (select parent is not null from _albion.graph where id=new.graph_id) then
                new.parent := coalesce(new.parent,
                    (select id from _albion.node 
                    where .5*(new.from_+new.to_) between from_ and to_ 
                    and hole_id=new.hole_id and 
                    n.graph_id=(select g.parent from _albion.graph as g where g.id=new.graph_id)));
            end if;
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.node(id, graph_id, hole_id, from_, to_, geom, parent) 
            values(new.id, new.graph_id, new.hole_id, new.from_, new.to_, new.geom, new.parent)
            returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.node set id=new.id, graph_id=new.graph_id, hole_id=new.hole_id, from_=new.from_, to_=new.to_, geom=new.geom, parent=new.parent
            where id=old.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.node where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger node_instead_trig
    instead of insert or update or delete on albion.node
       for each row execute procedure albion.node_instead_fct()
;




create or replace view albion.close_collar as
select a.id, a.geom from _albion.collar as a, _albion.collar as b, _albion.metadata as m
where a.id != b.id and st_dwithin(a.geom, b.geom, m.close_collar_distance)
;

create view albion.cell as select id, a, b, c, geom::geometry('POLYGON', $SRID) from _albion.cell
;

create or replace function albion.triangulate()
returns integer
language plpgsql volatile
as
$$
    begin
        delete from _albion.cell;
        insert into _albion.cell(a, b, c, geom)
        with cell as (
            select ST_DelaunayTriangles(ST_Collect(ST_Force2D(geom))) as geom from _albion.collar
        ),
        splt as (
            select (ST_Dump(geom)).geom from cell
        )
        select 
            (select c.id from _albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 1))),
            (select c.id from _albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 2))),
            (select c.id from _albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 3))),
            s.geom
        from splt as s;

        return (select count(1) from _albion.cell);
    end;
$$
;

create or replace function albion.cos_angle(anchor_ geometry, start_ geometry, end_ geometry)
returns real
language plpython3u immutable
as
$$
    import numpy
    from numpy.linalg import norm
    from shapely import wkb
    anchor = wkb.loads(anchor_, True)
    start = wkb.loads(start_, True)
    end = wkb.loads(end_, True)
    dir = numpy.array(anchor.coords[-1]) - numpy.array(anchor.coords[0])
    dir /= norm(dir)
    seg = numpy.array(end.coords[0]) - numpy.array(start.coords[0])
    seg /= norm(seg)

    return dir.dot(seg)
$$
;

-- contour of the cells that face the line
create or replace function albion.first_section(anchor geometry)
returns geometry
language plpgsql stable
as
$$
    begin
        return (
        with hull as (
            select st_exteriorring(st_unaryunion(st_collect(geom))) as geom from _albion.cell
        ),
        seg as (
            select ST_PointN(geom, generate_series(1, ST_NPoints(geom)-1)) as sp, ST_PointN(geom, generate_series(2, ST_NPoints(geom)  )) as ep
            from hull
        ),
        facing as (
            select st_force2d(st_makeline(sp, ep)) as geom
            from seg
            where -albion.cos_angle(anchor, sp, ep) > cos(60*pi()/180)
        ),
        merged as (
            select st_linemerge(st_collect(geom)) as geom from facing
        ),
        sorted as (
            select rank() over(order by st_length(geom) desc) as rk, geom
            from (select (st_dump(geom)).geom from merged) as t
        )
        select geom from sorted where rk=1
    ); 
    end;
$$
;

create or replace function albion.is_touchingrightside(line geometry, poly geometry)
returns boolean
language plpgsql immutable
as
$$
    declare
        ring geometry;
        p1 geometry;
        p2 geometry;
        p3 geometry;
        i1 boolean;
        i2 boolean;
        i3 boolean;
        alpha1 real;
        alpha2 real;
        alpha3 real;
    begin
        ring := st_exteriorring(poly);
        if st_numpoints(ring) = 4 then

            p1 := st_pointn(ring, 1);
            p2 := st_pointn(ring, 2);
            p3 := st_pointn(ring, 3);
            i1 := st_intersects(line, p1);
            i2 := st_intersects(line, p2);
            i3 := st_intersects(line, p3);

            if i1 and i2 and i3 then
                alpha1 := st_linelocatepoint(line, p1);
                alpha2 := st_linelocatepoint(line, p2);
                alpha3 := st_linelocatepoint(line, p3);
                return (alpha1 > alpha2 and alpha2 > alpha3)
                    or (alpha2 > alpha3 and alpha3 > alpha1)
                    or (alpha3 > alpha1 and alpha1 > alpha2);
            end if;

            if i1 and i2 then
                return st_linelocatepoint(line, p1) > st_linelocatepoint(line, p2);
            end if;
            if i2 and i3 then
                return st_linelocatepoint(line, p2) > st_linelocatepoint(line, p3);
            end if;
            if i3 and i1 then
                return st_linelocatepoint(line, p3) > st_linelocatepoint(line, p1);
            end if;

        else
            for i in 1..(st_numpoints(ring)-1) loop
                p1 := st_pointn(ring, i);
                p2 := st_pointn(ring, i+1);
                if st_intersects(line, p1) and st_intersects(line, p2) then
                    return st_linelocatepoint(line, p1) > st_linelocatepoint(line, p2);
                end if;

            end loop;
        end if;
        return 'f';
    end;
$$
;

select albion.is_touchingrightside('LINESTRING(327627.06 2079630.27,327229.65 2079063.55,326442.66 2078981.33,326224.82 2079030.19,326024.52 2079029.9,325824.61 2079029.57,325424.75 2079032.28,325226.26 2079030.34,325024.4 2079029.96,324826.45 2079029.17,324625.02 2079031.02,324426.44 2079030.49,324025.18 2079031.17,323624.52 2079029.32,323024.35 2079030.9,322824.89 2079030.38,322705.36 2079915.6)'::geometry, 'POLYGON((324426.44 2079030.49,324826.45 2079029.17,324625.02 2079031.02,324426.44 2079030.49))'::geometry)
;


-- triangle is visible if points are on the line, or by removing the trinagle edge that touch
-- the line, the line of sight from anchor to point doesn't cross the line
create or replace function albion.is_visible(anchor geometry, section geometry, poly geometry)
returns boolean
language plpgsql immutable
as
$$
    declare
        nb_visible integer;
        ring geometry;
        occluder geometry;
        line_od_sight geometry;
    begin
        nb_visible := 0;
        ring := st_exteriorring(poly);
        for i in 1..st_numpoints(ring) loop
            if st_intersects(section, st_pointn(ring, i)) then
                nb_visible := nb_visible + 1;
            else
                occluder := coalesce(occluder, st_difference(section, ring));
                line_od_sight := st_makeline(st_closestpoint(anchor, st_pointn(ring, i)), st_pointn(ring, i));
                --raise notice 'occluder %', st_astext(occluder);
                --raise notice 'los %', st_astext(line_od_sight);
                if not st_intersects(line_od_sight, occluder) then
                    nb_visible := nb_visible + 1;
                end if;
            end if;
        end loop;
        return nb_visible = st_numpoints(ring);
    end;
$$
;

select albion.is_touchingrightside('LINESTRING(0 0, 2 0)'::geometry, 'POLYGON((0 0, 1 1, 2 0, 0 0))'::geometry)
;

create or replace function albion.offset_section(offset_ integer, anchor geometry, old_geom geometry)
returns geometry
language plpgsql stable
as
$$
    begin
        if offset_ > 0 then
            for r in 1..offset_ loop
                with candidates as (
                    select rank() over(order by st_distance(anchor, st_centroid(geom))) as rk,
                        st_linemerge(st_symdifference(old_geom, st_reverse(st_exteriorring(geom)))) as geom
                    from _albion.cell
                    where st_intersects(geom, old_geom)
                    and st_dimension(st_intersection(geom, old_geom)) = 1
                    and albion.is_touchingrightside(old_geom, geom) = 't'
                    and albion.is_visible(anchor, old_geom, geom) = 't'
                )
                select 
                    case when st_linelocatepoint(anchor, st_startpoint(geom)) > st_linelocatepoint(anchor, st_endpoint(geom)) 
                        then geom 
                        else st_reverse(geom)
                    end from candidates where rk=1 into old_geom;
            end loop;
            return old_geom;
        else
            return geometry;
        end if;
    end;
$$
;

create view albion.section as select id, scale, group_id, anchor::geometry('LINESTRING', $SRID), geom::geometry('LINESTRING', $SRID)
from _albion.section
;

alter view albion.section alter column id set default _albion.unique_id()::varchar
;

alter view albion.section alter column scale set default 1;
;

create or replace function albion.section_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' then
            insert into _albion.section(id, anchor, geom, scale, group_id) 
                values(new.id, new.anchor, coalesce(new.geom, albion.first_section(new.anchor)), new.scale, new.group_id) 
                returning id, geom into new.id, new.geom;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.section set id=new.id, anchor=new.anchor, geom=new.geom, scale=new.scale, group_id=new.group_id
            where id=old.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.section where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger section_instead_trig
    instead of insert or update or delete on albion.section
       for each row execute procedure albion.section_instead_fct()
;


create or replace function albion.next_group()
returns integer
language plpgsql stable
as
$$
    begin
        return (select coalesce(max(id), 0) + 1 from _albion.group);
    end;
$$
;

create view albion.group as
select id from _albion.group
;

alter view albion.group alter column id set default albion.next_group()
;

create view albion.group_cell as
select row_number() over() as id, gc.cell_id, c.geom, gc.group_id, gc.section_id
from _albion.cell as c 
join _albion.group_cell as gc on gc.cell_id=c.id
;

create or replace function albion.group_cell_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op = 'INSERT' then
            insert into _albion.group_cell(section_id, group_id, cell_id) 
                values(new.section_id, new.group_id, new.cell_id); 
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.group_cell set section_id=new.section_id, group_id=new.group_id where cell_id=new.cell_id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.group_cell where cell_id=old.cell_id and group_id=old.group_id;
            return old;
        end if;
    end;
$$
;

create trigger group_cell_instead_trig
    instead of insert or update or delete on albion.group_cell
       for each row execute procedure albion.group_cell_instead_fct()
;

create view albion.current_section as
with hull as (
    select st_unaryunion(st_collect(c.geom)) as geom, gc.section_id
    from _albion.cell as c
    join _albion.group_cell as gc on gc.cell_id=c.id
    group by gc.section_id
),
hull_contour as (
    select st_exteriorring(
        case when st_geometrytype(geom) = 'ST_Polygon' then geom
        else (st_dump(geom)).geom
        end) as geom, section_id
        from hull
),
seg as (
    select ST_PointN(geom, generate_series(1, ST_NPoints(geom)-1)) as sp, ST_PointN(geom, generate_series(2, ST_NPoints(geom)  )) as ep, section_id
    from hull_contour
),
facing as (
    select st_force2d(st_makeline(seg.sp, seg.ep)) as geom, seg.section_id
    from seg join _albion.section as s on s.id = seg.section_id
    where albion.cos_angle(s.anchor, seg.sp, seg.ep) > cos(89*pi()/180)
),
merged as (
    select st_linemerge(st_collect(facing.geom)) as geom, section_id
    from facing join _albion.section as s on s.id = facing.section_id
    group by section_id, s.geom
),
sorted as (
    select rank() over(partition by section_id order by st_length(geom) desc) as rk, geom, section_id
    from (select (st_dump(geom)).geom, section_id from merged) as t
)
select section_id as id, st_reverse(geom)::geometry('LINESTRING', $SRID) as geom from sorted where rk=1
union all
select s.id, (albion.first_section(s.anchor))::geometry('LINESTRING', $SRID) as geom from albion.section as s
where not exists (select 1 from sorted as st where st.section_id=s.id) 
;

create or replace function albion.to_section(geom geometry, anchor geometry, z_scale integer default 1.)
returns geometry
language plpython3u immutable
as
$$
    import plpy
    from shapely.ops import transform 
    from shapely.geometry import LineString
    from shapely import wkb
    from shapely import geos
    import numpy
    from numpy.linalg import norm
    geos.WKBWriter.defaults['include_srid'] = True

    if geom is None:
        return None
    g = wkb.loads(geom, True)
    a = wkb.loads(anchor, True)
    orig = numpy.array(a.coords[0])
    dir_ = numpy.array(a.coords[-1]) - orig
    dir_ /= norm(dir_)
    nrml_ = numpy.array([-dir_[1] , dir_[0]])

    if g.type == 'LineString':
        xyz = numpy.array(g.coords)
        xyz[:,:2] -= orig
        xy = xyz[:,:2].dot(dir_).reshape(-1,1)*dir_
        xy += z_scale*xyz[:,2].reshape(-1,1)*nrml_
        xy += orig
        result = LineString(xy)
    else:
        def tr(x, y, z=None):
            z = z or (0,)*len(x)
            xy = (numpy.array((x,y)).T - orig).dot(dir_).reshape(-1,1)*dir_
            xy += z_scale*numpy.array(z).reshape(-1,1)*nrml_
            xy += orig
            return zip(*((x_, y_) for x_, y_ in xy ))

        result = transform(tr, g)
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(g._geom))
    return result.wkb_hex
$$
;

--create view albion.hole_section as
--select row_number() over() as id, h.id as hole_id, h.collar_id, h.depth_, s.id as section_id, 
--    (albion.to_section(h.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.hole as h, _albion.section as s
--;
--
----create index hole_section_geom_idx on albion.hole_section using gist(geom)
----;
----
----create index hole_section_collar_id_idx on albion.hole_section(hole_id)
----;
--
--create view albion.formation_section as
--select row_number() over() as id, f.id as formation_id, h.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, 
--    (albion.to_section(f.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.formation as f
--join _albion.hole as h on h.id=f.hole_id, _albion.section as s
--;
----
----create index formation_section_geom_idx on albion.formation_section using gist(geom)
----;
----
----create index formation_section_collar_id_idx on albion.formation_section(formation_id)
----;
----
--create view albion.lithology_section as
--select row_number() over() as id, f.id as lithology_id, h.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, 
--    (albion.to_section(f.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.lithology as f
--join _albion.hole as h on h.id=f.hole_id, _albion.section as s
--;
----
----create index lithology_section_geom_idx on albion.lithology_section using gist(geom)
----;
----
----create index lithology_section_collar_id_idx on albion.lithology_section(lithology_id)
----;
----
--create view albion.facies_section as
--select row_number() over() as id, f.id as facies_id, h.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, 
--    (albion.to_section(f.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.facies as f
--join _albion.hole as h on h.id=f.hole_id, _albion.section as s
--;
----
----create index facies_section_geom_idx on albion.facies_section using gist(geom)
----;
----
----create index facies_section_collar_id_idx on albion.facies_section(facies_id)
----;
----
--create view albion.mineralization_section as
--select row_number() over() as id, m.id as mineralization_id, h.collar_id, m.from_, m.to_, m.oc, m.accu, m.grade, m.comments, s.id as section_id, 
--    (albion.to_section(m.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.mineralization as m
--join _albion.hole as h on h.id=m.hole_id, _albion.section as s
--;
----
----create index mineralization_section_geom_idx on albion.mineralization_section using gist(geom)
----;
----
----create index mineralization_section_collar_id_idx on albion.mineralization_section(mineralization_id)
----;
----
--create view albion.radiometry_section as
--select row_number() over() as id, r.id as radiometry_id, h.collar_id, r.from_, r.to_, r.gamma, s.id as section_id, 
--    (albion.to_section(r.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.radiometry as r
--join _albion.hole as h on h.id=r.hole_id, _albion.section as s
--;
----
----create index radiometry_section_geom_idx on albion.radiometry_section using gist(geom)
----;
----
----create index radiometry_section_collar_id_idx on albion.radiometry_section(radiometry_id)
----;
----
--create view albion.resistivity_section as
--select row_number() over() as id, r.id as resistivity_id, h.collar_id, r.from_, r.to_, r.rho, s.id as section_id, 
--    (albion.to_section(r.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
--from _albion.resistivity as r
--join _albion.hole as h on h.id=r.hole_id, _albion.section as s
--;
----
----create index resistivity_section_geom_idx on albion.resistivity_section using gist(geom)
----;
----
----create index resistivity_section_collar_id_idx on albion.resistivity_section(resistivity_id)
----;

--create view albion.current_hole_section as
--select row_number() over() as id, h.id as hole_id, h.collar_id, h.depth_, s.id as section_id, h.geom::geometry('LINESTRING', $SRID)
--from albion.hole_section as h
--join _albion.collar as c on c.id=h.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where h.section_id=s.id 
--;
--
--create view albion.current_formation_section as
--select row_number() over() as id, f.id as formation_id, f.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, f.geom::geometry('LINESTRING', $SRID)
--from albion.formation_section as f
--join _albion.collar as c on c.id=f.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where f.section_id=s.id 
--;
--
--create view albion.current_lithology_section as
--select row_number() over() as id, f.id as lithology_id, f.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, f.geom::geometry('LINESTRING', $SRID)
--from albion.lithology_section as f
--join _albion.collar as c on c.id=f.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where f.section_id=s.id 
--;
--
--create view albion.current_facies_section as
--select row_number() over() as id, f.id as facies_id, f.collar_id, f.from_, f.to_, f.code, f.comments, s.id as section_id, f.geom::geometry('LINESTRING', $SRID)
--from albion.facies_section as f
--join _albion.collar as c on c.id=f.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where f.section_id=s.id 
--;
--
--create view albion.current_mineralization_section as
--select row_number() over() as id, m.id as mineralization_id, m.collar_id, m.from_, m.to_, m.oc, m.accu, m.grade, m.comments, s.id as section_id, m.geom::geometry('LINESTRING', $SRID)
--from albion.mineralization_section as m
--join _albion.collar as c on c.id=m.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where m.section_id=s.id 
--;
--
--create view albion.current_radiometry_section as
--select row_number() over() as id, r.id as radiometry_id, r.collar_id, r.from_, r.to_, r.gamma, s.id as section_id, r.geom::geometry('LINESTRING', $SRID)
--from albion.radiometry_section as r
--join _albion.collar as c on c.id=r.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where r.section_id=s.id 
--;
--
--create view albion.current_resistivity_section as
--select row_number() over() as id, r.id as resistivity_id, r.collar_id, r.from_, r.to_, r.rho, s.id as section_id, r.geom::geometry('LINESTRING', $SRID)
--from albion.resistivity_section as r
--join _albion.collar as c on c.id=r.collar_id
--join _albion.section as s on st_intersects(s.geom, c.geom)
--where r.section_id=s.id 
--;

create view albion.current_node_section as
select row_number() over() as id, n.id as node_id, h.collar_id, n.from_, n.to_, n.graph_id, s.id as section_id, 
    (albion.to_section(n.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.node as n
join _albion.hole as h on h.id=n.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;

create view albion.hole_section as
select row_number() over() as id, h.id as hole_id, h.collar_id, h.depth_, s.id as section_id, 
    (albion.to_section(h.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.hole as h
join _albion.collar as c on c.id=h.collar_id, _albion.section as s
;

create view albion.current_hole_section as
select row_number() over() as id, h.id as hole_id, h.collar_id, h.depth_, s.id as section_id, 
    (albion.to_section(h.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.hole as h
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;

create view albion.current_mineralization_section as
select row_number() over() as id, m.hole_id as hole_id, h.collar_id, m.level_, m.oc, m.accu, m.grade, s.id as section_id, 
    (albion.to_section(m.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.mineralization as m
join _albion.hole as h on h.id=m.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;

create view albion.current_radiometry_section as
select row_number() over() as id, r.hole_id as hole_id, h.collar_id, r.gamma, s.id as section_id, 
    (albion.to_section(r.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.radiometry as r
join _albion.hole as h on h.id=r.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;

create view albion.current_formation_section as
select row_number() over() as id, r.hole_id as hole_id, h.collar_id, r.code, r.comments, s.id as section_id, 
    (albion.to_section(r.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.formation as r
join _albion.hole as h on h.id=r.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;

create or replace function albion.section_at_group(section_id_ varchar, group_id_ integer)
returns geometry
language plpgsql
as
$$
    begin
        return (
        with hull as (
            select st_unaryunion(st_collect(c.geom)) as geom
            from _albion.cell as c
            join _albion.group_cell as gc on gc.cell_id=c.id
            where gc.section_id=section_id_ and gc.group_id <= group_id_
        ),
        hull_contour as (
            select st_exteriorring(
                case when st_geometrytype(geom) = 'ST_Polygon' then geom
                else (st_dump(geom)).geom
                end) as geom
                from hull
        ),
        seg as (
            select ST_PointN(geom, generate_series(1, ST_NPoints(geom)-1)) as sp, ST_PointN(geom, generate_series(2, ST_NPoints(geom)  )) as ep
            from hull_contour
        ),
        facing as (
            select st_force2d(st_makeline(seg.sp, seg.ep)) as geom
            from seg join _albion.section as s on s.id = section_id_
            where albion.cos_angle(s.anchor, seg.sp, seg.ep) > cos(89*pi()/180)
        ),
        merged as (
            select st_linemerge(st_collect(facing.geom)) as geom
            from facing join _albion.section as s on s.id = section_id_
        ),
        sorted as (
            select rank() over(order by st_length(geom) desc) as rk, geom
            from (select (st_dump(geom)).geom from merged) as t
        )
        select st_reverse(geom) from sorted where rk=1
        );
    end;
$$
;

create materialized view albion.section_geom as
select row_number() over() as id, group_id, section_id, albion.section_at_group(section_id, group_id)::geometry('LINESTRING', $SRID) as geom
from (select distinct section_id, group_id from _albion.group_cell) as t
;

create or replace function albion.segmentation(
    radiometry_ real[], from_ real[], to_ real[], ic_ real, oc_ real, cut_ real, measure_thickness real default .1)
returns TABLE (level_ real, from_ real, to_ real, oc real, accu real, grade real)
language plpython3u immutable
as
$$
    import plpy
    import numpy
    import math

    IC = int(round(ic_/measure_thickness)) # nb echantillon, intercalaire stérile minimale
    OC = int(round(oc_/measure_thickness)) # nb echantillon, ouverture chantier (épaisseur mini)
    cut = cut_ # cutoff
            
    first_from_ = from_[0]

    AVP = []
    for gamma, f, t in zip(radiometry_, from_, to_):
        AVP += [gamma]*int(round((t-f)/measure_thickness))
    AVP = numpy.array(AVP, dtype=numpy.float32)

    N = len(AVP)+2*IC+OC-1
  
    # Vecteurs de travail
    # note: le code est un portage de R
    # pour garder l indexation démarrant à 1
    # on alloue N + 1 éléments, le premier élément est inutilisé
    t = numpy.zeros((N+1,))
    t [(IC+OC):(IC+OC+len(AVP))] = AVP
    v = t - cut
    v[0] = 0

    SV  = numpy.zeros((N+1,))
    SV1 = numpy.zeros((N+1,))
    SV2 = numpy.zeros((N+1,))
    SO  = numpy.zeros((N+1,))
    SO1 = numpy.zeros((N+1,))
    SO2 = numpy.zeros((N+1,))
    
    SVP = numpy.zeros((N+1,), dtype=numpy.int32)
    SOP = numpy.zeros((N+1,), dtype=numpy.int32) 

    # Initialisation
    for i in range(OC, (IC+OC-1)+1):
        SV[i] = numpy.sum(v[(i-OC+1):(i+1)])
    SVP[IC+OC-1]=IC
    SOP[IC+OC-1]=1
    
    # Calcul des valeurs
    for i in range(IC+OC, N+1):
        # Calcul de SV
        SV1[i] = SV[i-1]+v[i]
        SV2[i] = SO[i-OC]+numpy.sum(v[(i-OC+1):(i+1)])
        SV[i]  = max(SV1[i], SV2[i])
        
        # Calcul de SO
        SO1[i] = SO[i-1]
        SO2[i] = SV[i-IC]
        SO[i]  = max(SO1[i], SO2[i])
        # Limites de chantiers
        if SV1[i] >= SV2[i]:
            SVP[i] = SVP[i-1]
        else:
            SVP[i] = i - OC + 1

        if SO1[i] >  SO2[i]:
            SOP[i] = SOP[i-1]
        else:
            SOP[i] = i - IC + 1

    # Calcul des chantiers
    class Rec(object):
        def __init__(self, N, OC, IC):
            self.nbr_max = 2*int(math.ceil(N/(OC+IC)))
            self.from_ = numpy.zeros(self.nbr_max+1, dtype=numpy.int32)
            self.to = numpy.zeros(self.nbr_max+1, dtype=numpy.int32)
            self.code = numpy.zeros(self.nbr_max+1, dtype=numpy.int32)
            self.accu = numpy.zeros(self.nbr_max+1, dtype=numpy.int32)
            self.nbr = 0
            self.idx = N

    int_ = Rec(N, OC, IC)

    while SOP[int_.idx] > 1:
        # L intercalaire
        int_.nbr += 1
        int_.to[int_.nbr] = int_.idx
        int_.from_[int_.nbr] = SOP[int_.to[int_.nbr]]
        int_.code[int_.nbr] = 0
        int_.accu[int_.nbr] = 0.0
        
        # Le chantier
        int_.nbr += 1
        int_.to[int_.nbr] = int_.from_[int_.nbr-1]-1
        int_.from_[int_.nbr] = SVP[int_.to[int_.nbr]]
        int_.code[int_.nbr] = 1
        int_.accu[int_.nbr] = numpy.sum(cut+v[int_.from_[int_.nbr]:int_.to[int_.nbr]+1])

        # mise à jour l index
        int_.idx = int_.from_[int_.nbr]-1

    result = []
    for ifrom_, ito_, c in zip(int_.from_, int_.to, int_.code):
        ifrom_ -= OC+IC
        ito_ -= OC+IC-1
        if ifrom_ >= 0 and ito_ > 0 and c:
            accu = numpy.sum(AVP[ifrom_:ito_])
            grade = accu/(ito_ - ifrom_)
            oc = (ito_ - ifrom_)*measure_thickness
            result.append((cut, ifrom_*measure_thickness + first_from_, ito_*measure_thickness + first_from_, oc, accu, grade))

    return result
$$
;

select hole_id, (t.r).level_, (t.r).from_, (t.r).to_, (t.r).oc, (t.r).accu, (t.r).grade
from (
select hole_id, albion.segmentation(
    array_agg(gamma order by from_),array_agg(from_ order by from_),  array_agg(to_ order by from_), 
    1., 1., 10) as r
from _albion.radiometry
group by hole_id
) as t
;

create table albion.test_mineralization(
    id varchar primary key default _albion.unique_id()::varchar,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    level_ real,
    from_ real,
    to_ real,
    oc real,
    accu real,
    grade real,
    comments varchar,
    geom geometry('LINESTRINGZ', $SRID))
;

insert into albion.test_mineralization(hole_id, level_, from_, to_, oc, accu, grade)
select hole_id, (t.r).level_, (t.r).from_, (t.r).to_, (t.r).oc, (t.r).accu, (t.r).grade
from (
select hole_id, albion.segmentation(
    array_agg(gamma order by from_),array_agg(from_ order by from_),  array_agg(to_ order by from_), 
    1., 1., 10) as r
from _albion.radiometry
group by hole_id
) as t
;

update albion.test_mineralization set geom=albion.hole_piece(from_, to_, hole_id)
;

create view albion.current_test_mineralization_section as
select row_number() over() as id, m.hole_id, h.collar_id, m.level_, m.oc, m.accu, m.grade, s.id as section_id, 
    (albion.to_section(m.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from albion.test_mineralization as m
join _albion.hole as h on h.id=m.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;


create materialized view albion.all_edge as
select case when a < b then a else b end as start_, case when a < b then b else a end as end_
from _albion.cell
union
select case when b < c then b else c end as start_, case when b < c then c else b end as end_
from _albion.cell
union
select case when c < a then c else a end as start_, case when c < a then a else c end as end_
from _albion.cell
;

create view albion.possible_edge as
with tan_ang as (
    select tan(correlation_angle*pi()/180) as value, tan(parent_correlation_angle*pi()/180) as parent_value
    
    from _albion.metadata
),
result as (
select ns.id as start_, ne.id as end_, ns.graph_id as graph_id, (st_makeline(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5)))::geometry('LINESTRINGZ', $SRID) as geom, null as parent
from albion.all_edge as e
join _albion.hole as hs on hs.collar_id=e.start_
join _albion.hole as he on he.collar_id=e.end_
join _albion.node as ns on ns.hole_id=hs.id
join _albion.node as ne on ne.hole_id=he.id, tan_ang
where ns.graph_id = ne.graph_id
and abs(st_z(st_3dlineinterpolatepoint(ns.geom, .5))-st_z(st_3dlineinterpolatepoint(ne.geom,.5)))
    /st_distance(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5)) < tan_ang.value
and ns.parent is null
and ne.parent is null

union all

select ns.id as start_, ne.id as end_, ns.graph_id as graph_id, (st_makeline(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5)))::geometry('LINESTRINGZ', $SRID) as geom, ns.parent as parent
from _albion.edge as pe
join _albion.node as pns on pns.id=pe.start_
join _albion.node as pne on pne.id=pe.end_
join _albion.node as ns on ns.parent=pns.id
join _albion.node as ne on ne.parent=pne.id, tan_ang
where ns.graph_id = ne.graph_id
and abs( -- tan(A-B) = (tan(A)-tan(B))/(1+tan(A)tan(B)
    (
    (st_z(st_3dlineinterpolatepoint(ns.geom, .5))-st_z(st_3dlineinterpolatepoint(ne.geom,.5)))
    /st_distance(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5))
    -
    (st_z(st_3dlineinterpolatepoint(pns.geom, .5))-st_z(st_3dlineinterpolatepoint(pne.geom,.5)))
    /st_distance(st_3dlineinterpolatepoint(pns.geom, .5), st_3dlineinterpolatepoint(pne.geom, .5))
    )
    /
    (
    1.0 
    +
    (st_z(st_3dlineinterpolatepoint(ns.geom, .5))-st_z(st_3dlineinterpolatepoint(ne.geom,.5)))
    /st_distance(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5))
    *
    (st_z(st_3dlineinterpolatepoint(pns.geom, .5))-st_z(st_3dlineinterpolatepoint(pne.geom,.5)))
    /st_distance(st_3dlineinterpolatepoint(pns.geom, .5), st_3dlineinterpolatepoint(pne.geom, .5))
    )
    ) < tan_ang.parent_value
)
select row_number() over() as id, * from result
;


create view albion.edge as
select id, start_, end_, graph_id, geom::geometry('LINESTRINGZ', $SRID)
from _albion.edge
;

alter view albion.edge alter column id set default _albion.unique_id();

create or replace function albion.edge_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            new.start_ := coalesce(new.start_, (select id from _albion.node where st_intersects(geom, new.geom) and st_centroid(geom)::varchar=st_startpoint(new.geom)::varchar));
            new.end_ := coalesce(new.end_, (select id from _albion.node where st_intersects(geom, new.geom) and st_centroid(geom)::varchar=st_endpoint(new.geom)::varchar));
            if new.start_ > new.end_ then
                select new.start_, new.end_ into new.end_, new.start_;
            end if;
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.edge(id, start_, end_, graph_id, geom) 
            values(new.id, new.start_, new.end_, new.graph_id, new.geom)
            returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.edge set id=new.id, start_=new.start_, end_=new.end_, graph_id=new.graph_id, new._geom=new.geom
            where id=old.id;
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

create view albion.current_edge_section as
select row_number() over() as id, e.start_, e.end_, e.graph_id, s.id as section_id, 
    (albion.to_section(e.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom
from _albion.edge as e
join _albion.node as ns on ns.id=e.start_
join _albion.node as ne on ne.id=e.end_
join _albion.hole as hs on hs.id=ns.hole_id
join _albion.hole as he on he.id=ne.hole_id
join _albion.collar as cs on cs.id=hs.collar_id
join _albion.collar as ce on ce.id=he.collar_id
join _albion.section as s on st_intersects(s.geom, cs.geom) and st_intersects(s.geom, ce.geom)
;

create view albion.current_possible_edge_section as
select row_number() over() as id, e.start_, e.end_, e.graph_id, s.id as section_id, 
    (albion.to_section(e.geom, s.anchor))::geometry('LINESTRING', $SRID) as geom, e.parent
from albion.possible_edge as e
join _albion.node as ns on ns.id=e.start_
join _albion.node as ne on ne.id=e.end_
join _albion.hole as hs on hs.id=ns.hole_id
join _albion.hole as he on he.id=ne.hole_id
join _albion.collar as cs on cs.id=hs.collar_id
join _albion.collar as ce on ce.id=he.collar_id
join _albion.section as s on st_intersects(s.geom, cs.geom) and st_intersects(s.geom, ce.geom)
;

