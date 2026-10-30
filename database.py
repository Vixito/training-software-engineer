import sqlite3, secrets, hashlib, time

DB_PATH = "ai_gateway.db"

def conectar():
  conexion = sqlite3.connect(DB_PATH)
  conexion.execute("PRAGMA foreign_keys = ON")
  return conexion

def generar_api_key():
  return "vgw_" + secrets.token_urlsafe(32)

def calcular_hash(api_key):
  return hashlib.sha256(api_key.encode()).hexdigest()

def registrar_api_key(usuario, nombre):
  api_key = generar_api_key()
  key_hash = calcular_hash(api_key)
  momento = time.time()
  conexion = conectar()

  try:
    cursor = conexion.execute("INSERT INTO api_keys (usuario, key_hash, nombre, creado_en) VALUES (?, ?, ?, ?)", (usuario, key_hash, nombre, momento))
    conexion.commit()

    return {"id": cursor.lastrowid, "usuario": usuario, "api_key": api_key, "nombre": nombre, "creado_en": momento}

  except sqlite3.Error:
    conexion.rollback()
    raise

  finally:
    conexion.close()

def buscar_api_key(key_hash):
  conexion = conectar()

  try:
    cursor = conexion.execute("SELECT usuario, nombre, creado_en FROM api_keys WHERE key_hash = ? AND revocado_en IS NULL", (key_hash,))
    resultado = cursor.fetchone()

    if resultado is None:
      return None

    return {"usuario": resultado[0], "nombre": resultado[1], "creado_en": resultado[2]}

  except sqlite3.Error:
    conexion.rollback()
    raise

  finally:
    conexion.close()

def revocar_api_key(key_hash):
  conexion = conectar()

  try:
    cursor = conexion.execute("UPDATE api_keys SET revocado_en = ? WHERE key_hash = ?", (time.time(), key_hash))
    conexion.commit()

    if cursor.rowcount:
      return True
    else:
      return False
    
  except sqlite3.Error:
    conexion.rollback()
    raise

  finally:
    conexion.close()

def regeneracion_api_key(key_hash):
  conexion = conectar()

  try:
    conexion.execute("BEGIN IMMEDIATE")
    
    cursor = conexion.execute("SELECT usuario, nombre FROM api_keys WHERE key_hash = ? AND revocado_en IS NULL", (key_hash,))
    buscador = cursor.fetchone()
    
    if buscador is None:
      conexion.rollback()
      return False

    usuario, nombre = buscador
    nueva_api_key = generar_api_key()
    nuevo_hash = calcular_hash(nueva_api_key)
    momento = time.time()

    cursor = conexion.execute("UPDATE api_keys SET revocado_en = ? WHERE key_hash = ? AND revocado_en IS NULL", (momento, key_hash))

    if cursor.rowcount != 1:
      raise RuntimeError("No se pudo revocar la clave anterior")
    
    cursor = conexion.execute("INSERT INTO api_keys (usuario, key_hash, nombre, creado_en) VALUES (?, ?, ?, ?)", (usuario, nuevo_hash, nombre, momento))
  
    resultado = {"id": cursor.lastrowid, "usuario": usuario, "api_key": nueva_api_key, "nombre": nombre, "creado_en": momento}
    
    conexion.commit()
    return resultado
    
  except sqlite3.Error:
    conexion.rollback()
    raise
  
  finally:
    conexion.close()

def inicializar_db():
  conexion = conectar()

  try:
    conexion.execute("CREATE TABLE IF NOT EXISTS usuarios (usuario TEXT PRIMARY KEY)")
    conexion.execute("CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE, nombre TEXT NOT NULL, creado_en REAL NOT NULL, revocado_en REAL, FOREIGN KEY (usuario) REFERENCES usuarios(usuario))")
    conexion.execute("CREATE TABLE IF NOT EXISTS solicitudes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, solicitud TEXT NOT NULL, creado_en REAL NOT NULL, FOREIGN KEY (usuario) REFERENCES usuarios(usuario))")
    conexion.commit()
  except sqlite3.Error:
    conexion.rollback()
    raise
  finally:
    conexion.close()

def registrar_usuario(usuario):
  conexion = conectar()

  try:
    cursor = conexion.execute("INSERT OR IGNORE INTO usuarios (usuario) VALUES (?)", (usuario,))
    conexion.commit()
    return cursor.rowcount
  except sqlite3.Error:
    conexion.rollback()
    raise
  finally:
    conexion.close()

def usuario_existe(usuario):
  conexion = conectar()

  try:
    cursor = conexion.execute("SELECT usuario FROM usuarios WHERE usuario = ?", (usuario,))
    resultado = cursor.fetchone()
    return resultado is not None
  except sqlite3.Error:
    conexion.rollback()
    raise
  finally:
    conexion.close()

def registrar_solicitud_si_permitida(usuario, solicitud, momento, limite=3, ventana=60):
  conexion = conectar()

  try:
    # Evita que otra escritura se adelante a nuestra comprobación
    conexion.execute("BEGIN IMMEDIATE")
    cursor = conexion.execute("SELECT COUNT(*) FROM solicitudes WHERE usuario = ? AND creado_en > ?", (usuario, momento - ventana))
    cantidad = cursor.fetchone()[0]

    if cantidad >= limite:
      conexion.rollback()
      return None

    cursor_2 = conexion.execute("INSERT INTO solicitudes (usuario, solicitud, creado_en) VALUES (?, ?, ?)", (usuario, solicitud, momento))
    conexion.commit()
    return {
      "id": cursor_2.lastrowid,
      "usuario": usuario,
      "solicitud": solicitud,
      "creado_en": momento
    }

  except sqlite3.Error:
    conexion.rollback()
    raise

  finally:
    conexion.close()

def historial(usuario, order, limite, desplazamiento, desde=None):
  if order not in ("ASC", "DESC"):
    raise ValueError("Orden inválido")
  
  conexion = conectar()

  try:
    count = conexion.execute(f"SELECT COUNT(*) FROM solicitudes WHERE usuario = ? AND (? IS NULL OR creado_en >= ?)", (usuario, desde, desde))
    cursor = conexion.execute(f"SELECT id, usuario, solicitud, creado_en FROM solicitudes WHERE usuario = ? AND (? IS NULL OR creado_en >= ?) ORDER BY creado_en {order}, id {order} LIMIT ? OFFSET ?", (usuario, desde, desde, limite, desplazamiento))
    return {"count": count.fetchone()[0], "solicitudes": cursor.fetchall()}

  except sqlite3.Error:
    conexion.rollback()
    raise

  finally:
    conexion.close()

def registrar_usuario_con_api_key(usuario, nombre):
  conexion = conectar()

  try:
    conexion.execute("BEGIN IMMEDIATE")

    cursor = conexion.execute("INSERT OR IGNORE INTO usuarios (usuario) VALUES (?)", (usuario,))
    
    # Si el usuario existe, no continuamos.
    if cursor.rowcount != 1:
      conexion.rollback()
      return None

    # Creamos la API Key dentro de la misma transacción
    api_key = generar_api_key()
    key_hash = calcular_hash(api_key)
    momento = time.time()

    cursor = conexion.execute("INSERT INTO api_keys (usuario, key_hash, nombre, creado_en) VALUES (?, ?, ?, ?)", (usuario, key_hash, nombre, momento))
    registro = {"id": cursor.lastrowid, "usuario": usuario, "api_key": api_key, "nombre": nombre, "creado_en": momento}
    
    conexion.commit()
    return registro

  except Exception:
    conexion.rollback()
    raise

  finally:
    conexion.close()