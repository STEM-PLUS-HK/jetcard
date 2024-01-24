import socket
import threading
import uuid
import time
import json
from jetcard.display_server import IPCConnection, IPCPacket
from typing import Union, Any

class IPCClient(IPCConnection):
    def __init__(self, address: str) -> None:
        self.address: str = address
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.connect(address)
        super().__init__(connection=conn, blocking=True)

class OLEDMenu:
    def __init__(self) -> None:
        self.obj_list: list[Item] = []
        self.actions = {'update_value': self.update_value}
        menu_address = '/tmp/menu_socket'
        self.ipc = IPCClient(menu_address)
        self.ipc_recv_thread = threading.Thread(target=self.ipc_recv)
        self.ipc_recv_thread.start()
        
    def reset(self) -> None:
        self.send(IPCPacket(action='reset_menu'))

    def update_value(self, *args, uuid: Union[str, None] = None, value: Any = True, **kwargs) -> None:
        for item in self.obj_list:
            if item.uuid == uuid:
                item.update(value)
                break

    def ipc_recv(self) -> None:
        while True:
            packets = self.ipc.recv()
            for packet in packets:
                self.actions[packet.action](self, *packet.args, **packet.kwargs)
                    
    def send(self, packet: IPCPacket) -> None:
        self.ipc.send([packet])
    
    def add(self, obj: 'Item') -> None:
        kwargs = {'root': obj.root.uuid if obj.root else 'base',
                  'name': obj.get_description(),
                  'uuid': obj.uuid}
        action = "create_item"
        if isinstance(obj, Function):
            kwargs['create_type'] = 'func'
        elif isinstance(obj, Menu):
            kwargs['create_type'] = 'menu'
        elif isinstance(obj, Variable):
            kwargs['create_type'] = 'var'
            kwargs['value'] = obj.get_value()
            kwargs['step'] = obj.get_step()
        else:
            kwargs['create_type'] = 'item'
        self.send(IPCPacket(action=action, kwargs=kwargs))
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
    
    # used by OLEDMenu class only
    def update(self, value: Union[Any, None] = None):
        pass

class Menu(Item):
    def __init__(self, *args, root=None, description="", **kwargs):
        super().__init__(*args, root=root, description=description, **kwargs)
        
    def reset(self):
        global oled_menu
        if hasattr(self, 'uuid'):
            oled_menu.send(IPCPacket(action='reset_menu', kwargs={'uuid': self.uuid}))
    
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
            oled_menu.send(IPCPacket(action='update_value', kwargs={'uuid':self.uuid, 'value':ret==True}))
            
    def callback_print(self, *args):
        print_data = ""
        for arg in args:
            print_data += str(arg) + " "
        item = Item(root=self, description=print_data)
    
class Variable(Item):
    def __init__(self, *args, root=None, value=None, step=None, description=None, **kwargs):
        self._value = value
        self._step = step
        super().__init__(*args, root=root, description=description, **kwargs)
    
    def get_value(self):
        return self._value
    
    def set_value(self, value):
        global oled_menu
        self._value = value
        if hasattr(self, 'uuid'):
            packet = {'action':'update_value', 'uuid':self.uuid, 'value':value}
            oled_menu.send(IPCPacket(action='update_value', kwargs={'uuid':self.uuid, 'value':value}))
        
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
