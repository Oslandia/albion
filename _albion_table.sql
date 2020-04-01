create table _albion.$NAME(
    id varchar primary key default _albion.unique_id()::varchar,
    hole_id varchar not null references _albion.hole(id) on delete cascade on update cascade,
    from_ real check (from_>=0),
    to_ real check (to_>=0),
    ${FIELDS_DEFINITION})
;

insert into _albion.layer(name, fields_definition) values ('$NAME', '$FIELDS_DEFINITION')
;
