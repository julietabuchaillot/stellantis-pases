from gevent import monkey
monkey.patch_all()

import requests

from flask import Flask, render_template, redirect, url_for, request, make_response, jsonify
from flask_socketio import SocketIO
import random
import uuid
from datetime import datetime, timedelta
import os
import json
import threading
import time



app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

fecha_actual = datetime.now().strftime("%Y-%m-%d")
hora_actual = datetime.now().replace(second=0, microsecond=0)
pases_asignados = {}
id_por_cookie = {}
ultimo_id_asignado = 1
ARCHIVO_JSON = "pases.json"

def guardar_en_json():
    with open(ARCHIVO_JSON, "w") as f:
        json.dump({
            "pases": pases_asignados,
            "ultimo_id": ultimo_id_asignado,
            "cookies": id_por_cookie
        }, f, indent=2)

def cargar_desde_json():
    global pases_asignados, ultimo_id_asignado, id_por_cookie
    if os.path.exists(ARCHIVO_JSON):
        with open(ARCHIVO_JSON) as f:
            datos = json.load(f)
            pases_asignados = {k: v for k, v in datos.get("pases", {}).items()}
            ultimo_id_asignado = datos.get("ultimo_id", 1)
            id_por_cookie = datos.get("cookies", {})

empresas = [
    "Motores Córdoba SA", "Autopartes Cuenca", "Chasis del Sur",
    "Electroservicios Córdoba", "Transporte Argentino",
    "Stellantis Argentina", "Stellantis Chile", "Stellantis Uruguay"
]
sub_roles_gerente = ["Gerente de Planta", "Gerente de Ventas", "Gerente de Compras", "Gerente de Seguridad"]
plantas_gerente = ["Stellantis Chile", "Stellantis Uruguay", "Stellantis Brasil"]

def generar_pase(id_numerico):
    global tipos_cola

    if tipos_cola:
        tipo = tipos_cola.popleft()
    else:
        # Aquí definimos probabilidades para que el pase sea impostor, valido o random
        p_impostor = 0.2  # 10% impostor
        p_valido = 0.2  # 30% válido
        p_random = 0.6  # 60% random

        r = random.random()
        if r < p_impostor:
            tipo = 'impostor'
        elif r < p_impostor + p_valido:
            tipo = 'valido'
        else:
            tipo = 'random'

    if tipo == 'valido':
        return {
            'id': str(id_numerico), 'rol': 'Visita', 'fecha': fecha_actual,
            'hora': hora_actual.strftime("%H:%M"), 'empresa': '',
            'documentacion': True, 'curso': True, 'certificado': True,
            'cita': True, 'es_impostor': False, 'nombre': ''
        }

    if tipo == 'impostor':
        return {
            'id': str(id_numerico), 'rol': 'Desconocido', 'fecha': "Sin cita",
            'hora': "--:--", 'empresa': '',
            'documentacion': False, 'curso': False, 'certificado': False,
            'cita': False, 'es_impostor': True, 'nombre': ''
        }

    # Caso 'random'
    roles = ['Visita', 'Proveedor', 'Gerente', 'Inspector', 'Auditor']
    rol = random.choice(roles)
    hora_cita = (hora_actual + timedelta(minutes=random.randint(-60, 120))).strftime("%H:%M")

    if rol == "Gerente":
        rol = random.choice(sub_roles_gerente)
        empresa = random.choice(plantas_gerente)
    elif rol == "Proveedor":
        empresa = random.choice(["Motores Córdoba SA", "Autopartes Cuenca", "Chasis del Sur"])
    elif rol in ["Inspector", "Auditor"]:
        empresa = random.choice(["Ministerio de Trabajo", "Sindicato Nacional", "ISO Control"])
    elif rol == "Visita":
        empresa = ""
    else:
        empresa = random.choice(empresas)

    return {
        'id': str(id_numerico), 'rol': rol, 'fecha': fecha_actual, 'hora': hora_cita, 'empresa': empresa,
        'documentacion': random.choice([True, False]),
        'curso': random.choice([True, False]),
        'certificado': random.choice([True, False]),
        'cita': True if fecha_actual and hora_cita else False,
        'es_impostor': False,
        'nombre': ''
    }


@app.route("/scan")
def scan():
    global ultimo_id_asignado
    user_id = request.cookies.get("user_id")
    if user_id and user_id in id_por_cookie:
        pase_id = id_por_cookie[user_id]
        return redirect(f"/scan/{pase_id}")
    if ultimo_id_asignado > 200:
        return "Ya no hay más pases disponibles."
    pase = generar_pase(ultimo_id_asignado)
    pases_asignados[pase['id']] = pase
    user_id = str(uuid.uuid4())
    id_por_cookie[user_id] = pase['id']
    ultimo_id_asignado += 1
    guardar_en_json()
    resp = make_response(redirect(f"/scan/{pase['id']}"))
    resp.set_cookie("user_id", user_id)
    return resp

@app.route("/scan/<id>")
def ver_pase(id):
    pase = pases_asignados.get(id)
    if not pase:
        return "Pase no encontrado."
    return render_template("pase_ws.html", pase=pase)

@app.route("/guardar_nombre", methods=["POST"])
def guardar_nombre():
    id = request.form.get("id")
    nombre = request.form.get("nombre")
    if id in pases_asignados:
        pases_asignados[id]['nombre'] = nombre
        guardar_en_json()
        return "Nombre guardado", 200
    return "Pase no encontrado", 404

@app.route("/guardar_foto", methods=["POST"])
def guardar_foto():
    id = request.form.get("id")
    foto = request.files.get("foto")
    if id and foto:
        ruta = os.path.join("static", "fotos")
        os.makedirs(ruta, exist_ok=True)
        foto.save(os.path.join(ruta, f"{id}.jpg"))
        return "Foto guardada", 200
    return "Error al guardar la foto", 400

@app.route("/revelar")
def revelar():
    return render_template("revelar_ws.html")

@app.route("/disparar_revelacion")
def disparar_revelacion():
    ahora = datetime.now()
    for pase in pases_asignados.values():
        puede_ingresar = (not pase['es_impostor'] and pase['fecha'] == fecha_actual and
                          all([pase['documentacion'],pase['curso'],pase['certificado'],pase['cita']]))
        estado_ingreso = "desconocido"
        try:
            cita_dt = datetime.strptime(pase['fecha'] + " " + pase['hora'], "%Y-%m-%d %H:%M")
            if cita_dt > ahora:
                estado_ingreso = "adelantado"
            elif cita_dt < ahora:
                estado_ingreso = "retrasado"
            else:
                estado_ingreso = "puntual"
        except Exception:
            estado_ingreso = "sin cita"

        socketio.emit('resultado', {
            'id': pase['id'],
            'puede_ingresar': puede_ingresar,
            'es_impostor': pase['es_impostor'],
            'nombre': pase['nombre'],
            'empresa': pase['empresa'],
            'rol': pase['rol'],
            'hora': pase['hora'],
            'fecha': pase['fecha'],
            'estado_ingreso': estado_ingreso
        })
    return "Revelación enviada", 200

@app.route("/obtener_pases")
def obtener_pases():
    return jsonify(list(pases_asignados.values()))

@app.route("/reiniciar")
def reiniciar():
    global pases_asignados, ultimo_id_asignado, id_por_cookie
    pases_asignados = {}
    id_por_cookie = {}
    ultimo_id_asignado = 1
    if os.path.exists(ARCHIVO_JSON):
        os.remove(ARCHIVO_JSON)

    # Eliminar fotos en static/fotos
    carpeta_fotos = os.path.join("static", "fotos")
    if os.path.exists(carpeta_fotos):
        for nombre_archivo in os.listdir(carpeta_fotos):
            ruta_archivo = os.path.join(carpeta_fotos, nombre_archivo)
            if os.path.isfile(ruta_archivo):
                os.remove(ruta_archivo)

    from collections import deque
    global tipos_cola
    TIPOS_CONTROLADOS = ['valido'] * 16 + ['impostor'] * 2 + ['random'] * 22
    random.shuffle(TIPOS_CONTROLADOS)
    tipos_cola = deque(TIPOS_CONTROLADOS)

    return "Juego reiniciado."


@app.route("/pase/<id>")
def ver_pase_publico(id):
    pase = pases_asignados.get(id)
    if not pase:
        return "Pase no encontrado", 404
    return render_template("ver_pase.html", pase=pase)

@socketio.on("connect")
def handle_connect():
    print("Cliente conectado.")


def mantener_viva():
    while True:
        try:
            print("↪️ Haciendo ping para mantener viva la app")
            requests.get("https://stellantis-pases.onrender.com/")
        except Exception as e:
            print("❌ Error en ping:", e)
        time.sleep(600)  # cada 10 minutos (600 segundos)

threading.Thread(target=mantener_viva, daemon=True).start()


if __name__ == "__main__":
    cargar_desde_json()
    socketio.run(app, host="0.0.0.0", port=3000)
