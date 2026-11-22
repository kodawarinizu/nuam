# Plan de desarrollo: Mantenedor de Calificaciones Tributarias NUAM (Grupo A)

Instrucciones para Claude Code. Desarrolla el proyecto **fase por fase**, en orden. Al terminar cada fase, ejecuta `pytest`, corrige lo que falle y haz un commit antes de pasar a la siguiente. Si algo de este plan es ambiguo, elige la opción más simple y anótala en `README.md` > "Decisiones".

El proyecto se crea **en la raíz de la carpeta actual** (no en una subcarpeta). Si el Excel del HDU (`HDU_Inacap_1.xlsx`) está en la carpeta, úsalo para verificar los datos de la sección 4; si no está, los datos de la sección 4 son la transcripción oficial y bastan.

## 0. Reglas del proyecto

- **Sin sobreingeniería.** Implementa solo lo que pide este plan. No agregues ORM, API web, frameworks de inyección de dependencias, temas visuales ni patrones extra.
- **Dependencias de la aplicación (solo estas):** `PySide6`, `xlwings`, `pdfplumber` (en `requirements.txt`). **Dependencias de desarrollo:** `pytest`, `reportlab` (en `requirements-dev.txt`; reportlab solo para generar los PDFs de prueba). Todo lo demás, con la biblioteca estándar (`sqlite3`, `logging`, `hashlib`, `decimal`, `dataclasses`, `csv`, `re`, `json`).
- **Python 3.11+.** Plataforma objetivo: Windows o macOS con Excel instalado (requisito de xlwings).
- **Arquitectura en capas estricta:** `ui` → `servicios` → `datos`. La interfaz nunca ejecuta SQL; los repositorios nunca contienen reglas de negocio.
- **Código en español** (nombres de módulos, funciones y mensajes), con docstrings breves y comentarios solo donde la regla de negocio no sea obvia.
- **Números:** montos como `int` (pesos). Factores como `Decimal`, redondeados a 8 decimales con `ROUND_HALF_UP`. Nunca `float` para factores.
- **Fechas:** guardar en ISO (`AAAA-MM-DD`) y mostrar como `DD-MM-AAAA`.
- **Todas las reglas de validación viven en `servicios/`**, nunca solo en la interfaz, porque la carga masiva no pasa por la interfaz.

## 1. Fuentes de los requisitos

- **HDU de NUAM** (Excel entregado por el cliente): escenarios de mantenedor, ingreso por montos y factores, modificación, eliminación, carga masiva, columna de origen y log. Lo necesario está transcrito en la sección 4.
- **Presentación de NUAM (video):** el cálculo puede venir por monto, por factor o desde una declaración jurada; los certificados llegan en PDF con los campos en distinto orden; el almacenamiento es anual y debe permitir recuperar ejercicios anteriores.
- **Plan del Grupo A:** Python, escritorio, base de datos estandarizada, xlwings, RBAC, log de auditoría inmutable y procesamiento masivo sin congelar la interfaz.
- **SII:** formato oficial del Certificado N°70 (ver sección 8).

## 2. Estructura del proyecto (en la raíz)

```
.
├── main.py
├── config.py
├── ui/
│   ├── __init__.py
│   ├── login.py
│   ├── ventana_principal.py
│   ├── modelo_tabla.py
│   ├── dialogo_calificacion.py
│   └── dialogo_carga.py
├── servicios/
│   ├── __init__.py
│   ├── errores.py
│   ├── entidades.py
│   ├── auth.py
│   ├── factores.py
│   ├── validaciones.py
│   ├── calificaciones.py
│   ├── carga_masiva.py
│   └── exportacion.py
├── datos/
│   ├── __init__.py
│   ├── schema.sql
│   ├── conexion.py
│   └── repositorios.py
├── infraestructura/
│   ├── __init__.py
│   ├── logs.py
│   ├── numeros.py
│   ├── lector_csv.py
│   ├── lector_excel.py
│   └── lector_pdf.py
├── scripts/
│   └── inicializar_bd.py
├── tests/
│   └── datos/
│       └── generar_certificados.py
├── logs/                (ignorado en git)
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini           (pythonpath = .)
├── .gitignore
├── plan_desarrollo.md
└── README.md
```

## 3. Configuración (`config.py`)

Constantes, sin archivos `.env`:

- `RUTA_BD = "nuam.db"`, `RUTA_LOGS = "logs/app.log"`
- `RANGO_SUMA_FACTORES = range(8, 20)` (columnas 8 a 19). **Decisión abierta:** un escenario del HDU dice 8–16 y la hoja de flujo y la de tipos de datos dicen 8–19; queda configurable.
- `COLUMNAS = range(8, 38)` (columnas 8 a 37).
- `COLUMNAS_CALCULADAS = range(8, 34)` (8 a 33, con fórmula en el HDU); `COLUMNAS_SOLO_INGRESO = range(34, 38)` (34 a 37, sin fórmula en el HDU: se ingresan como factor directamente).
- `DECIMALES_FACTOR = 8`
- `SECUENCIA_MINIMA = 10_000` (HDU: "secuencia evento superior a los 10.000"; 10.000 no es válida, 10.001 sí).
- `EJERCICIO_MIN, EJERCICIO_MAX = 1990, 2100`
- `MERCADOS = {"ACN": "Acciones", "CFI": "CFI", "FMU": "Fondos mutuos"}` ("ACN" viene del HDU; "CFI" y "FMU" son supuestos).
- `ORIGENES = ("MANUAL", "ARCHIVO", "PDF", "BOLSA")`
- `ROLES = ("admin", "corredor", "consulta")`
- `PBKDF2_ITERACIONES = 600_000`
- `LOG_MAX_BYTES = 1_000_000`, `LOG_BACKUPS = 5`

## 4. Datos del HDU (transcripción)

### 4.1 Nombres de las columnas 8 a 37 (hojas "3. Tipos de datos" y "3.2 Homologacion columnas")

| Col. | Nombre |
|---|---|
| 8 | Con crédito por IDPC generados a contar del 01.01.2017 |
| 9 | Con crédito por IDPC acumulados hasta el 31.12.2016 |
| 10 | Con derecho a crédito por pago de IDPC voluntario |
| 11 | Sin derecho a crédito |
| 12 | Rentas provenientes del registro RAP y Diferencia Inicial de sociedad acogida al ex Art. 14 TER A) LIR |
| 13 | Otras rentas percibidas Sin Prioridad en su orden de imputación |
| 14 | Exceso Distribuciones Desproporcionadas (N°9 Art.14 A) |
| 15 | Utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) Ley N°20.780 |
| 16 | Rentas generadas hasta el 31.12.1983 y/o utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) Ley N°21.210 |
| 17 | Rentas Exentas de Impuesto Global Complementario (IGC) (Artículo 11, Ley 18.401), Afectas a Impuesto Adicional |
| 18 | Rentas Exentas de Impuesto Global Complementario (IGC) y/o Impuesto Adicional (IA) |
| 19 | Ingresos No Constitutivos de Renta |
| 20 | No Sujetos a Restitución generados hasta el 31.12.2019 – Sin derecho a devolución |
| 21 | No Sujetos a Restitución generados hasta el 31.12.2019 – Con derecho a devolución |
| 22 | No Sujetos a Restitución generados a contar del 01.01.2020 – Sin derecho a devolución |
| 23 | No Sujetos a Restitución generados a contar del 01.01.2020 – Con derecho a devolución |
| 24 | Sujetos a Restitución (rentas afectas) – Sin derecho a devolución |
| 25 | Sujetos a Restitución (rentas afectas) – Con derecho a devolución |
| 26 | Sujetos a Restitución (rentas exentas) – Sin derecho a devolución |
| 27 | Sujetos a Restitución (rentas exentas) – Con derecho a devolución |
| 28 | Crédito por IPE (a contar del 01.01.2017) |
| 29 | Acumulados hasta el 31.12.2016, asociados a rentas afectas – Sin derecho a devolución |
| 30 | Acumulados hasta el 31.12.2016, asociados a rentas afectas – Con derecho a devolución |
| 31 | Acumulados hasta el 31.12.2016, asociados a rentas exentas (Art. 11, Ley 18.401) – Sin derecho a devolución |
| 32 | Acumulados hasta el 31.12.2016, asociados a rentas exentas (Art. 11, Ley 18.401) – Con derecho a devolución |
| 33 | Crédito por IPE (acumulados hasta el 31.12.2016) |
| 34 | Crédito por impuesto tasa adicional, Ex. Art. 21 LIR |
| 35 | Tasa Efectiva del Crédito del FUT (TEF) |
| 36 | Tasa Efectiva del Crédito del FUNT (TEX) |
| 37 | Devolución de capital Art. 17 N° 7 LIR |

Guarda esta tabla como constante `NOMBRES_COLUMNAS` en `config.py`.

### 4.2 Reglas de cálculo (hojas 3 y 3.2)

- Columnas 8 a 33: `factor = monto / suma(montos de las columnas 8 a 19)`.
- Columnas 34 a 37: sin fórmula en el HDU; se ingresan como factor.
- **Todo factor (8 a 37) debe estar entre 0 y 1** (hoja 3: "Decimal redondeado al 8vo decimal, no puede ser mayor que 1").
- La suma de los factores de `RANGO_SUMA_FACTORES` debe ser ≤ 1.

### 4.3 Formato del archivo de carga (hoja "3.1 Archivo de carga")

| Columna | Tipo | Largo | Valores / ejemplo |
|---|---|---|---|
| Ejercicio | Número | 4 | 2023 |
| Mercado | Texto | 3 | ACN |
| Instrumento | Texto | 50 | Copec |
| Fecha | Fecha | 10 | DD-MM-AAAA (12-12-2023) |
| Secuencia | Número | 10 | 123123 |
| Numero de dividendo | Número | 10 | 123456 |
| Tipo sociedad | Texto | 1 | A (abierta) o C (cerrada) |
| Valor Historico | Número | 10 | |
| Factor 8 … Factor 37 | Número | 9 | 1 entero y 8 decimales (0,92345321) |

El HDU no define el formato del archivo de **montos** (DJ 1948). **Decisión:** mismo formato, con `Monto 8` a `Monto 33` (enteros) en lugar de `Factor 8` a `Factor 33`. Como las columnas 34 a 37 no tienen fórmula, el archivo de montos puede traer además `Factor 34` a `Factor 37` (opcionales). Un archivo trae factores (8–37) o montos (8–33, más factores 34–37 opcionales), nunca montos y factores para la misma columna.

**Normalización del instrumento:** se guarda con `strip()` y en mayúsculas ("Copec", "COPEC" y "Copec " son el mismo instrumento), para que la llave y la vista corredor/bolsa los emparejen.

### 4.4 Pruebas de impacto (hoja "4. Flujo de proceso")

1. Ingresar o modificar una calificación por monto y validar que esté en el mantenedor.
2. Ingresar o modificar una calificación por factor y validar que esté en el mantenedor.
3. Ingresar o editar una calificación de un instrumento no inscrito y validar que esté en el mantenedor.
4. Cargar factores de forma masiva: si existe, se actualiza; si no, se agrega.
5. Cargar montos de forma masiva: si existe, se actualiza; si no, se agrega.
6. Validar que la información agregada quede local para ese corredor.
7. Validar que la suma de los factores 8 al 19 sea ≤ 1.
8. Al ingresar, cargar masivo o cargar externo, no se altera la información registrada en bolsa, ya que cualquier modificación debe ser local para cada corredor.

### 4.5 Bolsa y corredores (hoja "Objetivo y alcance", Consideraciones)

- La información ingresada por el corredor tiene prioridad: si el corredor ingresa una calificación, es esa la que se toma.
- Las calificaciones ingresadas o modificadas por los corredores son predominantes respecto de las ingresadas por Bolsa.
- Toda calificación ingresada por los corredores es local, para cada uno.

**Modelo que cumple las tres reglas y la prueba 8:** las calificaciones de bolsa son **compartidas** (`corredor_id` NULL) y **de solo lectura para los corredores**. Cuando un corredor ingresa o modifica una calificación que existe en bolsa, se crea **su propia copia** con su `corredor_id`; el registro de bolsa nunca se toca. En la búsqueda, el corredor ve su versión si existe y, si no, la de bolsa. Ningún origen sobrescribe al otro.

"Instrumento no inscrito": como no hay catálogo de instrumentos, el instrumento es texto libre y cualquier instrumento puede ingresarse. Anótalo en "Decisiones".

## 5. Base de datos (`datos/schema.sql`)

```sql
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
```

Notas:
- Bolsa y corredores según la sección 4.5: `corredor_id` NULL si y solo si `origen = 'BOLSA'` (lo asegura el `CHECK`). Dos índices únicos parciales separan la llave de bolsa de la de cada corredor, así que una carga de un corredor nunca choca con un registro de bolsa.
- Las validaciones de dominio (ejercicio, secuencia, tipo, mercado, origen) están en `servicios/validaciones.py`, no en `CHECK`, para tener una sola fuente de reglas y mensajes claros. Los `CHECK` se dejan solo para integridad estructural.
- `log_auditoria` no tiene llaves foráneas a propósito: el registro sobrevive aunque se elimine la calificación.
- `accion`: `INSERT`, `UPDATE`, `DELETE`, `LOGIN_OK`, `LOGIN_FALLIDO`, `CARGA_MASIVA`, `EXPORTACION`.
- `detalle`: JSON con la llave de la calificación y los campos cambiados (valor anterior y nuevo). La auditoría **sí** puede guardar montos y factores, porque está en la base protegida; el **log técnico** no.
- Los triggers protegen contra cambios desde la aplicación o SQL común, **no** contra alguien que copie o reemplace el archivo `.db`. Anótalo en el README.

## 6. Patrones a aplicar (y solo estos)

| Patrón | Dónde |
|---|---|
| Arquitectura en capas | `ui` → `servicios` → `datos`; `infraestructura` es usada por `servicios` |
| Repository | `datos/repositorios.py` (`RepositorioUsuarios`, `RepositorioCalificaciones`, `RepositorioAuditoria`) |
| Service Layer | `servicios/*.py` |
| DTO con `dataclass` | `servicios/entidades.py` (`Usuario`, `Calificacion`, `ResultadoCarga`, `FilaInvalida`) |
| Inyección por constructor | Cada servicio recibe sus repositorios; las pruebas usan SQLite `:memory:` |
| Strategy simple | `lector_csv.leer`, `lector_excel.leer` y `lector_pdf.leer` devuelven el mismo formato: `list[dict]` |
| Model-View de Qt | `ui/modelo_tabla.py` (`QAbstractTableModel`) + `QTableView` |
| Observer (señales y slots) | Lectura de archivos en segundo plano con `QThread` |
| Context manager | `with conexion:` envuelve cada operación junto con su registro de auditoría |

## 7. Fases

### Fase 0: Repositorio

- `git init`, `.gitignore` (`__pycache__/`, `*.db`, `logs/`, `.venv/`, `.pytest_cache/`), `pytest.ini` con `pythonpath = .`, `requirements.txt` y `requirements-dev.txt` con versiones fijas. `requirements-dev.txt` empieza con `-r requirements.txt`. Commit inicial.

### Fase 1: Base de datos y repositorios

Archivos: `config.py`, `datos/schema.sql`, `datos/conexion.py`, `datos/repositorios.py`, `servicios/entidades.py`, `servicios/errores.py`, `scripts/inicializar_bd.py`.

- `conexion.py`: `crear_conexion(ruta)` verifica primero que `sqlite3.sqlite_version` sea ≥ 3.35 (necesario para `RETURNING` y el upsert con índice parcial) y, si no, lanza un `RuntimeError` con un mensaje claro que indique la versión encontrada y la mínima. Luego activa `PRAGMA foreign_keys = ON`, usa `row_factory = sqlite3.Row` y ejecuta `schema.sql`. La conexión se usa **solo desde el hilo principal**.
- Repositorios con SQL **parametrizado** (`?`) siempre.
- `RepositorioCalificaciones`:
  - `obtener_por_llave(corredor_id, ejercicio, mercado, instrumento, secuencia)`: con `corredor_id` NULL busca en bolsa (`corredor_id IS NULL`, nunca `= NULL`).
  - `buscar_vista_corredor(corredor_id, filtros)`: devuelve las calificaciones del corredor **más** las de bolsa cuya llave (ejercicio, mercado, instrumento, secuencia) el corredor no tenga. Una sola consulta con `UNION ALL` y `NOT EXISTS`.
  - `buscar_todas(filtros)`: para el admin, incluye bolsa y todos los corredores.
  - `guardar(...)`: `INSERT ... ON CONFLICT (...) WHERE ... DO UPDATE SET ... RETURNING id`, usando el índice parcial que corresponda (de corredor o de bolsa). El `DO UPDATE` **no** modifica `creado_en`. Luego reemplaza el detalle de columnas. No contiene reglas de negocio.
- `errores.py`: `ErrorNegocio`, `ValidacionError`, `PermisoDenegado`, `CredencialesInvalidas`, `ArchivoInvalido`.
- `inicializar_bd.py` con dos subcomandos:
  - `python scripts/inicializar_bd.py init`: crea la base, un corredor de ejemplo y el usuario `admin` (contraseña pedida por consola con `getpass`).
  - `python scripts/inicializar_bd.py crear-usuario`: pide nombre, rol, corredor y contraseña. Sin pantalla de gestión de usuarios.

Pruebas (`tests/test_repositorios.py`): versión mínima de SQLite (con una versión simulada < 3.35 se lanza el error), llave única y upsert (sin cambiar `creado_en`), aislamiento entre corredores, triggers del log, cascada del detalle, índices parciales (una calificación de bolsa y una de corredor con la misma llave conviven; dos de bolsa con la misma llave hacen upsert) y `buscar_vista_corredor` (muestra la copia del corredor en vez de la de bolsa).

### Fase 2: Reglas de negocio

Archivos: `servicios/factores.py`, `servicios/validaciones.py`, `servicios/auth.py`, `servicios/calificaciones.py`, `servicios/carga_masiva.py`, `infraestructura/logs.py`, `infraestructura/numeros.py`.

`infraestructura/numeros.py`:
- `a_entero(valor)`: acepta `int`, `float` (`int(round(valor))`) y texto chileno (`"192.770.580"` → 192770580).
- `a_decimal(valor)`: acepta `float` (`Decimal(str(valor))`), `Decimal` y texto chileno (`"0,52277431"` → `Decimal("0.52277431")`).
- `a_fecha(valor)`: acepta `datetime`/`date` y texto `DD-MM-AAAA`; devuelve ISO.
- Valor vacío → `None`. Valor no interpretable → `ValidacionError` con el valor recibido.

`factores.py` (funciones puras):
- `calcular_factores(montos)`: para las columnas de `COLUMNAS_CALCULADAS`, `monto / suma(montos de RANGO_SUMA_FACTORES)`, redondeado a 8 decimales con `ROUND_HALF_UP`. Suma 0 → `ValidacionError`.
- `validar_factores(factores, calculados: bool)`:
  - Siempre: cada factor entre 0 y 1.
  - Solo si `calculados=False` (factores ingresados a mano o por archivo): suma de `RANGO_SUMA_FACTORES` ≤ 1,00000000, estricta.
  - Si vienen de montos, la suma ya es 1 por construcción y no se vuelve a validar (evita rechazos falsos por redondeo, por ejemplo 1,00000001).

`validaciones.py`: `validar_calificacion(datos)` normaliza el instrumento (`strip()` y mayúsculas, sección 4.3) y revisa ejercicio (`EJERCICIO_MIN`–`EJERCICIO_MAX`), mercado en `MERCADOS`, instrumento no vacío (máx. 50), fecha válida, secuencia > `SECUENCIA_MINIMA`, tipo de sociedad `A` o `C`, origen en `ORIGENES`. Mensajes que indiquen el campo.

`auth.py`:
- `pbkdf2_hmac("sha256", ...)`, sal con `secrets.token_bytes(16)`, comparación con `hmac.compare_digest`.
- `iniciar_sesion(nombre, clave) -> Usuario`; registra `LOGIN_OK` o `LOGIN_FALLIDO` sin la clave. Rechaza usuarios con `activo = 0`. Si el usuario no existe, calcula igual un hash de relleno, para que el tiempo de respuesta no revele qué usuarios existen. El mensaje de error es siempre el mismo ("Usuario o contraseña incorrectos").
- `requiere_rol(usuario, *roles)` → `PermisoDenegado`. Permisos: `admin` todo; `corredor` crear, modificar, eliminar, cargar y exportar sus datos; `consulta` solo ver y exportar.
- `corredor_efectivo(usuario, corredor_elegido)`: para `corredor` y `consulta` es el de su usuario (ignora el elegido); para `admin` el elegido es **obligatorio**, o `None` para operar sobre bolsa.
- Solo el `admin` puede crear, modificar, eliminar o cargar calificaciones de bolsa (origen `BOLSA`).

`calificaciones.py` (`ServicioCalificaciones`):
- `buscar`, `crear`, `modificar`, `eliminar`. Cada operación verifica permisos, valida y escribe en `log_auditoria` **en la misma transacción**. `modificado_en` se actualiza en cada cambio.
- **Origen en `crear`:** se deduce igual que en la carga: `BOLSA` si el ámbito es bolsa (`corredor_id` NULL) y `MANUAL` si no. La interfaz nunca lo elige.
- **Llave inmutable en `modificar`:** ejercicio, mercado, instrumento y secuencia no se pueden cambiar. Si los datos recibidos traen una llave distinta de la del registro, se lanza `ValidacionError`. Para cambiar la llave se elimina y se crea una nueva.
- **Bolsa y corredores (sección 4.5):**
  - `buscar` usa `buscar_vista_corredor` para corredor y consulta, y `buscar_todas` para el admin.
  - Si un corredor modifica una calificación de bolsa, el servicio crea **su copia completa** (cabecera y detalle de columnas, con los cambios aplicados; origen `MANUAL`, con su `corredor_id`) y deja intacto el registro de bolsa. Lo registra en la auditoría como `INSERT` con referencia al registro de bolsa en `detalle`.
  - Un corredor no puede eliminar una calificación de bolsa (`PermisoDenegado`). Si elimina su copia, vuelve a ver la de bolsa.
  - Una carga de bolsa (admin) nunca modifica copias de corredores, y viceversa.

`carga_masiva.py` (`ServicioCargaMasiva`):
- `previsualizar(filas, corredor_id) -> ResultadoCarga`: normaliza con `numeros.py`, valida con `validaciones.py`, calcula o valida factores, y marca cada fila válida como "nueva" o "actualiza" consultando `obtener_por_llave`. Filas inválidas → `FilaInvalida(numero_fila, motivo)`.
- **Montos y factores en la misma fila:** si la fila trae montos, calcula los factores 8–33 y toma los factores 34–37 que vengan en la fila (si vienen). Una columna con monto y factor a la vez es inválida.
- `confirmar(usuario, resultado, tipo_archivo)`: el **origen se deduce**, no se recibe: `corredor_id` NULL → `BOLSA`; si no, `ARCHIVO` (CSV/Excel) o `PDF` según `tipo_archivo`. Así nunca se viola el `CHECK` de la tabla. Guarda las válidas en una sola transacción y registra `CARGA_MASIVA` con cantidad de insertadas y actualizadas. La llave se evalúa dentro del ámbito de la carga: las del corredor contra sus propias calificaciones y las de bolsa contra bolsa.
- `previsualizar` y `confirmar` corren **en el hilo principal** (usan la conexión SQLite).

`infraestructura/logs.py`: `RotatingFileHandler` según `config.py`, formato `%(asctime)s %(levelname)s %(name)s %(message)s`, nivel INFO. Prohibido registrar montos, factores o contraseñas en el log técnico.

Pruebas (usar los datos de la sección 8):
- `test_numeros.py`: float de Excel, texto chileno, fechas en ambos formatos.
- `test_factores.py`: ejemplo del HDU; factores ingresados que suman 1,00000001 (falla); montos que suman 0 (falla); factor de columna 34 mayor que 1 (falla); monto de una columna 20–33 mayor que la suma de 8–19, cuyo factor calculado supera 1 (falla, según la hoja 3 del HDU).
- `test_validaciones.py`: secuencia 10.000 (falla) y 10.001 (pasa), tipo B, ejercicio 23, mercado inválido, instrumento " copec " normalizado a "COPEC".
- `test_auth.py`: hash, clave incorrecta, usuario inactivo (falla y registra `LOGIN_FALLIDO`), usuario inexistente (mismo mensaje que clave incorrecta), permisos, admin sin corredor elegido (falla), corredor intentando operar sobre bolsa (falla).
- `test_calificaciones.py`: las 8 pruebas de impacto de la sección 4.4 que no requieren archivos, auditoría de cada operación con su `detalle`, búsqueda de un ejercicio anterior, intento de cambiar la llave en `modificar` (lanza `ValidacionError`), origen deducido en `crear` (`MANUAL` para corredor, `BOLSA` para admin sobre bolsa). Para la prueba 8: el corredor modifica una calificación de bolsa → se crea su copia con el detalle completo, el registro de bolsa queda idéntico, el corredor ve su versión y otro corredor sigue viendo la de bolsa.
- `test_carga_masiva.py`: nuevas, actualizadas, inválidas con número y motivo, archivo de montos con factores 34–37 (se combinan), columna con monto y factor a la vez (inválida), origen deducido (`BOLSA` para admin sobre bolsa, `ARCHIVO` para corredor), carga de un corredor con la misma llave que bolsa (crea la del corredor y no altera bolsa), carga de bolsa con la misma llave que la copia de un corredor (actualiza bolsa y no altera la copia), instrumento `' OR 1=1 --` guardado como texto.

### Fase 3: Lectura y exportación de archivos

- `lector_csv.py`: `leer(ruta) -> list[dict]` con el módulo `csv`; detecta `;` o `,` como separador; encabezados sin importar orden ni mayúsculas. **No usa Excel**, así que se prueba en cualquier equipo.
- `lector_excel.py`: `leer(ruta)` con xlwings para `.xlsx`, `.xls` y `.xlsm`. Excel invisible, lee el rango usado de la primera hoja, **cierra Excel en un `finally`**. Mapea por nombre de encabezado. Falta de columna obligatoria → `ArchivoInvalido` indicando cuál. Los valores se devuelven crudos; la normalización la hace `numeros.py`.
- `lector_pdf.py`: `leer(ruta)` con pdfplumber; extrae el texto y busca cada monto (columnas 8–33; las 34–37 se ingresan a mano como factor en la vista dividida) por número de columna con una expresión regular, **independiente del orden**. Devuelve los montos, el año comercial si aparece y el texto extraído para la vista dividida. Campo no encontrado → `None`, marcado para corrección manual. PDF dañado o sin texto → `ArchivoInvalido`. Patrones como constantes al inicio del módulo.
  - **Mapeo de columnas:** la numeración del Certificado N°70 del SII no necesariamente coincide con la del HDU. Define `MAPEO_CERTIFICADO_A_HDU: dict[int, int]` como constante (por defecto identidad, 8→8 … 37→37) y aplícalo después de extraer. Anótalo en "Decisiones" como pendiente de verificar con el formato oficial.
- `exportacion.py`: `exportar(usuario, calificaciones, ruta)`. Para `.csv` usa el módulo `csv` (separador `;`, formato chileno), sin Excel. Para `.xlsx` y `.xls` usa xlwings; en `.xls`, `SaveAs` requiere `FileFormat=56`. Registra `EXPORTACION`.
- `tests/datos/generar_certificados.py` (usa reportlab): genera `certificado70_prueba.pdf` y `certificado70_orden_distinto.pdf` según la sección 8. Los PDFs generados se guardan en el repositorio para que las pruebas no requieran reportlab.

Pruebas: `test_lector_csv.py` (con un CSV en `tests/datos/`), `test_lector_pdf.py` (con los dos PDFs: ambos deben entregar los mismos montos), `test_exportacion.py` (CSV, sin Excel). Las que requieran Excel, con `pytest.mark.skipif`.

### Fase 4: Interfaz (PySide6)

Lineamientos de usabilidad:
- Widgets nativos, sin hojas de estilo propias. Orden de botones consistente.
- Confirmación antes de eliminar o de confirmar una carga masiva.
- Validación en línea: el campo con error se marca y el mensaje dice qué corregir.
- Barra de estado con el resultado de cada acción.
- Atajos: `Ctrl+N` nueva, `Ctrl+E` modificar, `Supr` eliminar, `Ctrl+O` cargar archivo, `Ctrl+F` buscar.
- Errores de negocio con `QMessageBox`; errores inesperados al log técnico y mensaje genérico.
- Botones habilitados según el rol (los permisos se verifican igual en los servicios).

Pantallas:
1. **`login.py`**: usuario, contraseña e Ingresar.
2. **`ventana_principal.py`**: filtros (mercado, origen, ejercicio y, solo para admin, corredor con las opciones "Todos", "Bolsa" y cada corredor), `QTableView` con Ejercicio, Instrumento, Fecha de pago, Descripción, Secuencia, Origen y Modificado; botones Ingresar, Modificar, Eliminar, Cargar archivo, Cargar PDF y Exportar.
3. **`dialogo_calificacion.py`**: datos básicos (para admin, selector obligatorio con "Bolsa" y cada corredor; mercado precargado; instrumento; secuencia > 10.000; dividendo 0 por defecto; fecha; descripción); pestaña **Montos** (columnas 8–33 con los nombres de la sección 4.1) con Calcular, Grabar y Cancelar; pestaña **Factores** editable (8–37) con la suma 8–19 visible. Al grabar por montos, los factores 8–33 se calculan y los 34–37 se toman de la pestaña Factores. Al modificar, ejercicio, mercado, instrumento, secuencia y el selector de corredor/bolsa quedan **de solo lectura**. El diálogo no muestra ni elige el origen.
4. **`dialogo_carga.py`** (para admin, selector obligatorio con "Bolsa" y cada corredor):
   - CSV o Excel: previsualización con filas marcadas "nueva", "actualiza" o "inválida" con su motivo; botón para ver el formato esperado (sección 4.3).
   - PDF: vista dividida (`QSplitter`) con el texto extraído a la izquierda y, a la derecha, los **datos básicos obligatorios y editables** (ejercicio precargado con el año comercial si se extrajo, mercado, instrumento, fecha de pago, secuencia, dividendo, tipo de sociedad) seguidos de los montos extraídos, con los no encontrados resaltados. El certificado no trae mercado, instrumento ni secuencia, así que el botón Previsualizar se habilita solo cuando los datos básicos están completos.
   - **Solo la lectura del archivo** corre en un `QThread` con barra de progreso. Si el hilo usa xlwings, en Windows (`if sys.platform == "win32":`) importa `pythoncom` y llama a `CoInitialize()` al inicio y `CoUninitialize()` al final; en macOS no se usa. `previsualizar` y `confirmar` se ejecutan en el hilo principal cuando el hilo termina.

`main.py`: configura el logging, abre la conexión, construye repositorios y servicios, muestra el login y luego la ventana principal.

### Fase 5: Documentación

`README.md` con:
1. Requisitos (Python 3.11+, Excel instalado, Windows o macOS).
2. Instalación paso a paso: entorno virtual, `pip install -r requirements.txt`, `python scripts/inicializar_bd.py init`, `crear-usuario`, `python main.py`. Para desarrollo: `pip install -r requirements-dev.txt` y `pytest`.
3. Arquitectura: diagrama de capas en texto y tabla de patrones con su justificación.
4. Modelo de datos: tablas, llave única, inmutabilidad del log y su límite (acceso directo al archivo).
5. Seguridad: RBAC, hash de contraseñas, aislamiento por corredor, consultas parametrizadas, auditoría.
6. Correspondencia entre las pruebas de impacto del HDU (sección 4.4) y funciones o pruebas.
7. Decisiones y supuestos: SQLite local; modelo bolsa compartida y copia local por corredor (sección 4.5); rango de suma configurable; columnas 34–37 sin fórmula; formato del archivo de montos (montos 8–33 y factores 34–37 opcionales); origen deducido del ámbito de la carga; instrumento normalizado a mayúsculas; códigos de mercado supuestos; instrumento no inscrito como texto libre; ejercicio del PDF precargado con el año comercial (supuesto basado en el ejemplo del HDU, ejercicio 2023 con fecha 12-12-2023; en Chile el año tributario es el comercial + 1, verificar con NUAM); mapeo de columnas del Certificado N°70 al HDU pendiente de verificar; datos básicos de la carga PDF ingresados a mano porque el certificado no los trae.
8. Trabajo futuro: base de datos central y autenticación corporativa.

## 8. Datos de prueba (solo de fuentes citables)

No inventes montos ni resultados. Cita la fuente en un comentario sobre cada fixture.

| Dato | Fuente | Uso |
|---|---|---|
| Montos col. 8 = 192.770.580; 9 = 64.161.878; 10 = 0; 11 = 111.812.860; 25 = 71.298.705; 30 = 15.837.333. Suma 8–19 = 368.745.318. Factores esperados: 8 = 0,52277431; 9 = 0,17400052; 10 = 0,00000000; 11 = 0,30322517; 25 = 0,19335488; 30 = 0,04294924. Suma 8–19 = 1,00000000 | HDU, hoja "3.2 Homologacion columnas" | `test_factores.py`, PDFs de prueba |
| Fila: 2023; ACN; Copec; 12-12-2023; secuencia 123123; dividendo 123456; tipo A; **las 30 columnas Factor 8 a 37 con 0,92345321** | HDU, hoja "3.1 Archivo de carga" | Prueba de formato. La suma 8–19 da 12 × 0,92345321 = 11,08143852 > 1: la validación debe **rechazarla** |
| 8 pruebas de impacto | HDU, sección 4.4 | `test_calificaciones.py`, `test_carga_masiva.py` |
| Estructura del Certificado N°70: encabezado del emisor (Nombre o Razón Social, RUT, Dirección, Giro o Actividad), destinatario, año comercial, columnas numeradas y pie con "CERTIFICADO N°", "Ciudad y Fecha" y firma del representante legal | SII, [Res. Ex. N°98 de 2020, Anexo 3](https://www.sii.cl/normativa_legislacion/resoluciones/2020/reso98_anexo3.pdf); vigente: [Res. Ex. N°85 de 2024, Anexo 7](https://www.sii.cl/normativa_legislacion/resoluciones/2024/reso85.pdf) | Patrones de `lector_pdf.py` y PDFs de prueba |

**Valores límite** (derivados de las reglas): factores ingresados que suman 1,00000000 (pasa) y 1,00000001 (falla); factor de columna 34 = 1,00000001 (falla); secuencia 10.000 (falla) y 10.001 (pasa); tipo A (pasa) y B (falla); ejercicio 2023 (pasa) y 23 (falla); suma de montos 0 (falla); misma llave dos veces (actualiza, no duplica); corredor modifica una calificación de bolsa (se crea su copia y bolsa queda intacta); instrumento `' OR 1=1 --` (se guarda como texto).

**PDFs de prueba:** con la estructura del Certificado N°70 y **solo** los montos de la primera fila de esta tabla, con la leyenda visible "Documento de prueba: formato SII, montos del HDU de NUAM". La segunda versión tiene las mismas columnas en otro orden.

## 9. Fuera de alcance

- Base de datos central, servidor o API.
- Sincronización en tiempo real con Excel (solo importación y exportación).
- Integración automática con el SII.
- Pantalla de gestión de usuarios (se usa el script).
- Temas visuales, internacionalización o empaquetado como ejecutable.

## 10. Criterio de término

- `pytest` pasa sin errores (salvo las pruebas marcadas por requerir Excel).
- La aplicación arranca, permite iniciar sesión, crear, modificar, eliminar, buscar, cargar CSV, Excel o PDF y exportar.
- Cada operación queda en `log_auditoria` con su `detalle`, y el log no puede alterarse desde la aplicación.
- El README permite instalar y ejecutar el sistema desde cero siguiendo los pasos.