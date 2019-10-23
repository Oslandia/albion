
"""
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
    (albion.to_section(m.geom, s.anchor, s.scale))::geometry('LINESTRING', $SRID) as geom
from albion.test_mineralization as m
join _albion.hole as h on h.id=m.hole_id
join _albion.collar as c on c.id=h.collar_id
join _albion.section as s on st_intersects(s.geom, c.geom)
;
"""
