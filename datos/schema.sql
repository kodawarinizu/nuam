PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS corredor (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS usuario (
    id           INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL UNIQUE,
    hash         TEXT NOT NULL,
    sal          TEXT NOT NULL,
    rol          TEXT NOT NULL CHECK (rol IN ('admin','corredor','consulta')),
    corredor_id  INTEGER REFERENCES corredor(id),
    activo       INTEGER NOT NULL DEFAULT 1,
    CHECK ((rol = 'admin') OR (corredor_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS calificacion (
    id                INTEGER PRIMARY KEY,
    corredor_id       INTEGER REFERENCES corredor(id),   -- NULL = calificación de bolsa (compartida)
    ejercicio         INTEGER NOT NULL,
    mercado           TEXT NOT NULL,
    instrumento       TEXT NOT NULL,
    fecha_pago        TEXT NOT NULL,
    secuencia         INTEGER NOT NULL,
    numero_dividendo  INTEGER NOT NULL DEFAULT 0,
    tipo_sociedad     TEXT,
    valor_historico   INTEGER,
    descripcion       TEXT,
    origen            TEXT NOT NULL,
    creado_en         TEXT NOT NULL,
    modificado_en     TEXT NOT NULL,
    CHECK ((origen = 'BOLSA') = (corredor_id IS NULL))
);

-- Llave de las calificaciones de cada corredor
CREATE UNIQUE INDEX IF NOT EXISTS ux_calificacion_corredor
    ON calificacion (corredor_id, ejercicio, mercado, instrumento, secuencia)
    WHERE corredor_id IS NOT NULL;

-- Llave de las calificaciones de bolsa (SQLite trata los NULL como distintos en UNIQUE, por eso va aparte)
CREATE UNIQUE INDEX IF NOT EXISTS ux_calificacion_bolsa
    ON calificacion (ejercicio, mercado, instrumento, secuencia)
    WHERE corredor_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_calificacion_filtros
    ON calificacion (corredor_id, ejercicio, mercado);

CREATE TABLE IF NOT EXISTS calificacion_detalle (
    calificacion_id  INTEGER NOT NULL REFERENCES calificacion(id) ON DELETE CASCADE,
    columna          INTEGER NOT NULL CHECK (columna BETWEEN 8 AND 37),
    monto            INTEGER,
    factor           TEXT,
    PRIMARY KEY (calificacion_id, columna)
);

CREATE TABLE IF NOT EXISTS log_auditoria (
    id           INTEGER PRIMARY KEY,
    fecha        TEXT NOT NULL,
    usuario_id   INTEGER,
    accion       TEXT NOT NULL,
    tabla        TEXT,
    registro_id  INTEGER,
    detalle      TEXT
);

CREATE TRIGGER IF NOT EXISTS log_sin_update
BEFORE UPDATE ON log_auditoria
BEGIN SELECT RAISE(ABORT, 'log_auditoria es inmutable'); END;

CREATE TRIGGER IF NOT EXISTS log_sin_delete
BEFORE DELETE ON log_auditoria
BEGIN SELECT RAISE(ABORT, 'log_auditoria es inmutable'); END;
