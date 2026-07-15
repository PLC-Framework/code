import socket

class TCPClientBase:
  """Clase base para los clientes TCP con gestión de conexión
  """
    
  def __init__(self, host: str, port: int, timeout: float = 5.0, show_timeout_message: bool= False):
    """Constructor
    """
    self.host = host
    self.port = port
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
      print(f"Client error: {exc_val}")
    return False  # No manejamos la excepción, la propagamos
  
  def connect(self):
    """Establece la conexión con el servidor
    """
    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.settimeout(self.timeout)
      self.socket.connect((self.host, self.port))
      self.connected = True
      print(f'Connected to <{self.host}:{self.port}>')
      
    except socket.error as e:
      self.connected = False
      print(f"Connection error: {e}")
      raise
  
  def close(self):
    """Cierra la conexión
    """
    if self.socket:
      try:
        self.socket.close()
        print("Connection closed")
        
      except socket.error as e:
        print(f"Error closing connection: {e}")
        
      finally:
        self.socket = None
        self.connected = False
  
  def _send(self, data: str):
    """Envía datos al servidor
    """
    if not self.connected:
      raise ConnectionError("Client is not connected to Server")
    
    try:
      self.socket.sendall(data.encode('utf-8'))
      
    except socket.error as e:
      self.connected = False
      print(f"Error sending data: {e}")
      raise
  
  def _receive(self, buffer_size: int = 4096) -> str:
    """Recibe datos del servidor
    """
    if not self.connected:
      raise ConnectionError("Client is not connected to Server")
    
    try:
      data = self.socket.recv(buffer_size)
      if not data:
        self.connected = False
        raise ConnectionError("Connection closed by Server")
      return data.decode('utf-8')
    
    except socket.timeout:
      if self.show_timeout_message:
        print("Timeout while receiving data")
      raise
    
    except socket.error as e:
      self.connected = False
      print(f"Error receiving data: {e}")
      raise

