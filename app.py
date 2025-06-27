from flask import Flask, render_template, redirect, url_for, request, make_response, jsonify
from flask_socketio import SocketIO
import random
from gevent import monkey
import uuid

monkey.patch_all()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

fecha_actual = "2025-06-26 15:00"
pases_asignados = {}
id_por_cookie = {}
ultimo_id_asignado = 1

def generar_pase(id_numerico):
    r = random.random()
    if r < 0.05:
        return {'id': str(id_numerico), 'rol': 'Visita', 'fecha': fecha_actual,
                'documentacion': True, 'curso': True, 'certificado': True,
                'autorizacion': True, 'cita': True, 'es_impostor': False, 'nombre': ''}
    elif r < 0.10:
        return {'id': str(id_numerico), 'rol': 'Desconocido', 'fecha': "Sin cita",
                'documentacion': False, 'curso': False, 'certificado': False,
                'autorizacion': False, 'cita': False, 'es_impostor': True, 'nombre': ''}
    else:
        roles = ['Visita','Proveedor','Gerente','Inspector','Auditor']
        return {'id': str(id_numerico),'rol': random.choice(roles),
                'fecha': random.choice([fecha_actual, "2025-06-27 10:00"]),
                'documentacion': random.choice([True,False]),
                'curso': random.choice([True,False]),
                'certificado': random.choice([True,False]),
                'autorizacion': random.choice([True,False]),
                'cita': random.choice([True,False]),
                'es_impostor': False,
                'nombre': ''}

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
        return "Nombre guardado", 200
    return "Pase no encontrado", 404

@app.route("/revelar")
def revelar():
    return render_template("revelar_ws.html")

@app.route("/disparar_revelacion")
def disparar_revelacion():
    for pase in pases_asignados.values():
        puede_ingresar = (not pase['es_impostor'] and pase['fecha'] == fecha_actual and
                          all([pase['documentacion'],pase['curso'],pase['certificado'],
                               pase['autorizacion'],pase['cita']]))
        socketio.emit('resultado', {
            'id': pase['id'],
            'puede_ingresar': puede_ingresar,
            'es_impostor': pase['es_impostor'],
            'nombre': pase['nombre']
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
    return "Juego reiniciado."

@socketio.on("connect")
def handle_connect():
    print("Cliente conectado.")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=3000)
