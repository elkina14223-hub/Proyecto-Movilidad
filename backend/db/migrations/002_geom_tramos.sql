-- KAN-41: columna geoespacial de los tramos, derivada del JSON [[lat, lon], ...] de "geometria".
ALTER TABLE tramos ADD COLUMN IF NOT EXISTS geom geometry(LineString, 4326);

CREATE OR REPLACE FUNCTION tramos_set_geom() RETURNS trigger AS $$
BEGIN
  NEW.geom := ST_MakeLine(ARRAY(
    SELECT ST_SetSRID(ST_MakePoint((p->>1)::float8, (p->>0)::float8), 4326)
    FROM json_array_elements(NEW.geometria::json) AS p
  ));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tramos_geom ON tramos;
CREATE TRIGGER trg_tramos_geom BEFORE INSERT OR UPDATE OF geometria ON tramos
  FOR EACH ROW EXECUTE FUNCTION tramos_set_geom();

-- Completa los tramos que ya existían
UPDATE tramos SET geometria = geometria WHERE geom IS NULL;

CREATE INDEX IF NOT EXISTS idx_tramos_geom ON tramos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_registros_slot ON registros_trafico (tramo_id, dia_semana, hora);
