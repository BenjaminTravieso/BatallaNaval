import socket
import threading
import json
import pygame

class ClienteJuego:
    def __init__(self, host="127.0.0.1", puerto=12345):
        self.host = host
        self.puerto = puerto
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.connect((self.host, self.puerto))
        except Exception as e:
            print("Error al conectar al servidor:", e)
            exit(1)
        self.name = input("Ingresa tu nombre: ").strip()
        self.server.sendall(self.name.encode("utf-8"))
        
        # Estado del juego
        self.phase = "setup"      # "setup" para posicionar barcos, "battle" para combate
        self.my_turn = False      # Se actualizará mediante mensajes del servidor
        self.ships = []           # Posiciones de tus barcos (ej.: [[1,2], [2,2], ...])
        self.ship_hits = []       # Posiciones de tus barcos alcanzadas por el enemigo
        self.enemy_hits = []      # Posiciones en el tablero enemigo en las que alcanzaste un impacto
        self.attack_result = None # Último resultado de ataque recibido
        self.enemy_attack = None  # Último ataque recibido
        
        # Parámetros gráficos
        self.cell_size = 30
        self.board_dim = 10 * self.cell_size  # 300 píxeles (10 celdas de 30px)
        self.own_board_origin = (50, 50)        # Tablero propio (para colocar barcos y ver tus impactos)
        self.enemy_board_origin = (400, 50)     # Tablero enemigo (donde atacas)
        
        # Iniciar hilo para recibir mensajes sin bloquear la UI
        self.receiver_thread = threading.Thread(target=self.escuchar_servidor, daemon=True)
        self.receiver_thread.start()
        
        self.iniciar_pygame()
    
    def escuchar_servidor(self):
        """Hilo dedicado a recibir y procesar mensajes del servidor."""
        while True:
            try:
                data = self.server.recv(1024).decode("utf-8")
                if not data:
                    continue
                msg = json.loads(data)
                msg_type = msg.get("type")
                if msg_type == "welcome":
                    print(msg.get("message"))
                elif msg_type == "startBattle":
                    print(msg.get("message"))
                    self.phase = "battle"
                elif msg_type == "turnNotification":
                    self.my_turn = msg.get("yourTurn", False)
                    print(msg.get("message"))
                elif msg_type == "updateAttackCoords":
                    self.attack_result = msg
                    print("Resultado de tu ataque:", msg)
                    if msg.get("hit"):
                        # Registrar el impacto en el tablero enemigo
                        if msg.get("coordinates") not in self.enemy_hits:
                            self.enemy_hits.append(msg.get("coordinates"))
                elif msg_type == "attacked":
                    self.enemy_attack = msg
                    print(msg.get("message"))
                    if msg.get("hit"):
                        # Registrar el impacto en tu tablero propio
                        if msg.get("coordinates") not in self.ship_hits:
                            self.ship_hits.append(msg.get("coordinates"))
                else:
                    print("Mensaje desconocido del servidor:", msg)
            except json.JSONDecodeError:
                print("Error al decodificar JSON.")
            except Exception as e:
                print("Error recibiendo mensaje:", e)
                break
    
    def iniciar_pygame(self):
        """Configura la ventana y arranca el loop principal de Pygame."""
        pygame.init()
        self.width, self.height = 800, 500
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Batalla Naval - Cliente")
        self.clock = pygame.time.Clock()
        self.run()
    
    def run(self):
        """Loop principal de Pygame."""
        running = True
        font = pygame.font.SysFont(None, 24)
        while running:
            self.clock.tick(30)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.KEYDOWN:
                    # En fase de configuración: al presionar Enter se envía la configuración de barcos
                    if self.phase == "setup" and event.key == pygame.K_RETURN:
                        config_msg = {"type": "setBoats", "coords": self.ships}
                        self.server.sendall(json.dumps(config_msg).encode("utf-8"))
                        print("Configuración enviada:", self.ships)
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if self.phase == "setup":
                        # Permite colocar barcos en el tablero propio
                        ox, oy = self.own_board_origin
                        if ox <= pos[0] < ox + self.board_dim and oy <= pos[1] < oy + self.board_dim:
                            grid_x = (pos[0] - ox) // self.cell_size
                            grid_y = (pos[1] - oy) // self.cell_size
                            if [grid_x, grid_y] not in self.ships:
                                self.ships.append([grid_x, grid_y])
                                print("Barco agregado en:", [grid_x, grid_y])
                    elif self.phase == "battle" and self.my_turn:
                        # En fase de batalla, al hacer clic en el tablero enemigo se envía un ataque
                        ex, ey = self.enemy_board_origin
                        if ex <= pos[0] < ex + self.board_dim and ey <= pos[1] < ey + self.board_dim:
                            grid_x = (pos[0] - ex) // self.cell_size
                            grid_y = (pos[1] - ey) // self.cell_size
                            attack_msg = {"type": "attack", "coordinates": [grid_x, grid_y]}
                            self.server.sendall(json.dumps(attack_msg).encode("utf-8"))
                            print("Ataque enviado en:", [grid_x, grid_y])
            
            # Actualizar la interfaz gráfica
            self.screen.fill((0, 0, 50))
            self.draw_grids()
            if self.phase == "setup":
                texto = "Fase de Configuración: coloca tus barcos (tablero izq.) y presiona Enter cuando termines."
                self.draw_text(texto, 50, 400, font)
                self.draw_ships()
            elif self.phase == "battle":
                if self.my_turn:
                    texto = "¡Tu turno! Haz clic en el tablero enemigo (lado der.) para atacar."
                else:
                    texto = "Esperando turno..."
                self.draw_text(texto, 400, 400, font)
                self.draw_ships()
                self.draw_enemy_hits()
            pygame.display.flip()
        pygame.quit()
    
    def draw_grids(self):
        """Dibuja ambas cuadrículas con separación."""
        # Tablero propio
        ox, oy = self.own_board_origin
        for i in range(11):
            start_x = ox + i * self.cell_size
            pygame.draw.line(self.screen, (255, 255, 255), (start_x, oy), (start_x, oy + self.board_dim))
        for j in range(11):
            start_y = oy + j * self.cell_size
            pygame.draw.line(self.screen, (255, 255, 255), (ox, start_y), (ox + self.board_dim, start_y))
        
        # Tablero enemigo
        ex, ey = self.enemy_board_origin
        for i in range(11):
            start_x = ex + i * self.cell_size
            pygame.draw.line(self.screen, (255, 255, 255), (start_x, ey), (start_x, ey + self.board_dim))
        for j in range(11):
            start_y = ey + j * self.cell_size
            pygame.draw.line(self.screen, (255, 255, 255), (ex, start_y), (ex + self.board_dim, start_y))
    
    def draw_ships(self):
        """
        Dibuja los barcos en el tablero propio.
        Se pinta en verde si no han sido alcanzados, y en rojo si han sido impactados.
        """
        ox, oy = self.own_board_origin
        for ship in self.ships:
            x, y = ship
            rect = pygame.Rect(ox + x * self.cell_size, oy + y * self.cell_size, self.cell_size, self.cell_size)
            color = (255, 0, 0) if [x, y] in self.ship_hits else (0, 255, 0)
            pygame.draw.rect(self.screen, color, rect)
    
    def draw_enemy_hits(self):
        """
        Dibuja en el tablero enemigo los ataques que lograron impacto.
        Se pinta cada celda impactada en rojo.
        """
        ex, ey = self.enemy_board_origin
        for pos in self.enemy_hits:
            x, y = pos
            rect = pygame.Rect(ex + x * self.cell_size, ey + y * self.cell_size, self.cell_size, self.cell_size)
            pygame.draw.rect(self.screen, (255, 0, 0), rect)
    
    def draw_text(self, text, x, y, font):
        """Dibuja cadenas de texto en la pantalla."""
        text_surface = font.render(text, True, (255, 255, 255))
        self.screen.blit(text_surface, (x, y))

if __name__ == "__main__":
    ClienteJuego(host="127.0.0.1", puerto=12345)