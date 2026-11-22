# Mantenedor de Calificaciones Tributarias NUAM (Grupo A)

Aplicación de escritorio en Python para mantener las calificaciones tributarias de cada corredor:
ingreso por montos o por factores, carga masiva desde CSV/Excel, carga de certificados PDF
(Certificado N°70 del SII), exportación, control de acceso por rol y log de auditoría inmutable.

## 1. Requisitos

- Python 3.11 o superior (probado con Python 3.15.2 y SQLite 3.53.4).
- Windows o macOS con **Microsoft Excel instalado** (lo exige xlwings para leer y exportar
  `.xlsx`, `.xls` y `.xlsm`). Sin Excel, la aplicación funciona igual con CSV y PDF.
- SQLite 3.35 o superior (viene incluido en Python; la aplicación lo verifica al iniciar).

## 2. Instalación paso a paso

Desde la carpeta del proyecto:

```powershell
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows (PowerShell)
# source .venv/bin/activate           # macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear la base, un corredor de ejemplo y el usuario admin (pide la contraseña)
python scripts/inicializar_bd.py init

# 4. Crear usuarios de corredor o de consulta (pide nombre, rol, corredor y contraseña)
python scripts/inicializar_bd.py crear-usuario

# 5. Ejecutar la aplicación
python main.py
```

En PowerShell, si la activación del entorno está bloqueada, ejecute antes
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` (solo afecta a esa ventana).

La base queda en `nuam.db` y el log técnico en `logs/app.log`, ambos en la carpeta del proyecto.

**Desarrollo:** `pip install -r requirements-dev.txt` (agrega pytest y reportlab) y ver la sección 9.

## 3. Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│ ui/            PySide6: login, ventana principal, diálogos   │  nunca ejecuta SQL
└──────────────────────────────┬───────────────────────────────┘
                               │ llama a
┌──────────────────────────────▼───────────────────────────────┐
│ servicios/     reglas de negocio, permisos, auditoría        │──┐ usa
└──────────────────────────────┬───────────────────────────────┘  │
                               │ llama a                          ▼
┌──────────────────────────────▼──────────────┐  ┌────────────────────────────────┐
│ datos/   SQLite: esquema, conexión,         │  │ infraestructura/  lectores CSV,│
│          repositorios (sin reglas)          │  │ Excel, PDF, números, log       │
└─────────────────────────────────────────────┘  └────────────────────────────────┘
```

| Patrón | Dónde | Justificación |
|---|---|---|
| Arquitectura en capas | `ui` → `servicios` → `datos`; `infraestructura` la usan los servicios | Las reglas viven en un solo lugar y se prueban sin interfaz. |
| Repository | `datos/repositorios.py` | Todo el SQL (parametrizado) está aislado; los servicios no conocen tablas. |
| Service Layer | `servicios/*.py` | Cada operación verifica permisos, valida y audita en una transacción. |
| DTO con `dataclass` | `servicios/entidades.py` | Datos tipados entre capas, sin lógica. |
| Inyección por constructor | Cada servicio recibe conexión, repositorios y reloj | Las pruebas usan SQLite `:memory:` y un reloj falso. |
| Strategy simple | `lector_csv.leer`, `lector_excel.leer`, `lector_pdf.leer` → `list[dict]` | La carga masiva no depende del tipo de archivo. |
| Model-View de Qt | `ui/modelo_tabla.py` + `QTableView` | La tabla muestra entidades sin copiarlas a widgets. |
| Observer (señales y slots) | `ui/dialogo_carga.py`: `QThread` emite `terminado`/`fallo` | La lectura de archivos no congela la interfaz. |
| Context manager | `with conexion:` en cada servicio | La operación y su registro de auditoría se confirman o se revierten juntos. |

## 4. Modelo de datos

| Tabla | Contenido |
|---|---|
| `corredor` | Corredores (id, nombre único). |
| `usuario` | Nombre, hash y sal de la contraseña, rol (`admin`, `corredor`, `consulta`), corredor (obligatorio salvo para admin), activo. |
| `calificacion` | Cabecera: corredor (NULL = bolsa), ejercicio, mercado, instrumento, fecha de pago, secuencia, dividendo, tipo de sociedad, valor histórico, descripción, origen, creado/modificado. |
| `calificacion_detalle` | Columnas 8 a 37 de cada calificación: monto (entero, pesos) y factor (texto con 8 decimales exactos). Se borra en cascada con la calificación. |
| `log_auditoria` | Fecha, usuario, acción, tabla, registro y detalle JSON. Sin llaves foráneas: sobrevive a la eliminación de lo auditado. |

**Llave única.** Una calificación se identifica por *(ejercicio, mercado, instrumento, secuencia)*
dentro de su ámbito. Hay dos índices únicos parciales: uno para cada corredor
(`corredor_id, ejercicio, mercado, instrumento, secuencia`) y otro para bolsa
(`corredor_id IS NULL`). Así un corredor puede tener su propia versión de una calificación de
bolsa sin chocar con ella. Un `CHECK` asegura que `origen = 'BOLSA'` si y solo si `corredor_id` es NULL.

**Inmutabilidad del log.** Los triggers `log_sin_update` y `log_sin_delete` rechazan cualquier
`UPDATE` o `DELETE` sobre `log_auditoria`. **Límite:** protegen contra la aplicación y contra SQL
común, no contra alguien con acceso al archivo `nuam.db` que lo copie, lo reemplace o borre los
triggers. Para eso se requiere una base central con permisos (ver Trabajo futuro).

## 5. Seguridad

- **RBAC:** `admin` puede todo (incluida bolsa y cualquier corredor); `corredor` crea, modifica,
  elimina, carga y exporta sus datos; `consulta` solo ve y exporta. Los botones se habilitan según
  el rol, pero **los permisos se verifican siempre en los servicios** (`servicios/auth.py`).
- **Contraseñas:** PBKDF2-HMAC-SHA256 con 600.000 iteraciones y sal aleatoria de 16 bytes
  (`secrets`), comparación en tiempo constante (`hmac.compare_digest`). Nunca se guardan ni se
  registran. Si el usuario no existe se calcula igual un hash de relleno y el mensaje es siempre
  "Usuario o contraseña incorrectos", para no revelar qué usuarios existen. Los usuarios
  inactivos no pueden ingresar.
- **Aislamiento por corredor:** toda búsqueda de un corredor o de consulta se limita a su
  `corredor_id` (más las calificaciones de bolsa, de solo lectura). Leer, modificar, eliminar o
  exportar datos de otro corredor lanza `PermisoDenegado`.
- **Consultas parametrizadas:** todo el SQL usa `?`. Un instrumento como `' OR 1=1 --` se guarda
  como texto (hay prueba).
- **Auditoría:** cada `INSERT`, `UPDATE`, `DELETE`, `LOGIN_OK`, `LOGIN_FALLIDO`, `CARGA_MASIVA` y
  `EXPORTACION` queda en `log_auditoria`, en la misma transacción que la operación. El detalle
  incluye la llave y los valores anteriores y nuevos.
- **Log técnico** (`logs/app.log`, rotativo): sin montos, factores ni contraseñas.

## 6. Pruebas de impacto del HDU (hoja "4. Flujo de proceso")

| # | Prueba del HDU | Dónde se implementa | Pruebas |
|---|---|---|---|
| 1 | Ingresar o modificar por monto | `ServicioCalificaciones.crear/modificar`, `factores.calcular_factores`, pestaña Montos | `test_calificaciones.py::test_ingresar_por_monto_queda_en_el_mantenedor`, `test_modificar_por_monto` |
| 2 | Ingresar o modificar por factor | Pestaña Factores, `factores.validar_factores` | `test_ingresar_y_modificar_por_factor` |
| 3 | Instrumento no inscrito | Instrumento como texto libre (`validaciones.py`) | `test_instrumento_no_inscrito` |
| 4 | Carga masiva de factores (actualiza o agrega) | `ServicioCargaMasiva`, `lector_csv`, `lector_excel` | `test_carga_masiva.py::test_filas_nuevas_y_actualizadas` |
| 5 | Carga masiva de montos | Igual que 4, con columnas `Monto N` | `test_carga_de_montos_con_factores_34_a_37` |
| 6 | Información local por corredor | Ámbito por `corredor_id` en repositorios y servicios | `test_aislamiento_entre_corredores` (repositorios y servicios) |
| 7 | Suma de factores 8 a 19 ≤ 1 | `factores.validar_factores` | `test_factores.py`, `test_suma_de_factores_mayor_que_uno_se_rechaza` |
| 8 | No se altera la información de bolsa | Bolsa compartida + copia local (`modificar`), índices parciales | `test_corredor_modifica_bolsa_crea_su_copia`, `test_carga_de_corredor_con_llave_de_bolsa_no_altera_bolsa`, `test_carga_de_bolsa_no_altera_copia_del_corredor` |

Otros escenarios: modificación (`dialogo_calificacion.py`, llave de solo lectura), eliminación con
confirmación (`VentanaPrincipal.eliminar`), columna de origen (tabla principal y filtro), log
(`log_auditoria`), certificados PDF en distinto orden (`lector_pdf.py`, `test_lector_pdf.py`),
ejercicios anteriores (filtro Ejercicio, `test_busqueda_de_ejercicio_anterior`).

### Uso rápido

- **Atajos:** `Ctrl+N` ingresar, `Ctrl+E` modificar (o doble clic), `Supr` eliminar,
  `Ctrl+O` cargar archivo, `Ctrl+F` buscar.
- **Carga CSV/Excel:** se previsualiza cada fila como *nueva*, *actualiza* o *inválida* (con el
  motivo) antes de confirmar. El botón "Ver formato esperado" muestra el formato.
- **Carga PDF:** a la izquierda el texto extraído, a la derecha los datos básicos (que el
  certificado no trae) y los montos encontrados; los no encontrados aparecen resaltados.

## 7. Decisiones y supuestos

- **SQLite local** (el HDU indica que las calificaciones son locales por corredor). Una base por
  instalación; cada usuario ve solo su corredor.
- **Bolsa compartida y copia local por corredor** (HDU, "Objetivo y alcance"): las calificaciones
  de bolsa tienen `corredor_id` NULL y solo el admin las crea, modifica o elimina. Si un corredor
  modifica una de bolsa, se crea su copia completa (cabecera y detalle) con origen `MANUAL` y la
  de bolsa queda intacta; el corredor ve su versión, los demás siguen viendo la de bolsa. Un
  corredor no puede eliminar una calificación de bolsa; si elimina su copia, vuelve a ver la de bolsa.
- **Rango de suma configurable:** `RANGO_SUMA_FACTORES = range(8, 20)` (8 a 19). Un escenario del
  HDU dice 8–16 y las hojas de flujo y de tipos de datos dicen 8–19.
- **Columnas 34 a 37 sin fórmula** en el HDU: se ingresan como factor. Las 8 a 33 se calculan como
  `monto / suma(montos 8–19)`. Todo factor (8 a 37) debe estar entre 0 y 1, también los calculados
  (un monto de las columnas 20–33 mayor que la suma 8–19 se rechaza).
- **Redondeo:** factores a 8 decimales con `ROUND_HALF_UP`. Si vienen de montos, la suma ya es 1
  por construcción y no se vuelve a validar (evita rechazos falsos por redondeo, p. ej. 1,00000001);
  si se ingresan a mano o por archivo, la suma ≤ 1,00000000 es estricta.
- **Formato del archivo de montos** (el HDU no lo define): igual al de factores, con `Monto 8` a
  `Monto 33` y, opcionalmente, `Factor 34` a `Factor 37`. Una columna con monto y factor a la vez
  es inválida. Una llave repetida dentro del mismo archivo también se informa como inválida.
- **Origen deducido, nunca elegido:** al crear, `BOLSA` (admin sobre bolsa) o `MANUAL`; en cargas,
  `BOLSA`, `ARCHIVO` (CSV/Excel) o `PDF`. **Al modificar**, la calificación pasa a origen `MANUAL`
  (o se mantiene `BOLSA` si es de bolsa), porque su contenido ahora lo definió una persona.
- **Llave inmutable:** al modificar no se pueden cambiar ejercicio, mercado, instrumento ni
  secuencia (ni el ámbito); para hacerlo, se elimina y se crea.
- **Instrumento normalizado:** sin espacios extremos y en mayúsculas ("Copec" = "COPEC").
- **Instrumento no inscrito:** no hay catálogo de instrumentos; cualquier instrumento es válido.
- **Códigos de mercado:** "ACN" viene del HDU; "CFI" y "FMU" son supuestos (`config.MERCADOS`).
- **Tipo de sociedad** opcional (A o C si se informa): el HDU lo incluye en el archivo de carga
  pero no en los datos básicos del ingreso manual.
- **Certificado PDF:** los patrones (`infraestructura/lector_pdf.py`) siguen la estructura del
  Certificado N°70 descrita en el plan (Res. Ex. SII N°98 de 2020, Anexo 3; vigente Res. Ex. N°85
  de 2024, Anexo 7). **El anexo del SII no se descargó**: se usó la estructura descrita en el plan
  (encabezado del emisor, destinatario, año comercial, columnas numeradas, pie con N° de
  certificado, ciudad y fecha y firma). Los patrones **deben ajustarse con un certificado real**.
  - Mapeo de columnas del certificado al HDU: identidad (`MAPEO_CERTIFICADO_A_HDU`), pendiente de
    verificar con el formato oficial.
  - Del PDF solo se leen montos 8 a 33; los datos básicos (mercado, instrumento, secuencia, etc.)
    y los factores 34–37 se ingresan a mano porque el certificado no los trae.
  - El ejercicio se precarga con el **año comercial** del certificado. Supuesto basado en el
    ejemplo del HDU (ejercicio 2023 con fecha de pago 12-12-2023); en Chile el año tributario es
    el comercial + 1: **verificar con NUAM**.
  - Un monto no encontrado queda vacío y resaltado; nunca se inventa un valor.
- **Exportación:** CSV con el módulo `csv` (separador `;`, formato chileno); Excel con xlwings
  (`.xls` con `FileFormat=56`). En Excel el factor se escribe como número con formato de 8
  decimales (conversión a `float` solo al escribir; los cálculos usan `Decimal`). El archivo
  exportado se puede volver a cargar.
- **Carga masiva:** un solo registro `CARGA_MASIVA` por carga, con origen, ámbito y cantidad de
  insertadas, actualizadas e inválidas.
- **Hash de contraseñas:** el campo `hash` guarda también las iteraciones (`600000$<hex>`), para
  poder aumentarlas en el futuro sin invalidar las existentes.
- **Rutas:** `RUTA_BD` y `RUTA_LOGS` se resuelven respecto de la carpeta del proyecto, para que
  `main.py` y el script usen la misma base desde cualquier carpeta.
- **Módulos auxiliares agregados** (no estaban en la estructura del plan): `ui/comun.py`
  (formulario y tabla de columnas compartidos por los diálogos), `infraestructura/formato_carga.py`
  (mapeo de encabezados compartido por los lectores CSV y Excel). Los lectores también escriben (`escribir`) para que xlwings y
  `csv` queden en infraestructura. `FilaValida` se agregó a las entidades para la previsualización.
- **Tabla del admin:** agrega la columna "Corredor" (o "Bolsa") para distinguir ámbitos.
- **Compatibilidad Python 3.15 + PySide6 6.12:** con los *lazy imports* de Python 3.15, importar
  xlwings después de PySide6 falla (`'lazy_import' object is not callable`). `ui/__init__.py`
  importa xlwings antes que PySide6.
- **Pruebas de la interfaz:** además de las pruebas de lógica, `tests/test_ui_humo.py` recorre los
  flujos principales sin pantalla (`QT_QPA_PLATFORM=offscreen`). No reemplaza la prueba manual.

## 8. Trabajo futuro (fuera de alcance)

- Base de datos central compartida (servidor), con permisos por usuario y log protegido a nivel
  de servidor.
- Autenticación corporativa (Active Directory / SSO).
- Ajuste del extractor PDF con certificados reales de distintos emisores.
- Pantalla de gestión de usuarios (hoy se usa `scripts/inicializar_bd.py`).

## 9. Cómo ejecutar las pruebas

```powershell
pip install -r requirements-dev.txt
pytest
```

- Las pruebas de lógica usan SQLite en memoria; no tocan `nuam.db`.
- Las que requieren Microsoft Excel se marcan con `pytest.mark.skipif` y se omiten si Excel no
  está instalado (`pytest -rs` muestra cuáles se omitieron).
- Datos de prueba: solo de fuentes citables (HDU de NUAM, hojas 3.1, 3.2 y 4; estructura del
  Certificado N°70 del SII), citados en cada fixture.
- Para regenerar los certificados PDF de prueba (requiere reportlab):
  `python tests/datos/generar_certificados.py`. Los PDFs están en el repositorio, así que las
  pruebas no necesitan reportlab.
