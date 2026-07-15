from enum import Enum
from typing import List, Union, Optional

class ConsoleColor(Enum):
  # Colores de texto
  BLACK = '\033[30m'
  RED = '\033[31m'
  GREEN = '\033[32m'
  YELLOW = '\033[33m'
  BLUE = '\033[34m'
  MAGENTA = '\033[35m'
  CYAN = '\033[36m'
  WHITE = '\033[37m'
  
  # Colores brillantes
  BRIGHT_RED = '\033[91m'
  BRIGHT_GREEN = '\033[92m'
  BRIGHT_YELLOW = '\033[93m'
  BRIGHT_BLUE = '\033[94m'
  BRIGHT_MAGENTA = '\033[95m'
  BRIGHT_CYAN = '\033[96m'
    
class ConsoleBackground(Enum):
  # Colores de fondo
  BLACK = '\033[40m'
  RED = '\033[41m'
  GREEN = '\033[42m'
  YELLOW = '\033[43m'
  BLUE = '\033[44m'
  MAGENTA = '\033[45m'
  CYAN = '\033[46m'
  WHITE = '\033[47m'
  
class ConsoleStyle(Enum):
  # Estilos
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'
  # Reset
  RESET = '\033[0m'



def colored_text(text: str | None = '', color: ConsoleColor | None = None , background: ConsoleBackground | None = None, styles: list[ConsoleStyle] | None = None) -> str:
  '''
    Function to color a text
  '''
  return (color.value if color else '') + \
    (background.value if background else '') + \
    (''.join(style.value for style in styles) if styles else '') + \
    (text if text else '') + \
    ConsoleStyle.RESET.value

def red_text(text: str | None = '') -> str:
  return ConsoleColor.RED.value + (text if text else '') + ConsoleStyle.RESET.value
