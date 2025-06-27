from flask import Flask, render_template
from flask_socketio import SocketIO
import random

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

fecha_actual = "2025-06-26 15:00"
pases_asignados = {}
ultimo_id_asignado = 1

def generar_pase(id_numerico):
    r = random.random()
    if r < 0.05:
        return {
            'id': str(id_numerico),
            'rol': 'Visita',
            'fecha': fecha_actual,
            'documentacion': True,
            'curso': True,
            'certificado': True,
            'autorizacion': True,
            'cita': True,
            'es_impostor': False
        }
    elif r < 0.10:
        return {
            'id': str(id_numerico),
            'rol': 'Desconocido',
            'fecha': "Sin cita",
            'documentacion': False,
            'curso': False,
            'certificado': False,
            'autorizacion': False,
            'cita': False,
            'es_impostor': True
        }
    else:
        roles = ['Visita', 'Proveedor', 'Gerente', 'Inspector', 'Auditor']
        return {
            'id': str(id_numerico),
            'rol': random.choice(roles),
            'fecha': random.choice([fecha_actual, "2025-06-27 10:00"]),
            'documentacion': random.choice([True, False]),
            'curso': random.choice([True, False]),
            'certificado': random.choice([True, False]),
            'autorizacion': random.choice([True, False]),
            'cita': random.choice([True, False]),
            'es_impostor': False
        }

@app.route("/scan")
def scan():
    global ultimo_id_asignado
    if ultimo_id_asignado > 200:
        return "Ya no hay más pases disponibles."
    pase = generar_pase(ultimo_id_asignado)
    pases_asignados[pase['id']] = pase
    ultimo_id_asignado += 1
    return render_template("pase_ws.html", pase=pase)

@app.route("/revelar")
def revelar():
    return render_template("revelar_ws.html")

@app.route("/disparar_revelacion")
def disparar_revelacion():
    for pase in pases_asignados.values():
        puede_ingresar = (
            not pase['es_impostor']
            and pase['fecha'] == fecha_actual
            and all([pase['documentacion'], pase['curso'], pase['certificado'],
                     pase['autorizacion'], pase['cita']])
        )
        socketio.emit('resultado', {
            'id': pase['id'],
            'puede_ingresar': puede_ingresar,
            'es_impostor': pase['es_impostor']
        })
    return "Revelación enviada", 200

@socketio.on("connect")
def handle_connect():
    print("Cliente conectado.")

from flask import jsonify

@app.route("/pases")
def obtener_pases():
    return jsonify(list(pases_asignados.values()))

if __name__ == "__main__":
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host="0.0.0.0")
