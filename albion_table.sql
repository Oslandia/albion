create view albion.${NAME} as
select t.id, t.hole_id, t.from_, t.to_, st_startpoint(h.geom)::geometry('POINTZ', ${SRID}) as geom, ${T_FIELDS} 
from _albion.${NAME} as t
join _albion.hole as h on h.id = t.hole_id
;

alter view albion.${NAME} alter column id set default _albion.unique_id()
;

create or replace function albion.${NAME}_instead_fct()
returns trigger
language plpgsql
as
$$$$
    begin
        if tg_op = 'INSERT' then
            insert into _albion.${NAME}(id, hole_id, from_, to_, ${FIELDS})
                values(new.id, new.hole_id, new.from_, new.to_, ${NEW_FIELDS})
                returning id into new.id;
            return new;
        elsif tg_op = 'UPDATE' then
            update _albion.${NAME} set id=new.id, hole_id=new.hole_id, from_=new.from_, to_=new.to_, ${SET_FIELDS}
            where id=old.id;
            return new;
        elsif tg_op = 'DELETE' then
            delete from _albion.${NAME} where id=old.id;
            return old;
        end if;
    end;
$$$$
;

create trigger ${NAME}_instead_trig
    instead of insert or update or delete on albion.${NAME}
       for each row execute procedure albion.${NAME}_instead_fct()
;

create materialized view albion.${NAME}_section_geom_cache as
select s.id as section_id, h.id as hole_id, t.id as ${NAME}_id,
    (albion.to_section(
            st_makeline(st_3dlineinterpolatepoint(h.geom, least(t.from_/h.depth_, 1)), 
                        st_3dlineinterpolatepoint(h.geom, least(t.to_/h.depth_, 1)))
                , s.anchor, s.scale)) as geom,
        st_startpoint(h.geom) as collar
from _albion.section as s, _albion.${NAME} as t
join _albion.hole as h on h.id=t.hole_id
;

create index ${NAME}_section_geom_cache_${NAME}_id_idx on albion.${NAME}_section_geom_cache(${NAME}_id)
;

create index ${NAME}_section_geom_cache_colar_idx on albion.${NAME}_section_geom_cache using gist(collar)
;


create view albion.${NAME}_section as
select row_number() over() as id, t.id as ${NAME}_id, sc.section_id, t.hole_id, sc.geom::geometry('LINESTRING', ${SRID}), ${T_FIELDS}
from _albion.${NAME} as t
join albion.${NAME}_section_geom_cache as sc on sc.${NAME}_id = t.id
join _albion.section as s on st_intersects(s.geom, sc.collar) and sc.section_id = s.id
;

