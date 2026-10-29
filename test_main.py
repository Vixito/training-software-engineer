from fastapi.testclient import TestClient
from main import app
import services, pytest, database, sqlite3, time

@pytest.fixture(autouse=True)
def preparar_db(tmp_path, monkeypatch):
  # Aquí hacemos operaciones antes de cada prueba
  ruta_db = str(tmp_path / "test.db")
  monkeypatch.setattr(database, "DB_PATH", ruta_db)
  database.inicializar_db()
  database.registrar_usuario("vixis")

  resultado = database.registrar_api_key("vixis", "Clave de pruebas")
  monkeypatch.setattr("test_main.HEADERS", {"X-API-Key": resultado["api_key"]})

client = TestClient(app)

def test_estado_servicio():
  respuesta = client.get("/")

  assert respuesta.status_code == 200
  assert respuesta.json() == {
    "servicio": "AI Gateway",
    "estado": "activo"
  }

def test_solicitud_usuario_registrado():
  respuesta = client.post(
    "/solicitudes", 
    json={"usuario": "vixis", "solicitud": "Hola, AI Gateway"},
    headers=HEADERS
  )

  assert respuesta.status_code == 200
  datos = respuesta.json()
  assert isinstance(datos["id"], int)
  assert datos["usuario"] == "vixis"
  assert datos["solicitud"] == "Hola, AI Gateway"
  assert isinstance(datos["creado_en"], (int, float))
  assert datos["estado"] == "recibida"

def test_solicitud_vacia():
  respuesta = client.post(
    "/solicitudes",
    json={"usuario": "vixis", "solicitud": ""},
    headers=HEADERS
  )

  assert respuesta.status_code == 422
  assert respuesta.json()["detail"][0]["type"] == "string_too_short"

def test_solicitud_solo_espacios():
  respuesta = client.post(
    "/solicitudes",
    json={"usuario": "vixis", "solicitud": "   "},
    headers=HEADERS
  )

  assert respuesta.status_code == 422
  assert respuesta.json()["detail"][0]["type"] == "value_error"

def test_limite_solicitudes():
  respuestas = []
  for r in range(4):
    respuestas.append(client.post("/solicitudes", json={"usuario": "vixis", "solicitud": "zzz"}, headers=HEADERS))
    
  assert all(respuesta.status_code == 200 for respuesta in respuestas[:3])
  assert respuestas[-1].status_code == 429
  assert respuestas[-1].json() == {
    "detail": "Demasiadas solicitudes en un lapso de 60 segundos."
  }

def test_limite_se_reinicia_con_el_tiempo(monkeypatch):
  tiempos = iter([100, 100, 100, 100, 161])
  monkeypatch.setattr(services, "obtener_tiempo", lambda: next(tiempos))
  
  respuestas = []
  for r in range(5):
    respuestas.append(client.post("/solicitudes", json={"usuario": "vixis", "solicitud": "tezzzt"}, headers=HEADERS))

  assert all(respuesta.status_code == 200 for respuesta in respuestas[:3])
  assert respuestas[3].status_code == 429
  assert respuestas[4].status_code == 200

def test_registrar_y_consultar_usuario():
  assert database.usuario_existe("vixis") is True
  assert database.usuario_existe("desconocido") is False

def test_vista_de_base_de_datos():
  resultado = database.registrar_solicitud_si_permitida("vixis", "Aprendiendo SQLite", 1000)
  assert isinstance(resultado["id"], int)
  assert resultado["usuario"] == "vixis"
  assert resultado["solicitud"] == "Aprendiendo SQLite"
  assert resultado["creado_en"] == 1000
  assert database.historial("vixis", "DESC", 1, 0)["count"] == 1

def test_solicitudes_usuarios_distintos():
  database.registrar_usuario("ana")
  database.registrar_solicitud_si_permitida("vixis", "zzz", 1000)
  database.registrar_solicitud_si_permitida("ana", "test", 1000)

  solicitud_vixis = database.historial("vixis", "DESC", 1, 0)["solicitudes"][0][2]
  solicitud_ana = database.historial("ana", "DESC", 10, 0)["solicitudes"][0][2]

  assert solicitud_vixis == "zzz"
  assert solicitud_ana == "test"

def test_error_base_datos(monkeypatch):
  def historial_falso(usuario, order, limite, desplazamiento, desde):
    raise sqlite3.OperationalError("Error simulado de SQLite")

  monkeypatch.setattr(database, "historial", historial_falso)
  respuesta = client.get("/usuarios/vixis/solicitudes", headers=HEADERS)

  assert respuesta.status_code == 500
  assert respuesta.json() == {
    "detail": "Problemas con el servidor, inténtelo más tarde."
  }

def test_solicitud_sin_campo_solicitud():
  respuesta = client.post("/solicitudes", json={}, headers=HEADERS)

  assert respuesta.status_code == 422

def test_espacios_en_solicitud():
  respuesta = client.post("/solicitudes", json={"usuario": "  vixis  ", "solicitud": "  Hola, AI Gateway  "}, headers=HEADERS)

  assert respuesta.status_code == 200
  assert respuesta.json()["usuario"] == "vixis"
  assert respuesta.json()["solicitud"] == "Hola, AI Gateway"

def test_pagina_sin_repeticiones():
  database.registrar_solicitud_si_permitida("vixis", "xd", 1000)
  database.registrar_solicitud_si_permitida("vixis", "xdd", 1000)
  database.registrar_solicitud_si_permitida("vixis", "xddd", 1000)
  database.registrar_solicitud_si_permitida("vixis", "xdddd", 1060)
  
  pagina_1 = client.get("/usuarios/vixis/solicitudes?limite=2&desplazamiento=0", headers=HEADERS)
  pagina_2 = client.get("/usuarios/vixis/solicitudes?limite=2&desplazamiento=2", headers=HEADERS)

  respuesta_1 = pagina_1.json()
  respuesta_2 = pagina_2.json()

  ids_1 = [registro["id"] for registro in respuesta_1["solicitudes"]]
  ids_2 = [registro["id"] for registro in respuesta_2["solicitudes"]]

  assert client.get("/usuarios/vixis/solicitudes", headers=HEADERS).json()["count"] == 4
  assert len(respuesta_1["solicitudes"]) == 2
  assert len(respuesta_2["solicitudes"]) == 2
  assert not set(ids_1) & set(ids_2)

def test_parametros_invalidos():
  assert client.get("/usuarios/vixis/solicitudes?limite=0", headers=HEADERS).status_code == 422
  assert client.get("/usuarios/vixis/solicitudes?limite=101", headers=HEADERS).status_code == 422
  assert client.get("/usuarios/vixis/solicitudes?desplazamiento=-1", headers=HEADERS).status_code == 422

def test_orden_esperado():
  fechas = [1000, 1020, 1040]
  for fecha in fechas:
    database.registrar_solicitud_si_permitida("vixis", "zzz", fecha)
    
  fechas_reales_asc = extraer_fechas(client.get("/usuarios/vixis/solicitudes?order=ASC", headers=HEADERS).json()["solicitudes"])
  fechas_reales_desc = extraer_fechas(client.get("/usuarios/vixis/solicitudes?order=DESC", headers=HEADERS).json()["solicitudes"])

  assert fechas_reales_asc == sorted(fechas)
  assert fechas_reales_desc == sorted(fechas, reverse=True)

def test_consultar_historial_sin_desde():
  fechas = [1000, 1020, 1040]
  for fecha in fechas:
    database.registrar_solicitud_si_permitida("vixis", "probanding", fecha)

  fechas_reales = extraer_fechas(client.get("/usuarios/vixis/solicitudes/?order=ASC", headers=HEADERS).json()["solicitudes"])
  fechas_reales_2 = extraer_fechas(client.get("/usuarios/vixis/solicitudes/?desde=1020&order=ASC", headers=HEADERS).json()["solicitudes"])
  
  assert fechas == fechas_reales
  assert fechas[1:] == fechas_reales_2

def test_orden_estable_con_fechas_iguales():
  database.registrar_solicitud_si_permitida("vixis", "misma fecha", 1000)
  database.registrar_solicitud_si_permitida("vixis", "misma fecha", 1000)
  database.registrar_solicitud_si_permitida("vixis", "misma fecha", 1000)

  ids_asc = [registro[0] for registro in database.historial("vixis", "ASC", 3, 0)["solicitudes"]]
  ids_desc = [registro[0] for registro in database.historial("vixis", "DESC", 3, 0)["solicitudes"]]

  assert ids_asc == sorted(ids_asc)
  assert ids_desc == sorted(ids_desc, reverse=True)

def test_solicitud_sin_api_key():
  respuesta = client.post("/solicitudes", json={"usuario": "vixis", "solicitud": "probanding"})

  assert respuesta.status_code == 401
  assert respuesta.json() == {"detail": "Credenciales inválidas."}

def test_registrar_api_key():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")

  assert resultado["id"] is not None
  assert resultado["usuario"] == "vixis"
  assert resultado["nombre"] == "Mi aplicación"
  assert resultado["api_key"].startswith("vgw_")
  assert resultado["creado_en"] > 0

def test_hash_api_key_guardado():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")
  conexion = database.conectar()

  try:
    cursor = conexion.execute("SELECT key_hash FROM api_keys WHERE id = ?", (resultado["id"],))
    hash_guardado = cursor.fetchone()[0]

    assert hash_guardado == database.calcular_hash(resultado["api_key"])
    assert hash_guardado != resultado["api_key"]

  finally:
    conexion.close()

def test_registrar_api_key_usuario_inexistente():
  with pytest.raises(sqlite3.IntegrityError):
    database.registrar_api_key("usuario_inexistente", "Mi aplicación")

def test_buscar_api_key_valida():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")
  key_hash = database.calcular_hash(resultado["api_key"])
  encontrada = database.buscar_api_key(key_hash)

  assert encontrada is not None
  assert encontrada["usuario"] == "vixis"
  assert encontrada["nombre"] == "Mi aplicación"

def test_buscar_api_key_inexistente():
  key_hash = database.calcular_hash("vgw_clave_inexistente")
  encontrada = database.buscar_api_key(key_hash)

  assert encontrada is None

def test_buscar_api_key_revocada():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")
  key_hash = database.calcular_hash(resultado["api_key"])
  conexion = database.conectar()

  try:
    conexion.execute("UPDATE api_keys SET revocado_en = ? WHERE id = ?", (time.time(), resultado["id"]))
    conexion.commit()
  finally:
    conexion.close()

  encontrada = database.buscar_api_key(key_hash)
  
  assert encontrada is None

def test_usuario_determinado_por_api_key():
  respuesta = client.post("/solicitudes", json={"usuario": "ana", "solicitud": "Probando autenticación"}, headers=HEADERS)

  assert respuesta.status_code == 200
  assert respuesta.json()["usuario"] == "vixis"

def test_usuario_no_puede_consultar_historial_ajeno():
  respuesta = client.get("/usuarios/ana/solicitudes", headers=HEADERS)

  assert respuesta.status_code == 403

def test_api_key_revocada_no_puede_consultar_historial():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")
  key_hash = database.calcular_hash(resultado["api_key"])
  database.revocar_api_key(key_hash)
  respuesta = client.get("/usuarios/vixis/solicitudes", headers={"X-API-Key": resultado["api_key"]})

  assert respuesta.status_code == 401

def test_revocar_hash_inexistente():
  key_hash = "zzz"
  assert database.revocar_api_key(key_hash) is False

def test_regeneracion_api_exitosa():
  resultado = database.registrar_api_key("vixis", "Mi aplicación")
  key_hash = database.calcular_hash(resultado["api_key"])
  regeneracion = database.regeneracion_api_key(key_hash)

  assert regeneracion["api_key"] != resultado["api_key"]
  assert database.buscar_api_key(key_hash) is None
  assert database.calcular_hash(regeneracion["api_key"]) != key_hash

def test_regeneracion_api_inexistente():
  assert database.regeneracion_api_key("zzz") is False

def test_regeneracion_api_fallida(monkeypatch):
  api_antigua = database.registrar_api_key("vixis", "Mi aplicación")
  key_hash = database.calcular_hash(api_antigua["api_key"])
  
  def devolver_clave_repetida():
    return api_antigua["api_key"]
  
  monkeypatch.setattr(database, "generar_api_key", devolver_clave_repetida)
  with pytest.raises(sqlite3.IntegrityError):
    database.regeneracion_api_key(key_hash)

  clave_activa = database.buscar_api_key(key_hash)

  assert clave_activa is not None
  assert clave_activa["nombre"] == "Mi aplicación"

# ==============================================  
API_KEY = "clave_de_prueba"
HEADERS = {"X-API-Key": API_KEY}
def extraer_fechas(respuesta):
  fechas = []
  for registro in respuesta:
    fechas.append(registro["creado_en"])
  return fechas