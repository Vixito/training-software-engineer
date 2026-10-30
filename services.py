import time
import database

class Error_UsuarioNoEncontrado(Exception):
  pass
class Error_RegistroUsuarioInvalido(Exception):
  pass

def obtener_tiempo():
  return time.time()

def verificar_limite(usuario, solicitud):
  momento = obtener_tiempo()
  verificar_usuario_registrado(usuario)
  return database.registrar_solicitud_si_permitida(usuario=usuario, solicitud=solicitud, momento=momento)

def obtener_historial(usuario, order, limite, desplazamiento, desde=None):
  verificar_usuario_registrado(usuario)
  return database.historial(usuario, order, limite, desplazamiento, desde)

def verificar_usuario_registrado(usuario):
  if not database.usuario_existe(usuario):
    raise Error_UsuarioNoEncontrado("Usuario no registrado.")

def service_registrar_usuario(usuario, nombre):
  new_user = database.registrar_usuario(usuario)
  if new_user == 1:
    registro = database.registrar_api_key(usuario, nombre)
    return {"id": registro["id"], "usuario": registro["usuario"], "api_key": registro["api_key"], "nombre": registro["nombre"], "creado_en": registro["creado_en"]}
  else:
    raise Error_RegistroUsuarioInvalido("No se pudo registrar el usuario correctamente.")
  