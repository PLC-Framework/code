
import threading
import socket
from time import sleep
from ConsoleColoredText import ConsoleColor, ConsoleStyle, colored_text, red_text

# Function
def findSubstring(text, substrings):
  for substring in substrings:
    if substring in text:
      return True
  return False

class TCPClientBase:
  """Clase base para los clientes TCP con gestión de conexión
  """
    
  def __init__(self, host: str, port: int, name: str, console_color: ConsoleColor, timeout: float = 5.0, show_timeout_message: bool= False):
    """Constructor
    """
    self.host = host
    self.port = port
    self.name = name
    self.console_color = console_color
    self.timeout = timeout
    self.socket = None
    self.connected = False
    self.show_timeout_message = show_timeout_message
    
  def __enter__(self):
    """Enter
    """
    self.connect()
    return self
  
  def __exit__(self, exc_type, exc_val, exc_tb):
    """Exit
    """
    self.close()
    if exc_type is not None:
      print(colored_text(f"{self.name} >>> Error:", color=self.console_color), red_text(exc_val))
    return False  # No manejamos la excepción, la propagamos
  
  def connect(self):
    """Establece la conexión con el servidor
    """
    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.settimeout(self.timeout)
      self.socket.connect((self.host, self.port))
      self.connected = True
      print(colored_text(f'{self.name} >>> Connected to {self.host}:{self.port}', color= self.console_color))
      
    except socket.error as e:
      self.connected = False
      print(colored_text(f"{self.name} >>> Connection error:", color=self.console_color), red_text(e.strerror))
      raise
  
  def close(self):
    """Cierra la conexión
    """
    if self.socket:
      try:
        self.socket.close()
        print(colored_text(f"{self.name} >>> Connection closed!", color=self.console_color))
        
      except socket.error as e:
        print(colored_text(f"{self.name} >>> Error closing connection:", color=self.console_color), red_text(e.strerror))
        
      finally:
        self.socket = None
        self.connected = False
  
  def _send(self, data: str):
    """Envía datos al servidor
    """
    if not self.connected:
      raise ConnectionError(f"{self.name} >>> It is not connected to Server")
    
    try:
      self.socket.sendall(data.encode('utf-8'))
      
    except socket.error as e:
      self.connected = False
      print(colored_text(f"{self.name} >>> Error sending data:", color=self.console_color), red_text(e.strerror))
      raise
  
  def _receive(self, buffer_size: int = 4096) -> str:
    """Recibe datos del servidor
    """
    if not self.connected:
      raise ConnectionError(f"{self.name} >>> It is not connected to Server")
    
    try:
      data = self.socket.recv(buffer_size)
      if not data:
        self.connected = False
        raise ConnectionError(f"{self.name} >>> Connection closed by Server")
      return data.decode('utf-8')
    
    except socket.timeout:
      if self.show_timeout_message:
        print(colored_text(f"{self.name} >>> Timeout while receiving data", color=self.console_color))
      raise
    
    except socket.error as e:
      self.connected = False
      print(colored_text(f"{self.name} >>> Error receiving data:", color=self.console_color), red_text(e.strerror))
      raise


class PlcLogReader(TCPClientBase):
  """TCP Client to read PLC Log
  """
  
  def __init__(self, host: str, port: int, name: str, console_color: ConsoleColor, timeout: float = 5.0, show_timeout_message: bool= False):
    """Constructor
    """
    super().__init__(host, port, name, console_color, timeout, show_timeout_message)
    self.name = name
    self.console_color = console_color
  
  def run(self, discard_messages = None, show_messages: list[str] | None = None, and_show_messages: list[str] | None = None, replaces = None):
    """Receive data
    """
    try:
      while self.connected:
        try:
          # Receive message
          message = self._receive()

          # Check if message must be discarted
          if discard_messages:
            if findSubstring(message, discard_messages):
              continue
            
          # Check if message must be showed
          if show_messages:
            if not findSubstring(message, show_messages):
              continue
          
          if and_show_messages:
            if not findSubstring(message, and_show_messages):
              continue
          
          # Replace characters in message
          if replaces:
            for find, replace_with in replaces:
              message = message.replace(find, replace_with)
            
          # Show message
          print(colored_text(f'{self.name} >>> {message}', color= self.console_color))
          
        except socket.timeout as e:
          continue  # Continue loop if timeout
        
        except ConnectionError as e:
          break  # Exit loop if connection error
    
    except Exception as e:
      print(colored_text(f"{self.name} >>> Error on main loop:", color=self.console_color), red_text(e.strerror))
      raise
      
class PlcLogReaderThread(threading.Thread):
  """Thread para manejar la conexión a un servidor PLC
  """
  
  def __init__(self, host: str, port: int, server_name: str = None, console_color = None,
              discard_messages=None, show_messages=None, and_show_mesages=None, replaces=None,
              timeout: float = 5.0, show_timeout_message: bool = False):
    
    threading.Thread.__init__(self)
    self.host = host
    self.port = port
    self.server_name = server_name or f"{host}:{port}"
    self.console_color = console_color
    self.discard_messages = discard_messages
    self.show_messages = show_messages
    self.and_show_messages = and_show_mesages
    self.replaces = replaces
    self.timeout = timeout
    self.show_timeout_message = show_timeout_message
    self.running = True
    self.daemon = True  # Hilo daemon para que termine con el programa principal
  
  def run(self):
    """Método principal del hilo
    """
    print(colored_text(f"{self.server_name} >>> Thread started", color= self.console_color))
    
    while self.running:
      try:
        with PlcLogReader(self.host, self.port, self.server_name, self.console_color,  
                        self.timeout, self.show_timeout_message) as plc:
          plc.run(
              discard_messages=self.discard_messages,
              show_messages=self.show_messages,
              and_show_messages=self.and_show_messages,
              replaces=self.replaces
          )
      
      except Exception as e:
        print(colored_text(f"{self.server_name} >>> Channel error:", color=self.console_color), red_text(e.__str__()))
      
      if self.running:
        print(colored_text(f"{self.server_name} >>> Wait 5 seconds!", color=self.console_color))
        sleep(5.0)
    
    print(colored_text(f"{self.server_name} >>> Thread stopped", color=self.console_color ))
  
  def stop(self):
    """Detiene el hilo
    """
    self.running = False


class PlcMultiServerManager:
  """Gestor para múltiples conexiones PLC
  """
  
  def __init__(self):
    self.threads = []
  
  def add_server(self, host: str, port: int, server_name: str = None, console_color = None,
                discard_messages=None, show_messages=None, and_show_messages=None, replaces=None,
                timeout: float = 5.0, show_timeout_message: bool = False):
    """Añade un servidor a la lista de conexiones
    """
    thread = PlcLogReaderThread(
      host=host,
      port=port,
      server_name=server_name,
      console_color = console_color,
      discard_messages=discard_messages,
      show_messages=show_messages,
      and_show_mesages=and_show_messages,
      replaces=replaces,
      timeout=timeout,
      show_timeout_message=show_timeout_message
    )
    self.threads.append(thread)
    return thread
  
  def start_all(self):
    """Inicia todas las conexiones
    """
    print("Starting all PLC connections...")
    for thread in self.threads:
      thread.start()
  
  def stop_all(self):
    """Detiene todas las conexiones
    """
    print("Stopping all PLC connections...")
    for thread in self.threads:
      thread.stop()
    
    # Esperar a que terminen los hilos
    for thread in self.threads:
      thread.join(timeout=2)
  
  def is_any_alive(self):
    """Verifica si algún hilo sigue activo
    """
    return any(thread.is_alive() for thread in self.threads)


# Execute
if __name__ == "__main__":
  
  print('Application started')
  
  servers = [
    {'name': 'Flapper', 'host': '127.0.0.1', 'port': 2000,
     'console_color' : ConsoleColor.BLUE,
     'show_messages' : [':CA:', ':IC:', ':RR:', ':ES:']},
      
    {'name': 'Master*', 'host': '127.0.0.1', 'port': 2001, 
     'console_color' : ConsoleColor.GREEN,
     'show_messages' : ['position', 'p_alarms', 'release', 'p_empty', 'p_inmode','p_opmode', 'p_enable', 'p_in_en'],
     'and_show_messages' : ['I16'],
     'replaces' : [('\r\n', '')]}
    ]
  
  # Crear gestor de múltiples servidores
  manager = PlcMultiServerManager()
  
  # Añadir servidores
  for server in servers:
    manager.add_server(
      host=server["host"],
      port=server["port"],
      server_name=server["name"],
      console_color=server['console_color'],
      show_messages=server.get("show_messages"),
      and_show_messages=server.get('and_show_messages'),
      replaces=server.get("replaces"),
      discard_messages=server.get("discard_messages")
    )
  
  try:
    # Iniciar todas las conexiones
    manager.start_all()
    
    # Mantener el programa ejecutándose
    print("Press Ctrl+C to stop all connections...")
    while manager.is_any_alive():
      sleep(1)
  
  except KeyboardInterrupt:
    print("\nShutting down...")
    manager.stop_all()
    print("All connections stopped.")
  
  except Exception as e:
    print(f"Unexpected error: {e}")
    manager.stop_all()
  
  finally:
    print(f'Application closed!')
