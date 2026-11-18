-- El texto de "periodo" de los datos de ejemplo supera 40 caracteres.
ALTER TABLE registros_trafico ALTER COLUMN periodo TYPE VARCHAR(120);
