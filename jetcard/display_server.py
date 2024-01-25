import threading
import Adafruit_SSD1306
import time
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw
from flask import Flask
from .utils import ip_address, power_mode, power_usage, cpu_usage, gpu_usage, memory_usage, disk_usage
import Jetson.GPIO as GPIO
import os
import socket
import decimal
import json
from enum import Enum
from typing import List, Tuple, Union, Any
from uuid import uuid4

UP_CHANNEL = 13
RIGHT_CHANNEL = 15
LEFT_CHANNEL = 16
DOWN_CHANNEL = 18
CENTER_CHANNEL = 19

class SwitchAction(Enum):
    PRESS_NOTHING = 0
    PRESS_CENTER = 1
    PRESS_UP = 2
    PRESS_DOWN = 3
    PRESS_LEFT = 4
    PRESS_RIGHT = 5


class DisplayInfo:
    def __init__(self, display_width: int, display_height: int, font: int, font_width: int, font_height: int) -> None:
        self.max_line = display_height // font_height
        self.line_height = font_height
        self.line_width = display_width
        self.font = font
        self.font_width = font_width

class Item:
    def __init__(self, root: Union[Any, None] = None, name: str = "", uuid: str = "") -> None:
        assert uuid != "", "uuid field cannot be empty string"
        self.root: Union[Any, None] = root
        self.name: str = name
        self.uuid: str = uuid
        self.lhs_display: str = name
        self.rhs_display: str = ""
    def get_display_info(self) -> Tuple[str, str]:
        return self.lhs_display, self.rhs_display
    def find(self, uuid: str) -> Union[Any, None]:
        return self if self.uuid == uuid else None
    def press_center_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        return None
    def press_up_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        return None
    def press_down_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        return None
    def press_left_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        return None
    def press_right_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        return None
    def render(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Any:
        return self.root    # won't render anything in Item, so return back to its root
    def display(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, action: SwitchAction, ipc: 'IPC') -> Any:
        ret = None
        if action == SwitchAction.PRESS_CENTER:
            ret = self.press_center_callback(disp_info=disp_info, draw=draw, ipc=ipc)
        elif action == SwitchAction.PRESS_UP:
            ret = self.press_up_callback(disp_info=disp_info, draw=draw, ipc=ipc)
        elif action == SwitchAction.PRESS_DOWN:
            ret = self.press_down_callback(disp_info=disp_info, draw=draw, ipc=ipc)
        elif action == SwitchAction.PRESS_LEFT:
            ret = self.press_left_callback(disp_info=disp_info, draw=draw, ipc=ipc)
        elif action == SwitchAction.PRESS_RIGHT:
            ret = self.press_right_callback(disp_info=disp_info, draw=draw, ipc=ipc)
        if ret == None:
            ret = self.render(disp_info=disp_info, draw=draw, ipc=ipc)
        return ret

class Return(Item):
    def __init__(self, root: Union[Any, None] = None, display: str = "<< Return", uuid: Union[str, None] = None, callback: Union[callable, None] = None) -> None:
        if uuid == None:
            uuid = "return" + str(uuid4()) # generate a uuid, adding a "return" prefix, ensure not duplicate with other
        super().__init__(root=root, name="return", uuid=uuid)
        self.lhs_display = display
        self.callback = callback
    def display(self, disp_info: DisplayInfo, draw, action: SwitchAction, ipc: 'IPC') -> Any:
        if self.callback:
            self.callback()
        return self.root.root

class Menu(Item):
    def __init__(self, root: Union[Any, None] = None, name: str = "", uuid: str = "base") -> None:
        super().__init__(root=root, name=name, uuid=uuid)
        return_item: Return = Return(root=self)
        self.obj_list: list[Item] = [return_item]
        self.select_idx: int = 0
        self.first_display_idx: int = 0
        self.lhs_display = ">> " + name
    def add(self, obj: Item) -> None:
        self.obj_list.append(obj)
    def reset(self) -> None:
        self.obj_list = self.obj_list[:1]
    def find(self, uuid: str) -> Union[Item, None]:
        ret = super().find(uuid)
        if ret == None:
            for o in self.obj_list:
                ret = o.find(uuid)
                if ret != None:
                    break
        return ret
    def press_center_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Item, None]:
        if len(self.obj_list) == 0:
            return None
        return self.obj_list[self.select_idx]#.display(disp_info, draw, SwitchAction.PRESS_NOTHING, ipc)
    def press_up_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.select_idx -= 1
    def press_down_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.select_idx += 1
    def render(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Any:
        if self.select_idx < 0:
            self.select_idx = len(self.obj_list)-1
            self.first_display_idx = max(len(self.obj_list) - disp_info.max_line, 0)
        elif self.select_idx >= len(self.obj_list):
            self.select_idx = 0
            self.first_display_idx = 0
        elif self.select_idx < self.first_display_idx:
            self.first_display_idx = self.select_idx
        elif self.select_idx == self.first_display_idx + disp_info.max_line:
            self.first_display_idx += 1
        for i in range(disp_info.max_line):
            idx = self.first_display_idx + i
            if idx == len(self.obj_list):
                break
            x = 0
            y = disp_info.line_height * i - 2
            obj = self.obj_list[idx]
            lhs, rhs = obj.get_display_info()
            if idx == self.select_idx:
                draw.rectangle((x, y+2, disp_info.line_width, y+disp_info.line_height+2), outline=255, fill=255)
                fill = 0
            else:
                fill = 255
            draw.text((x, y), lhs, font=disp_info.font, fill=fill)
            rhs_len = len(rhs)
            if rhs_len:
                x = disp_info.line_width - rhs_len * disp_info.font_width
                draw.text((x, y), rhs, font=disp_info.font, fill=fill)
        return self

class Variable(Item):
    def __init__(self, root: Union[Any, None] = None, name: str = "", value: Any = 0, step: Union[Any, None] = None, uuid: str = "") -> None:
        super().__init__(root=root, name=name, uuid=uuid)
        self.value = value
        self.step = step
        self.step_exponent = -decimal.Decimal(str(step)).as_tuple().exponent if step else None
        self.lhs_display = self.name
        self.rhs_display = str(self.value) if self.value != None else ""
    def update_value(self, value: Union[Any, None] = None, change: Union[Any, None] = None) -> None:
        if value != None:
            self.value = value
        elif change != None:
            if self.step != None:
                self.value += self.step*change
            elif isinstance(self.value, bool):
                self.value = not self.value
        if self.step_exponent != None:
            self.value = round(self.value, self.step_exponent)
        self.rhs_display = str(self.value)
    def press_center_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        # User accept result, send the value back to client
        ipc.send([IPCPacket(action='update_value', kwargs={'uuid': self.uuid, 'value':self.value})])
        return self.root
    def press_up_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.update_value(change=-10)
    def press_down_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.update_value(change=10)
    def press_left_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.update_value(change=-1)
    def press_right_callback(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Union[Any, None]:
        self.update_value(change=1)
    def render(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, ipc: 'IPC') -> Any:
        x = (disp_info.line_width - len(self.name) * disp_info.font_width) // 2
        draw.text((x, 2), self.name, font=disp_info.font, fill=255)
        value_str = "<<  " + str(self.value) + "  >>"
        x = (disp_info.line_width - len(value_str) * disp_info.font_width) // 2
        draw.text((x, 16), value_str,  font=disp_info.font, fill=255)
        return self

class Function(Menu):
    def __init__(self, root: Union[Any, None] = None, name: str = "", uuid: str = "") -> None:
        super().__init__(root=root, name=name, uuid=uuid)
        self.obj_list = []
        self.callback_running: bool = False
        self.lhs_display = "[ {name} ]".format(name=self.name)
    def add(self, obj):
        super().add(obj)
        self.select_idx = len(self.obj_list)-1
    def add_finish_return(self):
        return_item: Return = Return(root=self, display="<< completed, return", callback=self.reset)
        self.add(return_item)
    def reset(self):
        self.callback_running = False
        self.obj_list = []
    def display(self, disp_info: DisplayInfo, draw: PIL.ImageDraw, action: SwitchAction, ipc: 'IPC') -> Any:
        if not self.callback_running:
            self.reset()
            self.callback_running = True
            ipc.send([IPCPacket(action='update_value', kwargs={'uuid': self.uuid, 'value': 'call'})])
        return super().display(disp_info=disp_info, draw=draw, action=action, ipc=ipc)
    
class IPCPacket:
    def __init__(self, json_str: Union[str, None] = None, action: Union[str, None] = None, args: list = [], kwargs: dict = {}) -> None:
        if json_str != None:
            packet = json.loads(json_str)
            self.action = packet['action']
            self.args = packet['args']
            self.kwargs = packet['kwargs']
        elif action != None:
            self.action = action
            self.args = args
            self.kwargs = kwargs
    def stringify(self) -> str:
        packet = {'action': self.action,
                  'args': self.args,
                  'kwargs': self.kwargs}
        return json.dumps(packet)

class IPCConnection:
    def __init__(self, connection: socket.socket, blocking: bool = False) -> None:
        self.connection = connection
        self.connection.setblocking(blocking)
        self.recv_data = bytes([])
    def recv(self) -> List[IPCPacket]:
        try:
            data = self.connection.recv(1024)
            if data:
                self.recv_data += data
        except BlockingIOError:
            # no client send data
            pass
        recv_packets: list[IPCPacket] = []
        # first two byte is the packet length, big endian, after that is json string
        data_len = len(self.recv_data)
        while data_len > 2:
            packet_len = self.recv_data[0] | (self.recv_data[1]<<8)
            if data_len - 2 >= packet_len:
                recv_packets.append(IPCPacket(json_str=self.recv_data[2:packet_len+2].decode()))
                self.recv_data = self.recv_data[packet_len+2:]  # remove processed data
                data_len = len(self.recv_data)    # update remaining data length
            else:
                break
        return recv_packets
    def send(self, packets: List[IPCPacket]) -> bool:
        '''
        return status of sending packets
        '''
        send_data = bytes([])
        for packet in packets:
            packet_bytes = packet.stringify().encode()
            packet_len = len(packet_bytes)
            send_data += bytes([packet_len&0xFF, (packet_len>>8)&0xFF]) + packet_bytes
        try:
            self.connection.sendall(send_data)
            return True
        except:
            return False

class IPC:
    def __init__(self, address: str) -> None:
        self.address: str = address
        try:
            os.remove(self.address)
        except OSError:
            pass
        self.socket: socket.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.address)
        os.chmod(self.address, 0o777)   # giving permission such that non root user can still connect to this socket
        self.socket.listen(1)
        self.socket.setblocking(False)
        self.reset()
    def reset(self) -> None:
        self.connections: list[IPCConnection] = []
    def recv(self) -> List[IPCPacket]:
        try:
            conn, addr = self.socket.accept()
            self.connections.append(IPCConnection(conn))
        except BlockingIOError:
            pass
        recv_packets: list[IPCPacket] = []
        for conn in self.connections:
            recv_packets += conn.recv()
        return recv_packets
    def send(self, packets: List[IPCPacket]) -> None:
        for conn in self.connections:
            if conn.send(packets) == False:
                self.connections.remove(conn)   # clean up broken connection

class DisplayServer(object):
    
    def __init__(self, *args, **kwargs):
        self.display = Adafruit_SSD1306.SSD1306_128_32(rst=None, i2c_bus=1, gpio=1) 
        self.display.begin()
        self.display.clear()
        self.display.display()
        self.font = PIL.ImageFont.load_default()
        self.image = PIL.Image.new('1', (self.display.width, self.display.height))
        self.draw = PIL.ImageDraw.Draw(self.image)
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        self.stats_enabled = False
        self.stats_thread = None
        self.stats_interval = 1.0
        # init for quick menu
        self.disp_info = DisplayInfo(self.image.width, self.image.height, self.font, 6, 8)
        self.root_menu = Menu()
        self.menu_ptr = self.root_menu
        self.menu_on = False
        self.das_count = 0
        self.das_action = SwitchAction.PRESS_NOTHING
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(UP_CHANNEL, GPIO.IN)
        GPIO.setup(RIGHT_CHANNEL, GPIO.IN)
        GPIO.setup(LEFT_CHANNEL, GPIO.IN)
        GPIO.setup(DOWN_CHANNEL, GPIO.IN)
        GPIO.setup(CENTER_CHANNEL, GPIO.IN)
        GPIO.add_event_detect(UP_CHANNEL, GPIO.RISING, bouncetime=200)
        GPIO.add_event_detect(RIGHT_CHANNEL, GPIO.RISING, bouncetime=200)
        GPIO.add_event_detect(LEFT_CHANNEL, GPIO.RISING, bouncetime=200)
        GPIO.add_event_detect(DOWN_CHANNEL, GPIO.RISING, bouncetime=200)
        GPIO.add_event_detect(CENTER_CHANNEL, GPIO.RISING, bouncetime=200)
        self.ipc = IPC('/tmp/menu_socket')
        self.actions = {
            'reset_menu': self.reset_menu,
            'create_item': self.create_item,
            'update_value': self.update_value
        }
        self.enable_stats()
        
    def reset_menu(self, *args, uuid: Union[str, None] = None, **kwargs) -> None:
        ptr = self.root_menu.find(uuid)
        if ptr == None:
            self.root_menu = Menu()
            self.menu_ptr = self.root_menu
        elif isinstance(ptr, Menu):
            # make sure the menu_ptr is not inside the reset item set
            if ptr != self.menu_ptr and ptr.find(self.menu_ptr.uuid) != None:
                self.menu_ptr = ptr
            ptr.reset()

    def create_item(self, *args, create_type: str = 'item', root: Union[str, None] = None, **kwargs) -> None:
        root_ptr = self.root_menu.find(root)
        CREATE_TYPE = {'item': Item,
                       'menu': Menu,
                       'func': Function,
                       'var': Variable}
        if isinstance(root_ptr, Menu) and create_type in CREATE_TYPE:
            root_ptr.add(CREATE_TYPE[create_type](*args, root=root_ptr, **kwargs))

    def update_value(self, *args, uuid: Union[str, None] = None, value: Any = True, **kwargs) -> None:
        ptr = self.root_menu.find(uuid)
        if isinstance(ptr, Function):
            if value:
                #immediate return
                self.menu_ptr = self.menu_ptr.root
                ptr.reset()
            else:
                ptr.add_finish_return()
        elif isinstance(ptr, Variable):
            ptr.update_value(value)

    def _run_display_stats(self):
        while self.stats_enabled:
            packets = self.ipc.recv()
            for packet in packets:
                self.actions[packet.action](*packet.args, **packet.kwargs)
            if self.menu_on:
                self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
                action = SwitchAction.PRESS_NOTHING
                if GPIO.event_detected(UP_CHANNEL):
                    action = SwitchAction.PRESS_UP
                if GPIO.event_detected(RIGHT_CHANNEL):
                    action = SwitchAction.PRESS_RIGHT
                if GPIO.event_detected(LEFT_CHANNEL):
                    action = SwitchAction.PRESS_LEFT
                if GPIO.event_detected(DOWN_CHANNEL):
                    action = SwitchAction.PRESS_DOWN
                if GPIO.event_detected(CENTER_CHANNEL):
                    action = SwitchAction.PRESS_CENTER
                if action == SwitchAction.PRESS_NOTHING:
                    checked_action = SwitchAction.PRESS_NOTHING
                    if GPIO.input(UP_CHANNEL) == GPIO.HIGH:
                        checked_action = SwitchAction.PRESS_UP
                    elif  GPIO.input(DOWN_CHANNEL) == GPIO.HIGH:
                        checked_action = SwitchAction.PRESS_DOWN
                    elif GPIO.input(LEFT_CHANNEL) == GPIO.HIGH:
                        checked_action = SwitchAction.PRESS_LEFT
                    elif GPIO.input(RIGHT_CHANNEL) == GPIO.HIGH:
                        checked_action = SwitchAction.PRESS_RIGHT
                    if checked_action != self.das_action:
                        self.das_count = 0
                        self.das_action = checked_action
                    elif checked_action != SwitchAction.PRESS_NOTHING:
                        self.das_count += 1
                    if self.das_count > 5:
                        self.das_count = 6
                        action = self.das_action
                self.menu_ptr = self.menu_ptr.display(self.disp_info, self.draw, action, self.ipc)
                self.display.image(self.image)
                self.display.display()
                if self.menu_ptr == None:
                    self.menu_on = False
                    self.menu_ptr = self.root_menu
                time.sleep(0.05)
            else:
                self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)

                # set IP address
                top = -2
                if ip_address('eth0') is not None:
                    self.draw.text((4, top), 'IP: ' + str(ip_address('eth0')), font=self.font, fill=255)
                elif ip_address('wlan0') is not None:
                    self.draw.text((4, top), 'IP: ' + str(ip_address('wlan0')), font=self.font, fill=255)
                else:
                    self.draw.text((4, top), 'IP: not available')

                top = 6
                power_mode_str = power_mode()
                self.draw.text((4, top), 'MODE: ' + power_mode_str, font=self.font, fill=255)
                
                # set stats headers
                top = 14
                offset = 3 * 8
                headers = ['PWR', 'CPU', 'GPU', 'RAM', 'DSK']
                for i, header in enumerate(headers):
                    self.draw.text((i * offset + 4, top), header, font=self.font, fill=255)

                # set stats fields
                top = 22
                power_watts = '%.1f' % power_usage()
                gpu_percent = '%02d%%' % int(round(gpu_usage() * 100.0, 1))
                cpu_percent = '%02d%%' % int(round(cpu_usage() * 100.0, 1))
                ram_percent = '%02d%%' % int(round(memory_usage() * 100.0, 1))
                disk_percent = '%02d%%' % int(round(disk_usage() * 100.0, 1))
                
                entries = [power_watts, cpu_percent, gpu_percent, ram_percent, disk_percent]
                for i, entry in enumerate(entries):
                    self.draw.text((i * offset + 4, top), entry, font=self.font, fill=255)

                self.display.image(self.image)
                self.display.display()

                time.sleep(self.stats_interval)
                for i in range(int(self.stats_interval / 0.1)):
                    if GPIO.event_detected(CENTER_CHANNEL):
                        while GPIO.event_detected(CENTER_CHANNEL):
                            pass
                        while GPIO.event_detected(UP_CHANNEL):
                            pass
                        while GPIO.event_detected(RIGHT_CHANNEL):
                            pass
                        while GPIO.event_detected(LEFT_CHANNEL):
                            pass
                        while GPIO.event_detected(DOWN_CHANNEL):
                            pass
                        self.menu_on = True
                    time.sleep(0.1)

    def enable_stats(self):
        # start stats display thread
        if not self.stats_enabled:
            self.stats_enabled = True
            self.stats_thread = threading.Thread(target=self._run_display_stats)
            self.stats_thread.start()
        
    def disable_stats(self):
        self.stats_enabled = False
        if self.stats_thread is not None:
            self.stats_thread.join()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        self.display.image(self.image)
        self.display.display()

    def set_text(self, text):
        self.disable_stats()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        
        lines = text.split('\n')
        top = 2
        for line in lines:
            self.draw.text((4, top), line, font=self.font, fill=255)
            top += 10
        
        self.display.image(self.image)
        self.display.display()
        

app = Flask(__name__)


@app.route('/stats/on')
def enable_stats():
    global server
    server.enable_stats()
    return "stats enabled"

    
@app.route('/stats/off')
def disable_stats():
    global server
    server.disable_stats()
    return "stats disabled"


@app.route('/text/<text>')
def set_text(text):
    global server
    server.set_text(text)
    return 'set text: \n\n%s' % text


if __name__ == '__main__':
    server = DisplayServer()
    app.run(host='0.0.0.0', port='8000', debug=False)

