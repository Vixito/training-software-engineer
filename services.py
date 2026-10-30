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
  registro = database.registrar_usuario_con_api_key(usuario, nombre)
  if registro is None:
    raise Error_RegistroUsuarioInvalido("El usuario ya está registrado.")
  return registro
  