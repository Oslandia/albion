drop index _albion.collar_geom_idx
;
alter table _albion.hole drop constraint hole_collar_id_fkey
;
drop index _albion.hole_geom_idx
;
drop index _albion.hole_collar_id_idx
;
alter table _albion.deviation drop constraint deviation_hole_id_fkey
;
drop index _albion.deviation_hole_id_idx
;
alter table _albion.radiometry drop constraint radiometry_hole_id_fkey
;
drop index _albion.radiometry_geom_idx 
;
drop index _albion.radiometry_hole_id_idx 
;
alter table _albion.resistivity drop constraint resistivity_hole_id_fkey
;
drop index _albion.resistivity_geom_idx
;
drop index _albion.resistivity_hole_id_idx
;
alter table _albion.formation drop constraint formation_hole_id_fkey
;
drop index _albion.formation_geom_idx
;
drop index _albion.formation_hole_id_idx
;
alter table _albion.lithology drop constraint lithology_hole_id_fkey
;
drop index _albion.lithology_geom_idx
;
drop index _albion.lithology_hole_id_idx
;
alter table _albion.facies drop constraint facies_hole_id_fkey
;
drop index _albion.facies_geom_idx
;
drop index _albion.facies_hole_id_idx
;
alter table _albion.chemical drop constraint chemical_hole_id_fkey
;
drop index _albion.chemical_hole_id_idx
;
alter table _albion.mineralization drop constraint mineralization_hole_id_fkey
;
drop index _albion.mineralization_geom_idx
;
drop index _albion.mineralization_hole_id_idx
;






