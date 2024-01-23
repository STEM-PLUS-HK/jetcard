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
        if isinstance(obj, Function):
            self.send({'action': 'create_func', 'arg': arg})
        elif isinstance(obj, Menu):
            self.send({'action': 'create_menu', 'arg': arg})
        elif isinstance(obj, Variable):
            arg['value'] = obj.get_value()
            arg['step'] = obj.get_step()
            self.send({'action': 'create_var', 'arg': arg})
        else:
            arg['value'] = None
            arg['step'] = None
            self.send({'action': 'create_var', 'arg': arg})
        self.obj_list.append(obj)
        
oled_menu = OLEDMenu()

def reset_menu():
    global oled_menu
    oled_menu.reset()

class Item:
    def __init__(self, *args, root=None, description="", **kwargs):
        global oled_menu
        self.root = root
        self._description = description
        self.uuid = str(uuid.uuid4())
        oled_menu.add(self)

    def get_description(self):
        return self._description
    
class Menu(Item):
    def __init__(self, *args, root=None, description="", **kwargs):
        super().__init__(*args, root=root, description=description, **kwargs)
        
    def reset(self):
        global oled_menu
        if hasattr(self, 'uuid'):
            packet = {'action':'reset_menu', 'uuid':self.uuid}
            oled_menu.send(packet)
    
class Function(Menu):
    def __init__(self, callback_func, *args, root=None, description="", **kwargs):
        '''
        Callback argument: callback_func(self)
        Callback return: if return is True, the OLED menu will go back to the main menu immediately
        '''
        self.callback = callback_func
        self.callback_thread = None
        super().__init__(*args, root=root, description=description, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        if self.callback_thread != None:
            self.callback_thread.join()
        self.callback_thread = threading.Thread(target=self.callback_wrapper)
        self.callback_thread.start()
        
    def callback_wrapper(self):
        global oled_menu
        ret = True if self.callback == None else self.callback(self)
        if hasattr(self, 'uuid'):
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':ret==True}
            oled_menu.send(packet)
            
    def callback_print(self, output):
        print_data = str(output)
        item = Item(root=self, description=print_data)
    
class Variable(Item):
    def __init__(self, *args, root=None, value=None, step=None, description=None, **kwargs):
        self._value = value
        self._step = step
        super().__init__(*args, root=root, description=description, **kwargs)
        
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
        
class FloatVariable(Variable):
    def __init__(self, *args, root=None, value=0.0, step=0.1, description='', **kwargs):
        super().__init__(*args, root=root, value=float(value), step=step, description=description, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = float(value)
            
class IntVariable(Variable):    
    def __init__(self, *args, root=None, value=0, step=1, description='', **kwargs):
        super().__init__(*args, root=root, value=int(value), step=step, description=description, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = int(value)

class BoolVariable(Variable):
    def __init__(self, *args, root=None, value=True, description='', **kwargs):
        super().__init__(*args, root=root, value=bool(value), step=None, description=description, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        self._value = bool(value)
