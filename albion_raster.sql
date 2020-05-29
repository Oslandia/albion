-------------------------------------------------------------------------------
-- Nodes/Cells from hole -> Used to create raster
-------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION st_interpolate_from_tin (LOCATION geometry, tin geometry)
    RETURNS geometry
    AS $body$
DECLARE
    az float8;
    bz float8;
    cz float8;
    a1 float8;
    a2 float8;
    b1 float8;
    b2 float8;
    c1 float8;
    c2 float8;
    z float8;
    result geometry;
    ring geometry;
    tinpoint geometry;
    a geometry;
    b geometry;
    c geometry;
BEGIN
    IF st_numgeometries (tin) <> 1 THEN
        RAISE exception 'Expecting 1 geometry in TIN polygon, got %.', st_numgeometries (tin);
    END IF;
    ring := st_exteriorring (st_geometryn (tin, 1));
    IF st_numpoints (ring) <> 4 THEN
        RAISE exception 'Expecting 3 points in TIN polygon, got %.', st_numpoints (ring);
    END IF;
    IF st_ndims (ring) < 3 THEN
        RAISE exception 'Expecting 3 dimensions in TIN polygon, got %.', st_ndims (ring);
    END IF;
    a := st_pointn (ring, 1);
    b := st_pointn (ring, 2);
    c := st_pointn (ring, 3);
    a1 := st_x (LOCATION) - st_x (a);
    a2 := st_y (LOCATION) - st_y (a);
    b1 := st_x (LOCATION) - st_x (b);
    b2 := st_y (LOCATION) - st_y (b);
    c1 := st_x (LOCATION) - st_x (c);
    c2 := st_y (LOCATION) - st_y (c);
    az := st_z (a);
    bz := st_z (b);
    cz := st_z (c);
    z := ((a1 * b2 * cz) - (a1 * bz * c2) + (a2 * bz * c1) - (a2 * b1 * cz) + (az * b1 * c2) - (az * b2 * c1)) / ((a1 * b2) - (a1 * c2) + (a2 * c1) - (a2 * b1) + (b1 * c2) - (b2 * c1));
    result := ST_SetSRID (ST_MakePoint (ST_X (LOCATION), ST_Y (LOCATION), z), ST_SRID (LOCATION));
    RETURN result;
END;
$body$
LANGUAGE plpgsql
IMMUTABLE
;

COMMENT ON FUNCTION st_interpolate_from_tin (geometry, geometry) IS 'Linear interpolation of a given points z value from a triangle polygon
 @param location is the point geometry.
 @param tin is the triangle polygon (3D).
 @returns the interpolated z value at point location.';

-- original from https://lists.osgeo.org/pipermail/postgis-users/2006-February/010984.html

CREATE OR REPLACE FUNCTION _albion.st_createregulargridz (cell_id_ character varying, code_ integer, lvl_ text, xspacing_ double precision, yspacing_ double precision)
    RETURNS TABLE (
        id bigint,
        cell_id character varying,
        "row" integer,
        col integer,
        geom geometry,
        z double precision)
    LANGUAGE plpgsql
    AS $function$
DECLARE
    xmin integer;
    xmax integer;
    ymin integer;
    ymax integer;
    width integer;
    height integer;
    geomin geometry;
BEGIN
    SELECT
        c.geom,
        floor(ST_Xmin (c.geom)),
        ceil(ST_Xmax (c.geom)),
        floor(ST_Ymin (c.geom)),
        ceil(ST_Ymax (c.geom))
    FROM
        _albion.cells c
    WHERE
        c.cell_id = cell_id_
        AND code = code_
        AND lvl = lvl_ INTO geomin,
        xmin,
        xmax,
        ymin,
        ymax;
    width := xmax - xmin;
    height := ymax - ymin;
    RETURN QUERY
    SELECT
        row_number() OVER () AS id,
        cell_id_,
        i + 1 AS ROW,
        j + 1 AS col,
        st_interpolate_from_tin (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), geomin) AS geom,
        st_z (st_interpolate_from_tin (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), geomin)) z
    FROM
        generate_series(0, (width / xspacing_)::integer) AS i,
    generate_series(0, (height / yspacing_)::integer) AS j
WHERE
    ST_Intersects (ST_SetSRID (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), ST_SRID (geomin)), geomin);
END;
$function$
;

CREATE OR REPLACE FUNCTION _albion.collar_cell (isDepthValue_ boolean)
    RETURNS TABLE (
        id varchar,
        geom geometry
    )
    AS $BODY$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        ST_MakePolygon (ST_AddPoint (ST_AddPoint (ST_MakeLine (
        ST_MakePoint(ST_X(ma.geom), ST_Y(ma.geom), CASE WHEN isDepthValue_ IS TRUE THEN ma.depth_ ELSE ST_Z(ma.geom) END),
        ST_MakePoint(ST_X(mb.geom), ST_Y(mb.geom), CASE WHEN isDepthValue_ IS TRUE  THEN mb.depth_ ELSE ST_Z(mb.geom) END)),
        ST_MakePoint(ST_X(mc.geom), ST_Y(mc.geom), CASE WHEN isDepthValue_ IS TRUE  THEN mc.depth_ ELSE ST_Z(mc.geom) END)),
        ST_MakePoint(ST_X(ma.geom), ST_Y(ma.geom), CASE WHEN isDepthValue_ IS TRUE  THEN ma.depth_ ELSE ST_Z(ma.geom) END))) geom
    FROM
        albion.cell c
    LEFT JOIN albion.collar ma ON (c.a = ma.id)
    LEFT JOIN albion.collar mb ON (c.b = mb.id)
    LEFT JOIN albion.collar mc ON (c.c = mc.id);
END;
$BODY$
LANGUAGE plpgsql
;


CREATE OR REPLACE FUNCTION _albion.st_createregulargridz_collar (cell_id_ character varying, isDepthValue_ boolean, xspacing_ double precision, yspacing_ double precision)
    RETURNS TABLE (
        id bigint,
        cell_id character varying,
        "row" integer,
        col integer,
        geom geometry,
        val double precision)
    LANGUAGE plpgsql
    AS $function$
DECLARE
    xmin integer;
    xmax integer;
    ymin integer;
    ymax integer;
    width integer;
    height integer;
    geomin geometry;
BEGIN
    SELECT
        c.geom,
        floor(ST_Xmin (c.geom)),
        ceil(ST_Xmax (c.geom)),
        floor(ST_Ymin (c.geom)),
        ceil(ST_Ymax (c.geom))
    FROM
        (SELECT * FROM _albion.collar_cell(isDepthValue_)) c
    WHERE c.id = cell_id_
    INTO geomin,
        xmin,
        xmax,
        ymin,
        ymax;
    width := xmax - xmin;
    height := ymax - ymin;
    RETURN QUERY
    SELECT
        row_number() OVER () AS id,
        cell_id_,
        i + 1 AS ROW,
        j + 1 AS col,
        st_interpolate_from_tin (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), geomin) AS geom,
        st_z (st_interpolate_from_tin (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), geomin)) z
    FROM
        generate_series(0, (width / xspacing_)::integer) AS i,
        generate_series(0, (height / yspacing_)::integer) AS j
WHERE
    ST_Intersects (ST_SetSRID (ST_Translate (ST_MakePoint (xmin, ymin), i * xspacing_, j * yspacing_), ST_SRID (geomin)), geomin);
END;
$function$
;

CREATE MATERIALIZED VIEW _albion.hole_nodes AS (
    WITH nodes AS (
        SELECT
            f.hole_id,
            f.code,
            f.comments,
            ST_SetSRID (st_3dlineinterpolatepoint (h.geom, least (f.from_ / h.depth_, 1)), ST_SRID (h.geom)) geom,
            'from' AS lvl
        FROM
            _albion.hole h,
            _albion.formation f
        WHERE
            f.hole_id = h.id
        UNION
        SELECT
            f.hole_id,
            f.code,
            f.comments,
            ST_SetSRID (st_3dlineinterpolatepoint (h.geom, least (f.to_ / h.depth_, 1)), ST_SRID (h.geom)) geom,
            'to' AS lvl
        FROM
            _albion.hole h,
            _albion.formation f
        WHERE
            f.hole_id = h.id
)
        SELECT
            row_number() OVER () id,
            hole_id,
            lvl,
            code,
            geom
        FROM nodes)
;

CREATE UNIQUE INDEX ON _albion.hole_nodes (id)
;

CREATE INDEX sidx_hole_nodes_geom ON _albion.hole_nodes USING gist (geom)
;

CREATE OR REPLACE FUNCTION _albion.create_cell (code_ integer, lvl_ text)
    RETURNS TABLE (
        id varchar,
        geom geometry
    )
    AS $BODY$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        ST_MakePolygon (ST_AddPoint (ST_AddPoint (ST_MakeLine (ma.geom, mb.geom), mc.geom), ma.geom)) geom
    FROM
        albion.cell c
    LEFT JOIN _albion.hole_nodes ma ON (c.a = ma.hole_id
            AND ma.code = code_
            AND ma.lvl = lvl_)
    LEFT JOIN _albion.hole_nodes mb ON (c.b = mb.hole_id
            AND mb.code = code_
            AND mb.lvl = lvl_)
    LEFT JOIN _albion.hole_nodes mc ON (c.c = mc.hole_id
            AND mc.code = code_
            AND mc.lvl = lvl_);
END;
$BODY$
LANGUAGE plpgsql
;

CREATE MATERIALIZED VIEW _albion.cells AS (
    WITH c AS (
    SELECT DISTINCT
        code
    FROM
        _albion.formation),
        cells AS (
        SELECT
            'to' AS lvl,
            id AS cell_id,
            c.code,
            geom
        FROM
            c,
            _albion.create_cell (c.code, 'to')
        UNION
        SELECT
            'from' AS lvl,
            id AS cell_id,
            c.code,
            geom
        FROM
            c,
            _albion.create_cell (c.code, 'from')
)
            SELECT
                row_number() OVER () id,
                *
            FROM cells
)
;

CREATE UNIQUE INDEX ON _albion.cells (id)
;

CREATE INDEX sidx_cells_geom ON _albion.cells USING gist (geom)
;
