create view albion.${NAME} as
select id, hole_id, from_, to_, ${FIELDS} from _albion.${NAME}
;

create materialized view albion.${NAME}_section_geom_cache as
select s.id as section_id, h.id as hole_id, r.id as ${NAME}_id,
    (albion.to_section(
            st_makeline(st_3dlineinterpolatepoint(h.geom, least(r.from_/h.depth_, 1)), 
                        st_3dlineinterpolatepoint(h.geom, least(r.to_/h.depth_, 1)))
                , s.anchor, s.scale)) as geom,
        st_startpoint(h.geom) as collar
from _albion.section as s, _albion.${NAME} as r
join _albion.hole as h on h.id=r.hole_id
;

create index ${NAME}_section_geom_cache_${NAME}_id_idx on albion.${NAME}_section_geom_cache(${NAME}_id)
;

create index ${NAME}_section_geom_cache_colar_idx on albion.${NAME}_section_geom_cache using gist(collar)
;


create view albion.${NAME}_section as
select row_number() over() as id, r.id as ${NAME}_id, sc.section_id, r.hole_id, sc.geom::geometry('LINESTRING', ${SRID}), ${FIELDS}
from _albion.${NAME} as r
join albion.${NAME}_section_geom_cache as sc on sc.${NAME}_id = r.id
join _albion.section as s on st_intersects(s.geom, sc.collar) and sc.section_id = s.id
;

