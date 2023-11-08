import ipywidgets
import socket
import threading
import uuid
import time
import json
from traitlets import HasTraits, observe

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
               'name': obj.description,
               'uuid': obj.uuid}
        if type(obj) != Menu:
            arg['value'] = obj.value
            arg['step'] = obj.step
            self.send({'action': 'create_var', 'arg': arg})
        else:
            self.send({'action': 'create_menu', 'arg': arg})
        self.obj_list.append(obj)
        
oled_menu = OLEDMenu()

class Menu:
    def __init__(self, root=None, description=""):
        global oled_menu
        self.root = root
        self.description = description
        self.uuid = str(uuid.uuid4())
        oled_menu.add(self)

class FloatSlider(ipywidgets.FloatSlider):
    def __init__(self, root=None, **arg):
        global oled_menu
        super().__init__(**arg)
        self.root = root
        self.uuid = str(uuid.uuid4())
        self.update_from_menu = False
        oled_menu.add(self)
        
    def update(self,value):
        self.update_from_menu = True
        self.value = float(value)
        self.update_from_menu = False
            
    @observe('value')
    def value_change(self, change):
        global oled_menu
        if hasattr(self, 'uuid') and not self.update_from_menu:
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':change['new']}
            oled_menu.send(packet)
            
class IntSlider(ipywidgets.IntSlider):
    def __init__(self, root=None, **arg):
        global oled_menu
        super().__init__(**arg)
        self.root = root
        self.uuid = str(uuid.uuid4())
        self.update_from_menu = False
        oled_menu.add(self)
        
    def update(self,value):
        self.update_from_menu = True
        self.value = float(value)
        self.update_from_menu = False
            
    @observe('value')
    def value_change(self, change):
        global oled_menu
        if hasattr(self, 'uuid') and not self.update_from_menu:
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':change['new']}
            oled_menu.send(packet)
