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
    def __init__(self, display_width, display_height, font, font_width, font_height):
        self.max_line = display_height // font_height
        self.line_height = font_height
        self.line_width = display_width
        self.font = font
        self.font_width = font_width

class Menu:
    def __init__(self, root=None, name="", uuid="base"):
        self.root = root
        self.name = name
        self.obj_list = ['return']
        self.select_idx = 0
        self.first_display_idx = 0
        self.uuid = uuid
    def get_display_info(self):
        return ">> " + self.name, ""
    def add(self, obj):
        self.obj_list.append(obj)
    def reset(self):
        self.obj_list = ['return']
    def display(self, disp_info: DisplayInfo, draw, action: SwitchAction, menu_connection):
        if action == SwitchAction.PRESS_CENTER:
            if self.obj_list[self.select_idx] == 'return':
                return self.root
            else:
                return self.obj_list[self.select_idx].display(disp_info, draw, SwitchAction.PRESS_NOTHING, menu_connection)
        elif action == SwitchAction.PRESS_UP:
            self.select_idx -= 1
        elif action == SwitchAction.PRESS_DOWN:
            self.select_idx += 1
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
            if obj == 'return':
                name, value = "<< Return", ""
            else:
                name, value = obj.get_display_info()
            if idx == self.select_idx:
                draw.rectangle((x, y+2, disp_info.line_width, y+disp_info.line_height+2), outline=255, fill=255)
                draw.text((x, y), name, font=disp_info.font, fill=0)
                value_str = str(value)
                if len(value_str):
                    x = disp_info.line_width - len(value_str)*disp_info.font_width
                    draw.text((x, y), value_str, font=disp_info.font, fill=0)
            else:
                draw.text((x, y), name, font=disp_info.font, fill=255)
                value_str = str(value)
                if len(value_str):
                    x = disp_info.line_width - len(value_str)*disp_info.font_width
                    draw.text((x, y), value_str, font=disp_info.font, fill=255)
        return self
            
        
class Variable:
    def __init__(self, root=None, name="", value=0, step=None, uuid=""):
        self.root = root
        self.name = name
        self.value = value
        self.step = step
        self.uuid = uuid
        if step:
            self.step_exponent = -decimal.Decimal(str(step)).as_tuple().exponent
        else:
            self.step_exponent = None
    def get_display_info(self):
        return self.name, self.value if self.value != None else ""
    def get(self):
        return self.value
    def set_value(self, value):
        self.value = value
    def display(self, disp_info: DisplayInfo, draw, action: SwitchAction, menu_connection):
        if action == SwitchAction.PRESS_CENTER:
            # Here should send the value out
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':self.value}
            packet_string = json.dumps(packet)
            data_out = packet_string.encode()
            packet_len = len(data_out)
            data_out = bytes([packet_len&0xFF, (packet_len>>8)&0xFF]) + data_out
            for conn in menu_connection:
                try:
                    conn["connection"].sendall(data_out)
                except:
                    pass #better process should be delete the conn
            self.root.display(disp_info, draw, SwitchAction.PRESS_NOTHING, menu_connection)
            return self.root
        elif self.step:
            if action == SwitchAction.PRESS_LEFT:
                self.value -= self.step
            elif action == SwitchAction.PRESS_RIGHT:
                self.value += self.step
            elif action == SwitchAction.PRESS_UP:
                self.value -= self.step*10
            elif action == SwitchAction.PRESS_DOWN:
                self.value += self.step*10
            self.value = round(self.value, self.step_exponent)
        elif action != SwitchAction.PRESS_NOTHING and type(self.value) == bool:
            self.value = not self.value
        x = (disp_info.line_width - len(self.name)*disp_info.font_width) // 2
        draw.text((x, 2), self.name, font=disp_info.font, fill=255)
        x = (disp_info.line_width - len("<<  "+str(self.value)+"  >>")*disp_info.font_width) // 2
        draw.text((x, 16), "<<  "+str(self.value)+"  >>",  font=disp_info.font, fill=255)
        return self

class Function(Menu):
    def __init__(self, root=None, name="", uuid=""):
        super().__init__(root=root, name=name, uuid=uuid)
        self.obj_list = []
        self.callback_running = False
    def get_display_info(self):
        return "[  " + self.name + "  ]", ""
    def add(self, obj):
        super().add(obj)
        self.select_idx = len(self.obj_list)-1
    def reset(self):
        self.callback_running = False
        self.obj_list = []
    def add_finish_return(self):
        self.obj_list.append('return')
        self.select_idx = len(self.obj_list)-1
    def display(self, disp_info: DisplayInfo, draw, action: SwitchAction, menu_connection):
        if not self.callback_running:
            self.callback_running = True
            packet = {'action':'value_update', 'uuid':self.uuid, 'value':'call'}
            packet_string = json.dumps(packet)
            data_out = packet_string.encode()
            packet_len = len(data_out)
            data_out = bytes([packet_len&0xFF, (packet_len>>8)&0xFF]) + data_out
            for conn in menu_connection:
                try:
                    conn["connection"].sendall(data_out)
                except:
                    pass #better process should be delete the conn
        if action == SwitchAction.PRESS_CENTER:
            if len(self.obj_list) and self.obj_list[self.select_idx] == 'return':
                self.reset()
                return self.root
        elif action == SwitchAction.PRESS_UP:
            self.select_idx -= 1
        elif action == SwitchAction.PRESS_DOWN:
            self.select_idx += 1
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
            if obj == 'return':
                name, value = "<< Return", ""
            else:
                name, value = obj.get_display_info()
            if idx == self.select_idx:
                draw.rectangle((x, y+2, disp_info.line_width, y+disp_info.line_height+2), outline=255, fill=255)
                draw.text((x, y), name, font=disp_info.font, fill=0)
                value_str = str(value)
                if len(value_str):
                    x = disp_info.line_width - len(value_str)*disp_info.font_width
                    draw.text((x, y), value_str, font=disp_info.font, fill=0)
            else:
                draw.text((x, y), name, font=disp_info.font, fill=255)
                value_str = str(value)
                if len(value_str):
                    x = disp_info.line_width - len(value_str)*disp_info.font_width
                    draw.text((x, y), value_str, font=disp_info.font, fill=255)
        return self
    
    
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
        self.menu_temp_ptr = None
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
        self.menu_address = '/tmp/menu_socket'
        try:
            os.remove(self.menu_address)
        except OSError:
            pass
        self.menu_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.menu_socket.bind(self.menu_address)
        os.chmod(self.menu_address, 0o777)
        self.menu_socket.listen(1)
        self.menu_socket.setblocking(False)
        self.menu_connection = []
        self.enable_stats()
        
    def _run_display_stats(self):
        while self.stats_enabled:
            try:
                conn, addr = self.menu_socket.accept()
                conn.setblocking(False)
                self.menu_connection.append({"connection": conn, "recv_data": bytes([])})
            except BlockingIOError:
                pass
            for conn in self.menu_connection:
                try:
                    data = conn["connection"].recv(1024)
                    if data:
                        # process data
                        conn["recv_data"] += data
                        # first two byte is the packet length, big endian, after that is json string
                        while len(conn['recv_data']):
                            recv_data = conn['recv_data']
                            if len(recv_data) >= 2:
                                packet_length = recv_data[0] | (recv_data[1]<<8)
                                if len(recv_data)-2 >= packet_length:
                                    packet = recv_data[2:packet_length+2]
                                    conn['recv_data'] = conn['recv_data'][packet_length+2:] #remove processed data
                                    packet = json.loads(packet.decode())
                                    if packet['action'] == 'reset_menu':
                                        if 'uuid' in packet:
                                            ptr = self.find_menu(self.root_menu, packet['uuid'])
                                            if ptr != None:
                                                ptr.reset()
                                        else:
                                            self.root_menu = Menu()
                                            self.menu_ptr = self.root_menu
                                    elif packet['action'] == 'create_menu':
                                        self.menu_temp_ptr = self.find_menu(self.root_menu, packet['arg']['root'])
                                        packet['arg']['root'] = self.menu_temp_ptr
                                        self.menu_temp_ptr.add(Menu(**packet['arg']))
                                    elif packet['action'] == 'create_func':
                                        self.menu_temp_ptr = self.find_menu(self.root_menu, packet['arg']['root'])
                                        packet['arg']['root'] = self.menu_temp_ptr
                                        self.menu_temp_ptr.add(Function(**packet['arg']))
                                    elif packet['action'] == 'create_var':
                                        self.menu_temp_ptr = self.find_menu(self.root_menu, packet['arg']['root'])
                                        packet['arg']['root'] = self.menu_temp_ptr
                                        self.menu_temp_ptr.add(Variable(**packet['arg']))
                                    elif packet['action'] == 'value_update':
                                        ptr = self.find_menu(self.root_menu, packet['uuid'])
                                        if ptr != None:
                                            if isinstance(ptr, Function):
                                                if packet['value']:
                                                    #immediate return
                                                    self.menu_ptr = self.menu_ptr.root
                                                    ptr.reset()
                                                else:
                                                    ptr.add_finish_return()
                                            else:
                                                ptr.set_value(packet['value'])
                                else:
                                    break
                            else:
                                break
                    else:
                        # client connection closed
                        self.menu_connection.remove(conn)            
                except BlockingIOError:
                    # no client send data
                    pass
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
                self.menu_ptr = self.menu_ptr.display(self.disp_info, self.draw, action, self.menu_connection)
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
            
    def find_menu(self, root, uuid):
        if isinstance(root, Menu) or isinstance(root, Variable):
            if root.uuid == uuid:
                return root
        if isinstance(root, Menu):
            for o in root.obj_list:
                res = self.find_menu(o, uuid)
                if res:
                    return res
        return None

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
        

server = DisplayServer()
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
    app.run(host='0.0.0.0', port='8000', debug=False)

