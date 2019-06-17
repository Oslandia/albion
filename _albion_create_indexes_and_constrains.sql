vacuum analyse
;
create index collar_geom_idx on _albion.collar using gist(geom)
;
alter table _albion.hole add constraint hole_collar_id_fkey foreign key (collar_id) references _albion.collar(id)
;
create index hole_geom_idx on _albion.hole using gist(geom)
;
create index hole_collar_id_idx on _albion.hole(collar_id)
;
alter table _albion.deviation add constraint deviation_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index deviation_hole_id_idx on _albion.deviation(hole_id)
;
alter table _albion.radiometry add constraint radiometry_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index radiometry_geom_idx on _albion.radiometry using gist(geom) 
;
create index radiometry_hole_id_idx on _albion.radiometry(hole_id) 
;
alter table _albion.resistivity add constraint resistivity_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index resistivity_geom_idx on _albion.resistivity using gist(geom)
;
create index resistivity_hole_id_idx on _albion.resistivity(hole_id)
;
alter table _albion.formation add constraint formation_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index formation_geom_idx on _albion.formation using gist(geom)
;
create index formation_hole_id_idx on _albion.formation(hole_id)
;
alter table _albion.lithology add constraint lithology_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index lithology_geom_idx on _albion.lithology using gist(geom)
;
create index lithology_hole_id_idx on _albion.lithology(hole_id)
;
alter table _albion.facies add constraint facies_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index facies_geom_idx on _albion.facies using gist(geom)
;
create index facies_hole_id_idx on _albion.facies(hole_id)
;
alter table _albion.chemical add constraint chemical_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index chemical_hole_id_idx on _albion.chemical(hole_id)
;
alter table _albion.mineralization add constraint mineralization_hole_id_fkey foreign key (hole_id) references _albion.hole(id)
;
create index mineralization_geom_idx on _albion.mineralization using gist(geom)
;
create index mineralization_hole_id_idx on _albion.mineralization(hole_id)
;







