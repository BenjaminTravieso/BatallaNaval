import socket
import threading
import json

class ServidorJuego:
    def __init__(self, host="0.0.0.0", puerto=12345):
        self.host = host
        self.puerto = puerto
        self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Permitir reusar el puerto sin esperar tiempo de "TIME_WAIT"
        self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.jugadores = []  # Lista de diccionarios: {"conn": conexion, "name": nombre, "ships": []}
        self.lock = threading.Lock()  # Para sincronizar el cambio de turno
        self.turn = 0                # Índice del jugador que tiene el turno
        self.phase = "setup"         # Fase "setup" (organización de barcos) o "battle" (combate)

    def iniciar_servidor(self):
        self.servidor.bind((self.host, self.puerto))
        self.servidor.listen(2)
        print("Servidor iniciado. Esperando jugadores...")

        # Aceptamos conexiones hasta tener dos jugadores
        while len(self.jugadores) < 2:
            conn, addr = self.servidor.accept()
            # Recibir el nombre del jugador
            nombre = conn.recv(1024).decode("utf-8").strip()
            self.jugadores.append({"conn": conn, "name": nombre, "ships": None})
            print(f"Jugador {nombre} conectado desde {addr}")

            # Enviar mensaje de bienvenida e instrucciones para colocar barcos
            bienvenida = {
                "type": "welcome",
                "message": "Bienvenido, {}. Por favor, organiza tus naves enviando un mensaje JSON con el comando 'setBoats' y tus coordenadas.".format(nombre)
            }
            conn.sendall(json.dumps(bienvenida).encode("utf-8"))

        print("¡Todos los jugadores están conectados!")
        print("Esperando que ambos organicen sus naves...")
        self.esperar_configuracion()

    def esperar_configuracion(self):
        # Creamos un hilo por jugador para recibir la configuración de barcos
        threads = []
        for idx in range(2):
            t = threading.Thread(target=self.recibir_configuracion, args=(idx,))
            t.start()
            threads.append(t)
        # Esperamos a que ambos jugadores envíen sus configuraciones
        for t in threads:
            t.join()

        print("Ambos jugadores han organizado sus naves.")
        # Cambiar a fase de batalla y notificar el inicio
        with self.lock:
            self.phase = "battle"
        start_msg = {"type": "startBattle", "message": "Todos han organizado sus naves. ¡La batalla comienza!"}
        for jugador in self.jugadores:
            jugador["conn"].sendall(json.dumps(start_msg).encode("utf-8"))
        
        self.manejar_partida()

    def recibir_configuracion(self, idx):
        jugador = self.jugadores[idx]
        conn = jugador["conn"]
        while True:
            datos = conn.recv(1024).decode("utf-8")
            try:
                msg = json.loads(datos)
                if msg.get("type") == "setBoats":
                    # Se espera que msg["coords"] sea una lista de coordenadas: por ejemplo, [[3,5], [3,6], ...]
                    jugador["ships"] = msg["coords"]
                    print(f"{jugador['name']} organizó sus naves en: {jugador['ships']}")
                    break
                else:
                    # Si se recibe otro comando, se ignora hasta recibir la configuración.
                    print(f"Mensaje inesperado durante la fase de configuración de {jugador['name']}: {msg}")
            except json.JSONDecodeError:
                print("Error al decodificar JSON durante la configuración.")
                continue

    def manejar_partida(self):
        # Fase de batalla: alterna turnos entre los jugadores y procesa ataques
        while True:
            jugador_actual = self.jugadores[self.turn]
            conn_actual = jugador_actual["conn"]

            # Notificar al jugador con turno que debe atacar
            turno_msg = {
                "type": "turnNotification",
                "yourTurn": True,
                "message": "Es tu turno. Ingresa coordenadas de ataque. Ejemplo: {\"type\": \"attack\", \"coordinates\": [3,5]}"
            }
            conn_actual.sendall(json.dumps(turno_msg).encode("utf-8"))

            # Notificar al oponente que debe esperar
            oponente = self.jugadores[1 - self.turn]
            espera_msg = {
                "type": "turnNotification",
                "yourTurn": False,
                "message": "Espera tu turno. El enemigo está atacando..."
            }
            oponente["conn"].sendall(json.dumps(espera_msg).encode("utf-8"))

            # Esperar el ataque del jugador actual
            datos = conn_actual.recv(1024).decode("utf-8")
            try:
                msg = json.loads(datos)
                if msg.get("type") == "attack":
                    coords = msg.get("coordinates")
                    print(f"{jugador_actual['name']} ataca en: {coords}")
                    
                    # Se comprueba el impacto en los barcos del oponente.
                    # Para simplificar, se asume que si las coordenadas atacadas
                    # están dentro de la lista de posiciones del oponente se considera impacto.
                    enemigo = self.jugadores[1 - self.turn]
                    hit = coords in enemigo["ships"]  # Comparación simple; en un juego real se debería validar por cada bloque
                    resultado = {"type": "updateAttackCoords", "coordinates": coords, "hit": hit}
                    
                    # Enviar respuesta al atacante con el resultado del ataque
                    conn_actual.sendall(json.dumps(resultado).encode("utf-8"))
                    
                    # Notificar al oponente que ha sido atacado
                    enemy_msg = {
                        "type": "attacked",
                        "coordinates": coords,
                        "hit": hit,
                        "message": f"El enemigo atacó en {coords} y {'te alcanzó' if hit else 'falló'}."
                    }
                    enemigo["conn"].sendall(json.dumps(enemy_msg).encode("utf-8"))
                    
                    # Aquí se podría agregar lógica para determinar si algún jugador
                    # ha perdido todas sus naves y finalizar la partida.
                    
                    # Cambiar turno al siguiente jugador
                    with self.lock:
                        self.turn = 1 - self.turn
                else:
                    print("Mensaje no reconocido durante la batalla.")
            except json.JSONDecodeError:
                print("Error de JSON al procesar el ataque.")
                continue

if __name__ == "__main__":
    servidor = ServidorJuego()
    servidor.iniciar_servidor()