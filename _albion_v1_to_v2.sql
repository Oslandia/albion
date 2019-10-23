-- changed metadata 
alter table _albion.metadata drop column end_angle
;
alter table _albion.metadata drop column end_distance
;
alter table _albion.metadata add column end_node_relative_distance real default .3
;
alter table _albion.metadata add column end_node_thickness real default 1
;
alter table _albion.metadata add column version varchar default '2.0'
;

-- add layer table
create table _albion.layer(
    name varchar primary key,
    fields_definition text not null)
;

insert into _albion.layer(name, fields_definition)
select t.name, t.fields_definition
from (VALUES 
    ('radiometry', 'gamma real'), 
    ('resistivity', 'rho real'), 
    ('formation', 'code integer, comments varchar'), 
    ('lithology', 'code integer, comments varchar'), 
    ('facies', 'code integer, comments varchar'), 
    ('chemical', 'num_sample varchar, element varchar, thickness real, gt real, grade real, equi real, comments varchar'), 
    ('mineralization', 'level_ real, oc real, accu real, grade real, comments varchar')
    ) as t(name, fields_definition)
join information_schema.tables on table_schema = '_albion' and table_name = t.name
;

-- merge collar and hole tables
alter table _albion.hole alter column id set default _albion.unique_id()::varchar
;
alter table _albion.hole add column date_ varchar
;
alter table _albion.hole add constraint depth_check check(depth_ > 0)
;
alter table _albion.hole add column x double precision
;
alter table _albion.hole add column y double precision
;
alter table _albion.hole add column z double precision
;
alter table _albion.hole add column comments varchar
;
update _albion.hole as h set x=c.x, y=c.y, z=c.z, date_=c.date_, comments=c.comments
from _albion.collar as c where h.collar_id=c.id
;
alter table _albion.hole alter column x set not null
;
alter table _albion.hole alter column y set not null
;
alter table _albion.hole alter column z set not null
;
alter table _albion.hole drop column collar_id
;
alter table _albion.hole add constraint hole_geom_length_chk check (geom is null or abs(st_3dlength(geom) - depth_) <= 1e-3)
;

-- cell now references holes rather than collar
alter table _albion.cell drop constraint cell_a_fkey
;
alter table _albion.cell drop constraint cell_b_fkey
;
alter table _albion.cell drop constraint cell_c_fkey
;
alter table _albion.cell add constraint cell_a_fkey foreign key(a) REFERENCES _albion.hole(id);
;
alter table _albion.cell add constraint cell_b_fkey foreign key(b) REFERENCES _albion.hole(id);
;
alter table _albion.cell add constraint cell_c_fkey foreign key(c) REFERENCES _albion.hole(id);
;

-- change section
alter table _albion.section alter column geom type geometry('MULTILINESTRING', $SRID) using st_multi(geom)
;
alter table _albion.section drop column group_id
;

-- end_node now reference hole rather than collar
alter table _albion.end_node drop constraint end_node_collar_id_fkey;
;
alter table _albion.end_node rename column collar_id to hole_id
;
alter table _albion.end_node add constraint end_node_hole_id_fkey foreign key(hole_id) REFERENCES _albion.hole(id);
;

drop table _albion.collar
;
