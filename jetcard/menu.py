import socket
import threading
import uuid
import time
import json

class OLEDMenu:
    def __init__(self):
        menu_address = '/tmp/menu_socket'
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(menu_address)
        self.obj_list = []
        self.recv_thread = threading.Thread(target=self._recv)
        self.recv_thread.start()
        
    def reset(self):
        self.send({'action': 'reset_menu'})
        
    def _recv(self):
        var_id = None
        var_value = None
        recv_data = bytes([])
        while True:
            recv_data += self.sock.recv(1024)
            
            packet_length = recv_data[0] | (recv_data[1]<<8)
            packet = recv_data[2:packet_length+2]
            recv_data = recv_data[packet_length+2:] #remove processed data
            packet = json.loads(packet.decode())
            if packet['action'] == 'value_update':
                for o in self.obj_list:
                    if o.uuid == packet['uuid']:
                        o.update(packet['value'])
                        break
                    
    def send(self, packet):
        packet_string = json.dumps(packet)
        data_out = packet_string.encode()
        packet_len = len(data_out)
        data_out = bytes([packet_len&0xFF, (packet_len>>8)&0xFF]) + data_out
        self.sock.sendall(data_out)
    
    def add(self, obj):
        arg = {'root': obj.root.uuid if obj.root else 'base',
               'name': obj.get_description(),
               'uuid': obj.uuid}
        if isinstance(obj, Menu):
            self.send({'action': 'create_menu', 'arg': arg})
        else:
            arg['value'] = obj.get_value()
            arg['step'] = obj.get_step()
            self.send({'action': 'create_var', 'arg': arg})
        self.obj_list.append(obj)
        
oled_menu = OLEDMenu()

def reset_menu():
    global oled_menu
    oled_menu.reset()

class Menu:
    def __init__(self, root=None, description=""):
        global oled_menu
        self.root = root
        self._description = description
        self.uuid = str(uuid.uuid4())
        oled_menu.add(self)

    def get_description(self):
        return self._description
    
class Variable:
    def __init__(self, root=None, value=None, step=None, description=None, *args, **kwargs):
        global oled_menu
        self.root = root
        self.uuid = str(uuid.uuid4())
        self._value = value
        self._step = step
        self._description = description
        oled_menu.add(self)
        
    # used by OLEDMenu class only
    def update(self,value):
        raise NotImplementedError("Derived class should implement this method")
    
    def get_value(self):
        return self._value
    
    def set_value(self, value):
        global oled_menu
        self._value = value
        if hasattr(self, 'uuid'):
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':value}
            oled_menu.send(packet)
        
    def get_step(self):
        return self._step
    
    def get_description(self):
        return self._description
        
class FloatVariable(Variable):
    def __init__(self, root=None, value=0.0, step=0.1, description='', *args, **kwargs):
        print(value, step, description, args, kwargs)
        super().__init__(root=root, value=float(value), step=step, description=description, *args, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = float(value)
            
class IntVariable(Variable):    
    def __init__(self, root=None, value=0, step=1, description='', *args, **kwargs):
        Variable.__init__(self, root=root, value=int(value), step=step, description=description, *args, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = int(value)

class BoolVariable(Variable):
    def __init__(self, root=None, value=True, description='', *args, **kwargs):
        Variable.__init__(self, root=root, value=bool(value), step=None, description=description, *args, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = bool(value)
