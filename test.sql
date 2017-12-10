
--create table albion.test_polygons as
--with 
--linework as (
--    select st_union((select st_collect(geom) from  albion.visible), 
--            (select st_exteriorring(st_unaryunion(st_collect(geom))) as geom from albion.cell)) as geom
--),
--poly as (
--    select st_polygonize(geom) as geom from linework
--)
--select row_number() over() as id, st_reverse(p.geom) as geom from (select (st_dump(geom)).geom from poly) as p
--;

drop view if exists albion.debug
;
create view albion.next_group as 
select row_number() over() as id, c.id as cell_id, s.id as section_id, c.geom::geometry('POLYGON', $SRID)
from _albion.cell as c, albion.current_section as s
where st_intersects(c.geom, s.geom)
and st_dimension(st_intersection(c.geom, s.geom)) = 1
and albion.is_touchingrightside(s.geom, c.geom) = 't'
;

--create or replace function albion.next_section(anchor geometry, old_geom geometry)
--returns geometry
--language plpgsql stable
--as
--$$
--    begin
--        return (
--            with result as (
--                select
--                st_linemerge(st_symdifference(old_geom, st_collect(st_exteriorring(geom)))) as geom
--                from albion.debug
--            )
--            select 
--                case when st_linelocatepoint(anchor, st_startpoint(geom)) > st_linelocatepoint(anchor, st_endpoint(geom)) 
--                    then geom 
--                    else st_reverse(geom)
--                end 
--            from result
--            );
--    end;
--$$
--;

create table albion.cut_line(
    id varchar primary key,
    section varchar references _albion.section(id) on delete cascade on update cascade,
    geom geometry('LINESTRING', $SRID)
)
;

alter table albion.cut_line alter column id set default _albion.unique_id()::varchar
;

create view albion.missing_triangle as
with two_side as (
    select c.id, c.geom, count(1) as ct
    from _albion.cell as c, albion.cut_line as l
    where st_intersects(c.geom, l.geom) 
    and st_dimension(st_intersection(c.geom, l.geom))=1
    group by c.id
)
select id, geom
from _albion.cell
except
select id, geom
from two_side
where ct >= 2
;


insert into albion.cut_line(section, geom)
with edge as (
    select 
        s.id as section, c.id as cell,
        st_makeline(st_pointn(st_exteriorring(c.geom), 1), st_pointn(st_exteriorring(c.geom), 2)) as geom,
        albion.cos_angle(s.anchor, st_pointn(st_exteriorring(c.geom), 1), st_pointn(st_exteriorring(c.geom), 2)) as cos_angle
    from _albion.cell as c, _albion.section as s
    union all
    select 
        s.id as section,  c.id as cell,
        st_makeline(st_pointn(st_exteriorring(c.geom), 2), st_pointn(st_exteriorring(c.geom), 3)) as geom,
        albion.cos_angle(s.anchor, st_pointn(st_exteriorring(c.geom), 2), st_pointn(st_exteriorring(c.geom), 3)) as cos_angle
    from _albion.cell as c, _albion.section as s
    union all
    select 
        s.id as section,  c.id as cell,
        st_makeline(st_pointn(st_exteriorring(c.geom), 3), st_pointn(st_exteriorring(c.geom), 1)) as geom,
        albion.cos_angle(s.anchor, st_pointn(st_exteriorring(c.geom), 3), st_pointn(st_exteriorring(c.geom), 1)) as cos_angle
    from _albion.cell as c, _albion.section as s
)
,
ranked_edge as (
    select rank() over(partition by cell order by cos_angle) as rk, section, cell, geom, cos_angle
    from edge
)
select section, geom
from edge where cos_angle > cos(5*pi()/180.)
;





