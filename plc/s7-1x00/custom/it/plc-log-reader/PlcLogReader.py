import socket
import TcpClientBase as base
from time import sleep

# Module to read log from PLC
# version: v1.0
# author: cyanezf
## Description: First version

# Function
def findSubstring(text, substrings):
  for substring in substrings:
    if substring in text:
      return True
  return False

# Class
class PlcLogReader(base.TCPClientBase):
  """TCP Client to read PLC Log
  """
  
  def __init__(self, host: str, port: int, timeout: float = 5.0, show_timeout_message: bool= False):
    """Constructor
    """
    super().__init__(host, port, timeout, show_timeout_message)
  
  def run(self, discard_messages = None, replace = []):
    """Receive data
    """
    try:
      while self.connected:
        try:
          # Receive message
          message = self._receive()

          # Check if message must be showed
          show = discard_messages is None or not findSubstring(message, discard_messages)
          if not show:
            continue
          
          # Replace characters in message
          for find, replace_with in replace:
            message = message.replace(find, replace_with)
            # print(message.replace('\r\n', ''))
            
          # Show message
          print(message)
          
        except socket.timeout:
          continue  # Continue loop if timeout
        
        except ConnectionError:
          break  # Exit loop if connection error
    
    except Exception as e:
      print(f"Error on main loop: {e}")
      raise
      

# Execute
if __name__ == "__main__":
  
  print('##############################################')
  print('# PLC Log Reader #############################')
  print('##############################################')
  SERVER_HOST = "172.16.0.20"
  SERVER_PORT = 2000
    
  while True:
    try:
      with PlcLogReader(SERVER_HOST, SERVER_PORT) as plr:
        plr.run(discard_messages=['99', 'QQ',], replace=[('\r\n', ''), ])
    
    except Exception as e:
      print(f"Channel error: {e}")
    
    print('Wait 5 seconds!')
    sleep (5.0)
    
  