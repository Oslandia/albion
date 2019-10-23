-------------------------------------------------------------------------------
-- PUBLIC SCHEMA FOR DATABASE INTERFACE
-------------------------------------------------------------------------------

create schema albion
;

-------------------------------------------------------------------------------
-- UTILITY FUNCTIONS
-------------------------------------------------------------------------------


create or replace function albion.hole_geom(hole_id_ varchar)
returns geometry
language plpgsql stable
as
$$
    declare
        depth_max_ real;
        hole_geom_ geometry;
        x_ double precision;
        y_ double precision;
        z_ double precision;
        collar_geom_ geometry;
        path_ varchar;
    begin

        select x, y, z, depth_ from _albion.hole where id=hole_id_ into x_, y_, z_, depth_max_;
        collar_geom_ := st_setsrid(st_makepoint(x_, y_, z_), $SRID);
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
            x_ + sum(0.5 * (md2 - md1) * (sin(wd1) * sin(haz1) + sin(wd2) * sin(haz2))) over w as x,
            y_ + sum(0.5 * (md2 - md1) * (sin(wd1) * cos(haz1) + sin(wd2) * cos(haz2))) over w as y,
            z_ - sum(0.5 * (md2 - md1) * (cos(wd2) + cos(wd1))) over w as z
            from dz
            window w AS (order by md1)
        ),
        line as (
            select st_makeline(('SRID=$SRID; POINTZ('||x||' '||y||' '||z||')')::geometry order by md2 asc) as geom
            from pt
        )
        select ST_RemoveRepeatedPoints(st_addpoint(geom, collar_geom_, 0), 1.e-6)
            from line as l
        into hole_geom_;

        if hole_geom_ is not null and st_3dlength(hole_geom_) < depth_max_ and st_3dlength(hole_geom_) > 0 then
            path_ := 'too short';
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
                        ), st_numpoints(hole_geom_))
            from direction as d, last_segment as s
            into hole_geom_;

            -- hole have no deviation
        elsif hole_geom_ is null or st_3dlength(hole_geom_) = 0 then
            path_ := 'no length';
            select st_makeline( collar_geom_, st_translate(collar_geom_, 0, 0, -depth_max_)) into hole_geom_;
        end if;

        if abs(st_3dlength(hole_geom_) - depth_max_) > 1e-3 then
            raise 'hole %s %s %s %',  hole_id_, depth_max_, st_3dlength(hole_geom_), path_;
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
                st_3dlineinterpolatepoint(geom, least(from_/l, 1)),
                st_3dlineinterpolatepoint(geom, least(to_/l, 1)))
            from (select geom, st_3dlength(geom) as l from albion.hole where id=hole_id_) as t
        );
    end;
$$
;

create or replace view albion.collar as select id, st_startpoint(geom)::geometry('POINTZ', $SRID) as geom, date_, comments, depth_ from _albion.hole
;

alter view albion.collar alter id set default _albion.unique_id()::varchar
;

create or replace function albion.collar_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            new.date_ := coalesce(new.date_, now()::date::varchar);
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.hole(id, date_, depth_, x, y, z, comments)
            values(new.id, new.date_, new.depth_, st_x(new.geom), st_y(new.geom), st_z(new.geom), new.comments)
            returning id into new.id;
            update _albion.hole set geom = albion.hole_geom(new.id) where id=new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.hole set id=new.id, date_=new.date_, depth_=new.depth_, x=st_x(new.geom), y=st_y(new.geom), z=st_z(new.geom), comments=new.comments
            where id=old.id;
            update _albion.hole set geom = albion.hole_geom(new.id) where id=new.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.collar where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger collar_instead_trig
    instead of insert or update or delete on albion.collar
       for each row execute procedure albion.collar_instead_fct()
;

create view albion.metadata as select id, srid, close_collar_distance, snap_distance, precision, interpolation, end_node_relative_distance, end_node_thickness, correlation_distance, correlation_angle, parent_correlation_angle, version from _albion.metadata
;

create view albion.layer as select name, fields_definition from _albion.layer
;

create view albion.hole as select id, depth_, geom::geometry('LINESTRINGZ', $SRID) from _albion.hole
;

create view albion.deviation as select hole_id, from_, dip, azimuth from _albion.deviation
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
                    (select id from _albion.node as n
                    where .5*(new.from_+new.to_) between n.from_ and n.to_
                    and n.hole_id=new.hole_id and
                    n.graph_id=(select g.parent from _albion.graph as g where g.id=new.graph_id)));
            end if;
        end if;

        new.geom := coalesce(new.geom, albion.hole_piece(new.from_, new.to_, new.hole_id));

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
select distinct on (a.id) a.id, a.geom from albion.collar as a, albion.collar as b, _albion.metadata as m
where a.id != b.id and st_dwithin(a.geom, b.geom, m.close_collar_distance)
;

create view albion.cell as select id, a, b, c, geom::geometry('POLYGON', $SRID) from _albion.cell
;

create or replace function albion.tesselate(polygon_ geometry, lines_ geometry, points_ geometry)
returns geometry
language plpython3u volatile
as
$$
    from shapely import wkb
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True
    from fourmy import tessellate

    polygon = wkb.loads(bytes.fromhex(polygon_))
    lines = wkb.loads(bytes.fromhex(lines_)) if lines_ else None
    points = wkb.loads(bytes.fromhex(points_)) if points_ else None
    result = tessellate(polygon, lines, points)

    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(polygon._geom))
    return result.wkb_hex
$$
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
            select albion.tesselate(
                st_convexhull((select st_collect(st_force2d(geom)) from albion.collar)), 
                st_multi((select st_collectionhomogenize(st_collect(cut)) from albion.named_section)),
                st_multi((select st_collect(st_force2d(geom)) from albion.collar))
            ) as geom
        ),
        splt as (
            select (ST_Dump(geom)).geom from cell
        )
        select
            (select c.id from albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 1))),
            (select c.id from albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 2))),
            (select c.id from albion.collar as c where st_intersects(c.geom, st_pointn(st_exteriorring(s.geom), 3))),
            s.geom
        from splt as s;

        refresh materialized view albion.all_edge;

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
    anchor = wkb.loads(bytes.fromhex(anchor_))
    start = wkb.loads(bytes.fromhex(start_))
    end = wkb.loads(bytes.fromhex(end_))
    dir = numpy.array(anchor.coords[-1]) - numpy.array(anchor.coords[0])
    dir /= norm(dir)
    seg = numpy.array(end.coords[0]) - numpy.array(start.coords[0])
    seg /= norm(seg)

    return dir.dot(seg)
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


-- polygon is visible if points are on the line, or by removing the edge that touches
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
        point_on_poly geometry;
        line_od_sight geometry;
    begin
        nb_visible := 0;
        ring := st_exteriorring(poly);
        occluder := st_difference(section, ring);
        if occluder is not null then
            for i in 1..st_numpoints(ring) loop
                if st_intersects(section, st_pointn(ring, i)) then
                    nb_visible := nb_visible + 1;
                else
                    line_od_sight := st_makeline(st_closestpoint(anchor, st_pointn(ring, i)), st_pointn(ring, i));
                    --raise notice 'occluder %', st_astext(occluder);
                    --raise notice 'los %', st_astext(line_od_sight);
                    if not st_intersects(line_od_sight, occluder) then
                        nb_visible := nb_visible + 1;
                    end if;
                end if;
            end loop;
        end if;
        -- we also check that the line between a point on surface and the anchor crosses the section (we are looking "away" from anchor)
        point_on_poly := st_pointonsurface(poly);
        line_od_sight := st_makeline(st_closestpoint(anchor, point_on_poly), point_on_poly);
        return nb_visible = st_numpoints(ring) and st_intersects(line_od_sight, section);
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

create view albion.section as select id, scale, anchor::geometry('LINESTRING', $SRID), geom::geometry('MULTILINESTRING', $SRID)
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
            insert into _albion.section(id, anchor, geom, scale)
                values(new.id, new.anchor, new.geom, new.scale)
                returning id, geom into new.id, new.geom;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.section set id=new.id, anchor=new.anchor, geom=new.geom, scale=new.scale 
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


create view albion.group as
select id from _albion.group
;

create view albion.group_cell as
select gc.section_id || ' ' || gc.cell_id as id, gc.cell_id, c.geom, gc.group_id, gc.section_id
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

create or replace function albion.to_section(geom geometry, anchor geometry, z_scale real)
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
    g = wkb.loads(bytes.fromhex(geom))
    a = wkb.loads(bytes.fromhex(anchor))
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

create or replace function albion.from_section(geom_ geometry, anchor_ geometry, section_ geometry, z_scale_ real)
returns geometry
language plpython3u immutable
as
$$
    import plpy
    from shapely.ops import transform
    from shapely.geometry import LineString
    from shapely import wkb
    from shapely import geos
    from numpy import array, dot
    from numpy.linalg import norm
    geos.WKBWriter.defaults['include_srid'] = True

    if geom_ is None:
        return None
    g = wkb.loads(bytes.fromhex(geom_))
    a = wkb.loads(bytes.fromhex(anchor_))
    s = wkb.loads(bytes.fromhex(section_))

    orig = array(a.coords[0])
    dir_ = array(a.coords[-1]) - orig
    dir_ /= norm(dir_)
    nrml_ = array([-dir_[1] , dir_[0]])

    if g.type == 'LineString':
        xy = array(g.coords)
        points = []
        for p in xy:
            z = dot(nrml_, p-orig)/z_scale_
            big_distance = 100*z_scale_*z
            # intersection between section geom and line extending from point in the normal direction
            plpy.warning(big_distance, nrml_, z, p, s.intersection(LineString([p-nrml_*big_distance, p+nrml_*big_distance])).wkt)
            x, y = s.intersection(LineString([p-nrml_*big_distance, p+nrml_*big_distance])).coords[0]
            points.append((x,y,z))
        result = LineString(points)
    else:
        assert(False)
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(g._geom))
    return result.wkb_hex
$$
;

create view albion.hole_section as
select row_number() over() as id, h.id as hole_id, h.depth_, s.id as section_id,
    (albion.to_section(h.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom
from _albion.section as s
join _albion.hole as h on s.geom && h.geom and st_intersects(st_startpoint(h.geom), s.geom)
;


create view albion.node_section as
select row_number() over() as id, n.id as node_id, h.id as hole_id, n.from_, n.to_, n.graph_id, s.id as section_id,
    (albion.to_section(n.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom
from _albion.section as s
join _albion.hole as h on s.geom && h.geom and st_intersects(st_startpoint(h.geom), s.geom)
join _albion.node as n on n.hole_id = h.id
;


create or replace function albion.section_at_group(section_id_ varchar, group_id_ integer)
returns geometry
language plpgsql
as
$$
    begin
        return (
        with hull as (
            select st_multi(st_unaryunion(st_collect(c.geom))) as geom
            from _albion.cell as c
            join _albion.group_cell as gc on gc.cell_id=c.id
            where gc.section_id=section_id_ and gc.group_id <= group_id_
        ),
        hull_contour as (
            select st_exteriorring(geom) as geom from (select (st_dump(geom)).geom from hull) as t
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

create or replace view albion.possible_edge as
with tan_ang as (
    select tan(correlation_angle*pi()/180) as value, tan(parent_correlation_angle*pi()/180) as parent_value
    from _albion.metadata
),
result as (
select ns.id as start_, ne.id as end_, ns.graph_id as graph_id, (st_makeline(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5)))::geometry('LINESTRINGZ', $SRID) as geom --, null as parent

from albion.all_edge as e
join _albion.hole as hs on hs.id=e.start_
join _albion.hole as he on he.id=e.end_
join _albion.node as ns on ns.hole_id=hs.id
join _albion.node as ne on ne.hole_id=he.id, tan_ang
where ns.graph_id = ne.graph_id
and (
    (
        abs(ns.from_-ns.to_) >= abs(ne.from_-ne.to_)
        and st_z(st_startpoint(ns.geom)) + st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.value >= st_z(st_startpoint(ne.geom))
        and st_z(st_endpoint(ns.geom)) - st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.value <= st_z(st_endpoint(ne.geom))
    )
    or
    (
        abs(ns.from_-ns.to_) < abs(ne.from_-ne.to_)
        and st_z(st_startpoint(ne.geom)) + st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.value >= st_z(st_startpoint(ns.geom))
        and st_z(st_endpoint(ne.geom)) - st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.value <= st_z(st_endpoint(ns.geom))
    )
    )

and st_distance( ne.geom, ns.geom ) < ( select correlation_distance from albion.metadata )
and ns.parent is null
and ne.parent is null

union all -- for graphs with parents

select ns.id as start_, ne.id as end_, ns.graph_id as graph_id, (st_makeline(st_3dlineinterpolatepoint(ns.geom, .5), st_3dlineinterpolatepoint(ne.geom, .5)))::geometry('LINESTRINGZ', $SRID) as geom --, ns.parent as parent
from _albion.edge as pe
join _albion.node as pns on pns.id=pe.start_
join _albion.node as pne on pne.id=pe.end_
join _albion.node as ns on ns.parent=pns.id
join _albion.node as ne on ne.parent=pne.id, tan_ang
where ns.graph_id = ne.graph_id
and
    (
    (
        abs(ns.from_-ns.to_) >= abs(ne.from_-ne.to_)
        and st_z(st_startpoint(ns.geom)) + st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.parent_value + (st_z(st_3dlineinterpolatepoint(pne.geom, .5)) - st_z(st_3dlineinterpolatepoint(pns.geom, .5))) >= st_z(st_startpoint(ne.geom))
        and st_z(st_endpoint(ns.geom)) - st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.parent_value + (st_z(st_3dlineinterpolatepoint(pne.geom, .5)) - st_z(st_3dlineinterpolatepoint(pns.geom, .5))) <= st_z(st_endpoint(ne.geom))

    )
    or
    (
        abs(ns.from_-ns.to_) < abs(ne.from_-ne.to_)
        and st_z(st_startpoint(ne.geom)) + st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.parent_value  + (st_z(st_3dlineinterpolatepoint(pns.geom, .5)) - st_z(st_3dlineinterpolatepoint(pne.geom, .5))) >= st_z(st_startpoint(ns.geom)) 

        and st_z(st_endpoint(ne.geom)) - st_distance(st_startpoint(ns.geom), st_startpoint(ne.geom))*tan_ang.parent_value + (st_z(st_3dlineinterpolatepoint(pns.geom, .5)) - st_z(st_3dlineinterpolatepoint(pne.geom, .5)) ) <= st_z(st_endpoint(ns.geom)) 

    )
    )
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
    declare
        edge_ok integer;
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            new.start_ := coalesce(new.start_, (select id from _albion.node where st_intersects(geom, new.geom) and st_centroid(geom)::varchar=st_startpoint(new.geom)::varchar));
            new.end_ := coalesce(new.end_, (select id from _albion.node where st_intersects(geom, new.geom) and st_centroid(geom)::varchar=st_endpoint(new.geom)::varchar));
            if new.start_ > new.end_ then
                select new.start_, new.end_ into new.end_, new.start_;
            end if;
            -- @todo check that edge is in all_edge
            select count(1)
            from albion.all_edge as ae
            join _albion.hole as hs on hs.id=ae.start_
            join _albion.hole as he on he.id=ae.end_
            join _albion.node as ns on (ns.hole_id in (hs.id, he.id) and ns.id=new.start_)
            join _albion.node as ne on (ne.hole_id in (hs.id, he.id) and ne.id=new.end_)
            into edge_ok;
            if edge_ok = 0 then
                raise EXCEPTION 'impossible edge (not a cell edge)';
            end if;
            new.geom := st_makeline(
                st_3dlineinterpolatepoint((select geom from _albion.node where id=new.start_), .5),
                st_3dlineinterpolatepoint((select geom from _albion.node where id=new.end_), .5));
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

create view albion.edge_section as
with hole_idx as (
    select h.id, rank() over(partition by s.id order by st_linelocatepoint(s.anchor, st_startpoint(h.geom))) as rk, s.id as section_id
    from _albion.section as s
    join _albion.hole as h on s.geom && h.geom and st_intersects(s.geom, st_startpoint(h.geom))
)
select  s.id || ' ' || e.id as id, e.id as edge_id, e.start_, e.end_, e.graph_id, s.id as section_id,
    (albion.to_section(e.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom
from _albion.edge as e
join _albion.node as ns on ns.id=e.start_
join _albion.node as ne on ne.id=e.end_
join _albion.hole as hs on hs.id=ns.hole_id
join _albion.hole as he on he.id=ne.hole_id
join hole_idx as cs on cs.id=hs.id
join hole_idx as ce on ce.id=he.id,
_albion.section as s
where ((cs.rk = ce.rk + 1) or (ce.rk = cs.rk + 1))
and cs.section_id=s.id
and ce.section_id=s.id
;

create or replace function albion.edge_section_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        new_geom geometry;
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            new.start_ := coalesce(new.start_, (select node_id from albion.node_section as n, _albion.metadata as m
                    where st_dwithin(n.geom, st_startpoint(new.geom), m.snap_distance)
                    and graph_id=new.graph_id
                    order by st_distance(n.geom, st_startpoint(new.geom)) asc
                    limit 1
                    ));
            new.end_ := coalesce(new.end_, (select node_id from albion.node_section as n, _albion.metadata as m
                    where st_dwithin(n.geom, st_endpoint(new.geom), m.snap_distance)
                    and graph_id=new.graph_id
                    order by st_distance(n.geom, st_endpoint(new.geom)) asc
                    limit 1
                    ));
            if new.start_ > new.end_ then
                select new.start_, new.end_ into new.end_, new.start_;
                select st_reverse(new.geom) into new.geom;
            end if;
            select st_makeline(st_3dlineinterpolatepoint(s.geom, .5), st_3dlineinterpolatepoint(e.geom, .5))
            from _albion.node as s, _albion.node as e
            where s.id=new.start_ and e.id=new.end_ into new_geom;

            -- TODO test if edge is possible
        end if;

        if tg_op = 'INSERT' then
            insert into _albion.edge(start_, end_, graph_id, geom)
            values(new.start_, new.end_, new.graph_id, new_geom)
            returning id into new.edge_id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.edge set id=new.edge_id, start_=new.start_, end_=new.end_, graph_id=new.graph_id, new._geom=new_geom
            where id=old.edge_id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.edge where id=old.edge_id;
            return old;
        end if;
    end;
$$
;

create trigger edge_section_instead_trig
    instead of insert or update or delete on albion.edge_section
       for each row execute procedure albion.edge_section_instead_fct()
;

create view albion.possible_edge_section as
select row_number() over() as id, e.start_, e.end_, e.graph_id, s.id as section_id,
    (albion.to_section(e.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom --, e.parent
from albion.possible_edge as e
join _albion.node as ns on ns.id=e.start_
join _albion.node as ne on ne.id=e.end_
join _albion.hole as hs on hs.id=ns.hole_id
join _albion.hole as he on he.id=ne.hole_id
join _albion.section as s on s.geom && hs.geom and st_intersects(s.geom, st_startpoint(hs.geom)) and
                             s.geom && he.geom and st_intersects(s.geom, st_startpoint(he.geom))
;


create or replace function albion.elementary_volumes(cell_id_ varchar, graph_id_ varchar, geom_ geometry, holes_ varchar[], starts_ varchar[], ends_ varchar[], hole_ids_ varchar[], node_ids_ varchar[], nodes_ geometry[], end_ids_ varchar[], end_geoms_ geometry[])
returns setof geometry
language plpython3u immutable
as
$$
open('/tmp/debug_input_%s.txt'%(cell_id_), 'w').write(
    cell_id_+'\n'+
    graph_id_+'\n'+
    geom_+'\n'+
    ' '.join(holes_)+'\n'+
    ' '.join(starts_)+'\n'+
    ' '.join(ends_)+'\n'+
    ' '.join(hole_ids_)+'\n'+
    ' '.join(node_ids_)+'\n'+
    ' '.join(nodes_)+'\n'+
    ' '.join(end_ids_)+'\n'+
    ' '.join(end_geoms_)+'\n'
)
$INCLUDE_ELEMENTARY_VOLUME
for v in elementary_volumes(holes_, starts_, ends_, hole_ids_, node_ids_, nodes_, end_ids_, end_geoms_, $SRID):
    yield v
$$
;

create or replace function albion.volume_of_geom(multipoly geometry)
returns real
language plpython3u immutable
as
$$
    from shapely import wkb
    import plpy
    from numpy import array, average

    m = wkb.loads(bytes.fromhex(multipoly))
    volume = 0
    for p in m:
        r = p.exterior.coords
        v210 = r[2][0]*r[1][1]*r[0][2];
        v120 = r[1][0]*r[2][1]*r[0][2];
        v201 = r[2][0]*r[0][1]*r[1][2];
        v021 = r[0][0]*r[2][1]*r[1][2];
        v102 = r[1][0]*r[0][1]*r[2][2];
        v012 = r[0][0]*r[1][1]*r[2][2];
        volume += (1./6.)*(-v210 + v120 + v201 - v021 - v102 + v012)
    return volume
$$
;

create or replace function albion.is_closed_volume(multipoly geometry)
returns boolean
language plpython3u immutable
as
$$
    from shapely import wkb

    m = wkb.loads(bytes.fromhex(multipoly))

    edges = set()
    for p in m:
        for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
            if (e, s) in edges:
                edges.remove((e, s))
            else:
                edges.add((s, e))
    return len(edges)==0
$$
;

create or replace view albion.volume as
select id, graph_id, cell_id, triangulation, albion.volume_of_geom(triangulation) as volume--, albion.is_closed_volume(triangulation) as is_closed
from _albion.volume
;

create or replace function albion.mesh_boundarie(multipoly geometry)
returns geometry
language plpython3u immutable
as
$$
    from shapely import wkb
    from shapely.geometry import MultiLineString
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    m = wkb.loads(bytes.fromhex(multipoly))

    edges = set()
    for p in m:
        for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
            if (e, s) in edges:
                edges.remove((e, s))
            else:
                edges.add((s, e))
    result = MultiLineString(list(edges))
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(m._geom))
    return result
$$
;


create or replace function albion.volume_union(multipoly geometry)
returns geometry
language plpython3u immutable
as
$$
    from shapely import wkb
    from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
    from shapely import geos
    geos.WKBWriter.defaults['include_srid'] = True

    if multipoly is None:
        return None

    m = wkb.loads(bytes.fromhex(multipoly))

    node_map = {}
    triangles = []
    vtx = []
    for p in m:
        t = []
        for v in p.exterior.coords[:-1]:
            v = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
            if v not in node_map:
                node_map[v] = len(vtx)
                vtx.append(v)
            t.append(node_map[v])
        triangles.append(t)

    exterior = set()
    for t in triangles:
        rt = tuple(reversed(t))
        if rt in exterior:
            exterior.remove(rt)
        elif (rt[1:]+rt[:1]) in exterior:
            exterior.remove(rt[1:]+rt[:1])
        elif (rt[2:]+rt[:2]) in exterior:
            exterior.remove(rt[2:]+rt[:2])
        else:
            exterior.add(tuple(t))

    result = MultiPolygon([Polygon([vtx[p] for p in t]) for t in exterior])

    ## check for pairs of triangles with centroid less than 1cm appart
    #suspects = []
    #r = list(result)
    #for i, p in enumerate(r):
    #    for q in r[i+1:]:
    #        if p.centroid.distance(q.centroid) < .01:
    #            suspects.append(p)
    #            suspects.append(q)
    #rv = plpy.execute("SELECT albion.to_obj('{}'::geometry) as obj".format(MultiPolygon(suspects).wkb_hex))
    #open("/tmp/unclosed_suspects.obj", 'w').write(rv[0]['obj'])


    ## check generated volume is closed
    #edges = set()
    #for p in result:
    #    for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
    #        if (e, s) in edges:
    #            edges.remove((e, s))
    #        else:
    #            edges.add((s, e))
    #if (len(edges)):
    #    rv = plpy.execute("SELECT albion.to_obj('{}'::geometry) as obj".format(result.wkb_hex))
    #    open("/tmp/unclosed_volume.obj", 'w').write(rv[0]['obj'])

    #    rv = plpy.execute("SELECT albion.to_vtk('{}'::geometry) as vtk".format(MultiLineString([LineString(e) for e in edges]).wkt))
    #    open("/tmp/unclosed_border.vtk", 'w').write(rv[0]['vtk'])
    #    plpy.error("elementary volume is not closed", edges)
    #assert(len(edges)==0)

    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(m._geom))
    return result.wkb_hex
$$
;

create or replace function albion.to_obj(multipoly geometry)
returns varchar
language plpython3u immutable
as
$$
    from shapely import wkb
    if multipoly is None:
        return ''
    m = wkb.loads(bytes.fromhex(multipoly))
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
    m = wkb.loads(bytes.fromhex(multiline))
    res = "# vtk DataFile Version 4.0\nvtk output\nASCII\nDATASET POLYDATA\n"
    node_map = {}
    nodes = ""
    elem = []
    n = 0
    for l in m:
        elem.append([])
        for c in l.coords:
            sc = "%f %f %f" % (tuple(c))
            if sc not in node_map:
                nodes += sc+"\n"
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

create view albion.end_node as
select id, geom, node_id, hole_id, graph_id
from _albion.end_node
;

-- view of termination edges
create or replace view albion.half_edge as
select n.id as node_id, n.graph_id, h.id as hole_id, case when ae.start_=h.id then ae.end_ else ae.start_ end as other
from _albion.node as n
join _albion.hole as h on h.id=n.hole_id
join albion.all_edge as ae on (ae.start_=h.id or ae.end_=h.id)
except
select n.id, n.graph_id, h.id as hole_id, case when e.start_=n.id then he.id else hs.id end as other
from _albion.node as n
join _albion.hole as h on h.id=n.hole_id
join _albion.edge as e on (e.start_=n.id or e.end_=n.id)
join _albion.node as ns on ns.id=e.start_
join _albion.node as ne on ne.id=e.end_
join _albion.hole as hs on hs.id=ns.hole_id
join _albion.hole as he on he.id=ne.hole_id
;

create or replace function albion.end_node_geom(node_geom_ geometry, collar_geom_ geometry, rel_distance real default .3, thickness real default 1, nx real default null, ny real default null, nz real default null)
returns geometry
language plpython3u
as
$$
    from numpy import array
    from numpy import cross
    from shapely import wkb
    from shapely.geometry import LineString
    from shapely import geos
    from math import sqrt
    geos.WKBWriter.defaults['include_srid'] = True

    node_geom = wkb.loads(bytes.fromhex(node_geom_))
    collar_geom = wkb.loads(bytes.fromhex(collar_geom_))

    node_coords = array(node_geom.coords)
    center = .5*(node_coords[0] + node_coords[1])
    dir = array(collar_geom.coords[0]) - center
    dir[2] = 0
    dir *= rel_distance
    dir = cross(array([nx, ny, nz]), cross(dir, array([0,0,1])))
    top = center + dir + array([0,0,.5*thickness])
    bottom = center + dir - array([0,0,.5*thickness])
    result = LineString([tuple(top), tuple(bottom)])

    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(node_geom._geom))
    return result.wkb_hex
$$
;

create or replace view albion.normal as
select e.id, e.start_, e.end_,
    - (st_x(st_endpoint(geom)) - st_x(st_startpoint(geom))) * ((st_z(st_endpoint(geom)) - st_z(st_startpoint(geom)))) as nx,
    - (st_y(st_endpoint(geom)) - st_y(st_startpoint(geom))) * ((st_z(st_endpoint(geom)) - st_z(st_startpoint(geom)))) as ny,
      (st_x(st_endpoint(geom)) - st_x(st_startpoint(geom)))^2 + ((st_y(st_endpoint(geom)) - st_y(st_startpoint(geom))))^2 as nz,
      (180/pi())*atan(abs(st_z(st_endpoint(geom)) - st_z(st_startpoint(geom)))/st_length(geom)) as angl
from _albion.edge as e
;

create or replace view albion.average_normal as
with nrml as ( 
    select avg(nx) as nx, avg(ny) as ny, avg(nz) as nz, n.id
    from _albion.node as n
    left join albion.normal as e on e.start_=n.id or e.end_=n.id
    group by n.id
)
select id, coalesce(nx/sqrt(nx^2+ny^2+nz^2), 0) as nx,  coalesce(ny/sqrt(nx^2+ny^2+nz^2), 0) as ny,  coalesce(nz/sqrt(nx^2+ny^2+nz^2), 1) as nz
from nrml
;


create or replace view albion.dynamic_end_node as
select row_number() over() as id, he.graph_id, n.id as node_id, albion.end_node_geom(n.geom, st_startpoint(h.geom), m.end_node_relative_distance, end_node_thickness, nrml.nx::real, nrml.ny::real, nrml.nz::real)::geometry('LINESTRINGZ', $SRID) as geom, h.id as hole_id
from albion.half_edge as he
join _albion.node as n on n.id=he.node_id
join _albion.hole as h on h.id=he.other
join _albion.metadata as m on 't'
join albion.average_normal as nrml on nrml.id = coalesce(n.parent, n.id);
;


create or replace view albion.end_node_section as
with hole_idx as (
    select h.id, rank() over(partition by s.id order by st_linelocatepoint(s.anchor, st_startpoint(h.geom))) as rk, h.id as hole_id, s.id as section_id
    from _albion.section as s
    join _albion.hole as h on s.geom && h.geom and st_intersects(s.geom, st_startpoint(h.geom))
)
select  tn.id||' '||s.id as id, tn.id as end_node_id, n.id as node_id, tn.graph_id, s.id as section_id,
    (albion.to_section(tn.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom,
    (albion.to_section(n.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as node_geom
from _albion.end_node as tn
join _albion.node as n on n.id=tn.node_id
join _albion.hole as h on h.id=n.hole_id
join _albion.section as s on true
join hole_idx as cn on (cn.id=h.id and cn.section_id=s.id)
join hole_idx as cc on (cc.id=tn.hole_id and cc.section_id=s.id)
where cn.rk=cc.rk+1 or cc.rk=cn.rk+1
;

create or replace function albion.end_node_section_instead_fct()
returns trigger
language plpgsql
as
$$
    declare
        anchor_ geometry;
        section_ geometry;
        z_scale_ real;
    begin
        if tg_op = 'INSERT' then
            raise exception 'cannot insert en new node';
            return new;
        elsif tg_op = 'UPDATE' then
            select anchor, geom, scale from _albion.section
            where id=old.section_id into anchor_, section_, z_scale_;
            raise notice 'update % % %', new.geom, old.section_id, old.end_node_id;
            update _albion.end_node set
                geom=albion.from_section(new.geom, anchor_, section_, z_scale_)
                where id=old.end_node_id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.end_node where id=old.end_node_id;
            return old;
        end if;
    end;
$$
;

create trigger end_node_section_instead_trig
    instead of insert or update or delete on albion.end_node_section
       for each row execute procedure albion.end_node_section_instead_fct()
;


create or replace view albion.section_polygon as
with node as (
    select node_id, section_id, geom from albion.node_section
),
edge as (
    select graph_id, section_id, start_, end_ from albion.edge_section
),
poly as (
    select 
        ('SRID=32632; POLYGON(('||
                    st_x(st_startpoint(ns.geom)) ||' '||st_y(st_startpoint(ns.geom))||','||
                    st_x(st_endpoint(ns.geom))   ||' '||st_y(st_endpoint(ns.geom))  ||','||
                    st_x(st_endpoint(ne.geom))   ||' '||st_y(st_endpoint(ne.geom))  ||','||
                    st_x(st_startpoint(ne.geom)) ||' '||st_y(st_startpoint(ne.geom))||','||
                    st_x(st_startpoint(ns.geom)) ||' '||st_y(st_startpoint(ns.geom))||
                    '))')::geometry as geom, e.graph_id, e.section_id
    from edge as e
    join node as ns on ns.node_id=e.start_ and ns.section_id=e.section_id
    join node as ne on ne.node_id=e.end_ and ne.section_id=e.section_id
),
term as (
    select ('SRID=32632; POLYGON(('||
                    st_x(st_startpoint(t.node_geom)) ||' '||st_y(st_startpoint(t.node_geom))||','||
                    st_x(st_endpoint(t.node_geom))   ||' '||st_y(st_endpoint(t.node_geom))  ||','||
                    st_x(st_endpoint(t.geom))   ||' '||st_y(st_endpoint(t.geom))  ||','||
                    st_x(st_startpoint(t.geom)) ||' '||st_y(st_startpoint(t.geom))||','||
                    st_x(st_startpoint(t.node_geom)) ||' '||st_y(st_startpoint(t.node_geom))||
                    '))')::geometry as geom,
        t.graph_id, t.section_id
        from albion.end_node_section as t
)
select row_number() over() as id, st_multi(st_union(geom))::geometry('MULTIPOLYGON', 32632) as geom, graph_id, section_id
from (select * from poly union all select * from term where st_isvalid(geom)) as t
group by graph_id, section_id
;

create or replace view albion.section_intersection as
with inter as (
    select st_collectionextract((st_dump(st_intersection(a.geom, b.geom))).geom, 3) as geom
    from albion.section_polygon as a, albion.section_polygon as b
    where a.id>b.id
    and a.graph_id=b.graph_id
    and a.section_id=b.section_id
    and st_intersects(a.geom, b.geom)
    and st_area(st_intersection(a.geom, b.geom)) > 0
)
select row_number() over() as id, geom::geometry('POLYGON', $SRID)
from inter
where not st_isempty(geom)
;



create or replace view albion.dynamic_volume as
with res as (
select
c.id as cell_id, g.id as graph_id, ed.starts, ed.ends, nd.hole_ids as hole_ids, nd.ids as node_ids, nd.geoms as node_geoms, en.ids as end_ids, en.geoms as end_geoms, c.geom, ARRAY[ha.id, hb.id, hc.id] as holes
from  _albion.graph as g
join _albion.cell as c on true
join _albion.hole as ha on ha.id = c.a
join _albion.hole as hb on hb.id = c.b
join _albion.hole as hc on hc.id = c.c
join lateral (
    select coalesce(array_agg(n.id), '{}'::varchar[]) as ids, coalesce(array_agg(n.hole_id), '{}'::varchar[]) as hole_ids, coalesce(array_agg(n.geom), '{}'::geometry[]) as geoms
    from _albion.node as n
    where n.hole_id in (ha.id, hb.id, hc.id)
    and n.graph_id=g.id
) as nd on true
join lateral (
    select coalesce(array_agg(e.start_), '{}'::varchar[]) as starts, coalesce(array_agg(e.end_), '{}'::varchar[]) as ends
    from _albion.edge as e
    join _albion.node as ns on ns.id=e.start_
    join _albion.node as ne on ne.id=e.end_
    where ne.hole_id in (ha.id, hb.id, hc.id) and ns.hole_id in (ha.id, hb.id, hc.id)
    and e.graph_id=g.id
) as ed on true
join lateral (
    select coalesce(array_agg(en.node_id), '{}'::varchar[]) as ids, coalesce(array_agg(en.geom), '{}'::geometry[]) as geoms
    from _albion.end_node as en
    join _albion.node as n on n.id=en.node_id
    where en.hole_id in (c.a, c.b, c.c)
    and n.hole_id in (ha.id, hb.id, hc.id)
    and en.graph_id=g.id
) as en on true
)
select cell_id, graph_id, albion.elementary_volumes(cell_id, graph_id, st_force3d(geom), holes, starts, ends, hole_ids, node_ids, node_geoms, end_ids, end_geoms)::geometry('MULTIPOLYGONZ', $SRID) as geom, starts, ends, holes, hole_ids, node_ids, end_ids, end_geoms
from res
;


--select albion.to_obj(albion.elementary_volumes(
--        '{a, b, a}'::varchar[],
--        '{b, c, c}'::varchar[],
--        '{e, f, g}'::varchar[],
--        '{a, b, c}'::varchar[],
--        'MULTILINESTRINGZ((0 0 0, 0 0 -1), (1 0 0, 1 0 -1.1), (0 1 0, 0 1 -1.2))'::geometry))
--;
--
--select albion.to_obj(albion.elementary_volumes(
--        '{a, b, a, b, a}'::varchar[],
--        '{b, c, c, d, d}'::varchar[],
--        '{a, b, c, c}'::varchar[],
--        '{a, b, c, d}'::varchar[],
--        'MULTILINESTRINGZ((0 0 0, 0 0 -.1), (1 0 0, 1.05 0 -.11), (0.03 1 0, 0 1 -.12), (0 1 .15, 0 1 .05))'::geometry))
--;
--
--select albion.to_obj(albion.elementary_volumes(
--        '{a, b, a, b, a, c, c, e}'::varchar[],
--        '{b, c, c, d, d, e, f, f}'::varchar[],
--        '{a, b, c, c, a, b}'::varchar[],
--        '{a, b, c, d, e, f}'::varchar[],
--        'MULTILINESTRINGZ((0 0 0, 0 0 -.1), (1 0 0, 1.05 0 -.11), (0.03 1 0, 0 1 -.12), (0 1 .15, 0 1 .05), (0 0 -.3, 0 0 -.5), (1 0 -.2, 1.05 0 -.3))'::geometry))
--;

--select albion.to_obj(albion.elementary_volumes(
--        '{a, b, a, c, e, c, b}'::varchar[],
--        '{b, d, d, e, f, f, e}'::varchar[],
--        '{a, b, c, c, a, b}'::varchar[],
--        '{a, b, c, d, e, f}'::varchar[],
--        'MULTILINESTRINGZ((0 0 0, 0 0 -.1), (1 0 0, 1.05 0 -.11), (0.03 1 0, 0 1 -.12), (0 1 .15, 0 1 .05), (0 0 -.3, 0 0 -.5), (1 0 -.2, 1.05 0 -.3))'::geometry))
--;


--select albion.to_obj(albion.elementary_volumes(
--'{293309, 293309, 293309, 293411, 293411, 293310, 293310}'::varchar[],
--'{293440, 293441, 293411, 293440, 293441, 293441, 293412}'::varchar[],
--'{TMRI_0717_1, TMRI_0789_1, TMRI_0717_1, TMRI_0789_1, TMRI_0717_1, TMRI_0777_1, TMRI_0777_1, TMRI_0789_1, TMRI_0777_1, TMRI_0789_1, TMRI_0717_1, TMRI_0789_1, TMRI_0717_1, TMRI_0777_1}'::varchar[],
--'{293309, 293440, 293309, 293441, 293309, 293411, 293411, 293440, 293411, 293441, 293310, 293441, 293310, 293412}'::varchar[],
--'01050000A0787F00000E00000001020000800200000013154A5788BC1341F27E88ADD2A93F41DDC836A48ECB7640F78772A388BC13411BFEBE9FD2A93F41C0A2699C9393764001020000800200000059D97C6C85BC13418A67D48DBAA93F41FF7B08EA919F7640418F5F6685BC1341B0A9D78CBAA93F4178920C2DC58A764001020000800200000013154A5788BC1341F27E88ADD2A93F41DDC836A48ECB7640F78772A388BC13411BFEBE9FD2A93F41C0A2699C939376400102000080020000005E3F399385BC13419833B790BAA93F412744AD66C4EA764050BFC17285BC1341BB98A18EBAA93F4131BD49D291AF764001020000800200000013154A5788BC1341F27E88ADD2A93F41DDC836A48ECB7640F78772A388BC13411BFEBE9FD2A93F41C0A2699C93937640010200008002000000EAF7DBB529BC1341350EF10DD4A93F415EECEAE169E176400A74A55E2ABC1341E896ED28D4A93F4169719E7FAD947640010200008002000000EAF7DBB529BC1341350EF10DD4A93F415EECEAE169E176400A74A55E2ABC1341E896ED28D4A93F4169719E7FAD94764001020000800200000059D97C6C85BC13418A67D48DBAA93F41FF7B08EA919F7640418F5F6685BC1341B0A9D78CBAA93F4178920C2DC58A7640010200008002000000EAF7DBB529BC1341350EF10DD4A93F415EECEAE169E176400A74A55E2ABC1341E896ED28D4A93F4169719E7FAD9476400102000080020000005E3F399385BC13419833B790BAA93F412744AD66C4EA764050BFC17285BC1341BB98A18EBAA93F4131BD49D291AF764001020000800200000056B7652688BC1341EA1D85B9D2A93F41D7DF7D1858F87640E1BD403F88BC13418DABDEB2D2A93F41BFCC2B28C0DE76400102000080020000005E3F399385BC13419833B790BAA93F412744AD66C4EA764050BFC17285BC1341BB98A18EBAA93F4131BD49D291AF764001020000800200000056B7652688BC1341EA1D85B9D2A93F41D7DF7D1858F87640E1BD403F88BC13418DABDEB2D2A93F41BFCC2B28C0DE764001020000800200000042B5BD4C29BC134102FDA4FBD3A93F4171017AF02C16774018C4BC7729BC134173507003D4A93F4124AB1F80CAFF7640'::geometry))
--;

-- collect triangles of neighbor elementary volumes
create or replace function albion.triangle_intersection(t1_ geometry, t2_ geometry)
returns geometry
language plpython3u immutable
as
$$
    from shapely import geos
    from shapely.geometry import MultiPolygon, Polygon
    from shapely import wkb
    import numpy
    import plpy
    geos.WKBWriter.defaults['include_srid'] = True
    t1 = wkb.loads(bytes.fromhex(t1_))
    t2 = wkb.loads(bytes.fromhex(t2_))

    t1s = set((tuple(t.exterior.coords[0:3]) for t in t1))
    t2s = set((tuple(reversed(t.exterior.coords[0:3])) for t in t2))

    result = MultiPolygon([ Polygon(t) for t in t1s.intersection(t2s)])
    if not len(result):
        return None
    geos.lgeos.GEOSSetSRID(result._geom, geos.lgeos.GEOSGetSRID(t1._geom))
    return result.wkb_hex
$$
;


create or replace view albion.volume_section as
with touching_cell as (
    select c.id, st_intersection(s.geom, c.geom) as geom, v.triangulation, s.id as section_id, v.graph_id
    from _albion.section as s
    join _albion.cell as c on c.geom && s.geom 
    and st_intersects(c.geom, s.geom) 
    and st_length(st_intersection(s.geom, c.geom)) > 0
    join _albion.volume as v on v.cell_id = c.id
),
tri as (
    select (st_dump(albion.triangle_intersection(c1.triangulation, c2.triangulation))).geom as geom, c1.section_id, c1.graph_id
    from touching_cell as c1
    join touching_cell as c2 on c2.id > c1.id and st_length(st_intersection(c1.geom, c2.geom)) >0 and c1.section_id = c2.section_id and c1.graph_id = c2.graph_id
)
select row_number() over() as id, st_collect(geom)::geometry('MULTIPOLYGONZ', $SRID) as geom, section_id, graph_id
from tri
group by section_id, graph_id
;


create or replace view albion.named_section as 
select s.id, s.geom, s.section, rank() over (partition by section order by st_distance(s.geom, a.anchor)) as rank_, s.cut 
from _albion.named_section as s
join _albion.section as a on s.section = a.id
;

create or replace function albion.named_section_instead_fct()
returns trigger
language plpgsql
as
$$
    begin
        if tg_op in ('INSERT', 'UPDATE') then
            new.id := coalesce(new.id,  _albion.unique_id()::varchar);
            new.cut := coalesce(new.cut, (
                with geom as (
                    select st_dumppoints(new.geom) as pt
                ),
                segment as (
                    select st_makeline(lag((pt).geom) over (order by (pt).path), (pt).geom) as geom from geom
                ),
                filtered as (
                    select geom from segment as s
                    except
                    select s.geom from segment as s 
                    join _albion.named_section as o 
                    on st_intersects(o.cut, s.geom) 
                    and st_linelocatepoint(s.geom, st_intersection(o.cut, s.geom)) not in (0.0, 1.0) 
                    and st_geometrytype(st_intersection(o.cut, s.geom)) = 'ST_Point'
                )
                select st_multi(st_linemerge(st_collect(geom))) from filtered
            ));
        end if;


        if tg_op = 'INSERT' then
            insert into _albion.named_section(id, geom, cut, section)
            values(new.id, new.geom, new.cut, new.section)
            returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.named_section set id=new.id, geom=new.geom, cut=new.cut, section=new.section
            where id=old.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.named_section where id=old.id;
            return old;
        end if;
    end;
$$
;

create trigger named_section_instead_trig
    instead of insert or update or delete on albion.named_section
       for each row execute procedure albion.named_section_instead_fct()
;


create or replace function albion.next_section(section_ varchar) 
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            select n.cut 
            from albion.named_section as n
            join albion.section as s on s.id=n.section
            where s.id=section_ and st_distance(n.cut, s.anchor) > coalesce(st_distance(s.geom, s.anchor), 0)
            order by st_distance(n.cut, s.anchor) asc
            limit 1
        );
    end;
$$
;

create or replace function albion.previous_section(section_ varchar) 
returns geometry
language plpgsql stable
as
$$
    begin
        return (
            select n.cut 
            from albion.named_section as n
            join albion.section as s on s.id=n.section
            where s.id=section_ and st_distance(n.cut, s.anchor) < coalesce(st_distance(s.geom, s.anchor), 9999999)
            order by st_distance(n.cut, s.anchor) desc
            limit 1
        );
    end;
$$
;



-- TODO
-- [x] ajout de collar stérile (avec note) 
-- [x] polygone de maillage convex hull ou un trou
-- supprimer des cellules et les edges associés

-- Methode
-- import des collar et deviations dans répertoire + option data to_ from_
-- calcul des minéralisations
-- ajout de collar stériles flmaggés (verticaux)
-- creation des sections nommées
-- triangulation
-- effacer des cellules
-- creation de graph



/*
select (st_dumppoints(st_intersection(a.geom, b.geom))).geom as geom from albion.named_section as a join albion.named_section as b on st_intersects(a.geom, b.geom) and a.id > b.id
except
select st_force2d(geom) as geom from albion.collar
*/
