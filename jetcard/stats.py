# Copyright (c) 2017 Adafruit Industries
# Author: Tony DiCola & James DeVito
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import time

import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from .utils import get_ip_address

import subprocess

# 128x32 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_32(rst=None, i2c_bus=1, gpio=1) # setting gpio to 1 is hack to avoid platform detection

# Initialize library.
while True:
    try:
        # Try to connect to the OLED display module via I2C.
        disp.begin()
    except OSError as err:
        print("OS error: {0}".format(err))
        time.sleep(10)
    else:
        break

# Clear display.
disp.clear()
disp.display()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load default font.
font = ImageFont.load_default()

# quick menu init
import Jetson.GPIO as GPIO
import os
import socket
import decimal
import json
NUM_LINE_IN_DISPLAY = 4
LINE_HEIGHT = 8
LINE_WIDTH = width
FONT_WIDTH = 6
UP_CHANNEL = 13
RIGHT_CHANNEL = 15
LEFT_CHANNEL = 16
DOWN_CHANNEL = 18
CENTER_CHANNEL = 19
MENU_IDLE = 0
MENU_ACTIVE = 1
menu_state = MENU_IDLE
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
menu_address = '/tmp/menu_socket'
try:
    os.remove(menu_address)
except OSError:
    pass
menu_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
menu_socket.bind(menu_address)
menu_socket.listen(1)
menu_socket.setblocking(False)
menu_connection = []
PRESS_NOTHING = 0
PRESS_CENTER = 1
PRESS_UP = 2
PRESS_DOWN = 3
PRESS_LEFT = 4
PRESS_RIGHT = 5
das_count = 0
das_action = PRESS_NOTHING
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
    def reset(self, obj):
        self.obj_list = ['return']
    def display(self, draw, action):
        if action == PRESS_CENTER:
            if self.obj_list[self.select_idx] == 'return':
                return self.root
            else:
                return self.obj_list[self.select_idx].display(draw, PRESS_NOTHING)
        elif action == PRESS_UP:
            self.select_idx -= 1
        elif action == PRESS_DOWN:
            self.select_idx += 1
        if self.select_idx < 0:
            self.select_idx = len(self.obj_list)-1
            self.first_display_idx = max(len(self.obj_list) - NUM_LINE_IN_DISPLAY, 0)
        elif self.select_idx >= len(self.obj_list):
            self.select_idx = 0
            self.first_display_idx = 0
        elif self.select_idx < self.first_display_idx:
            self.first_display_idx = self.select_idx
        elif self.select_idx == self.first_display_idx + NUM_LINE_IN_DISPLAY:
            self.first_display_idx += 1
        for i in range(NUM_LINE_IN_DISPLAY):
            idx = self.first_display_idx + i
            if idx == len(self.obj_list):
                break
            x = 0
            y = LINE_HEIGHT*i-2
            obj = self.obj_list[idx]
            if obj == 'return':
                name, value = "<< Return", ""
            else:
                name, value = obj.get_display_info()
            if idx == self.select_idx:
                draw.rectangle((x,y+2,LINE_WIDTH,y+LINE_HEIGHT+2), outline=255, fill=255)
                draw.text((x, y), name,  font=font, fill=0)
                value_str = str(value)
                if len(value_str):
                    x = LINE_WIDTH - len(value_str)*FONT_WIDTH
                    draw.text((x, y), value_str, font=font, fill=0)
            else:
                draw.text((x, y), name,  font=font, fill=255)
                value_str = str(value)
                if len(value_str):
                    x = LINE_WIDTH - len(value_str)*FONT_WIDTH
                    draw.text((x, y), value_str, font=font, fill=255)
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
        return self.name, self.value
    def get(self):
        return self.value
    def set_value(self, value):
        self.value = value
    def display(self, draw, action):
        global menu_connection
        if action == PRESS_CENTER:
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
            self.root.display(draw, PRESS_NOTHING)
            return self.root
        elif action == PRESS_LEFT:
            if self.step:
                self.value -= self.step
        elif action == PRESS_RIGHT:
            if self.step:
                self.value += self.step
        elif action == PRESS_UP:
            if self.step:
                self.value -= self.step*10
        elif action == PRESS_DOWN:
            if self.step:
                self.value += self.step*10
        self.value = round(self.value, self.step_exponent)
        x = (LINE_WIDTH - len(self.name)*FONT_WIDTH) // 2
        draw.text((x, 2), self.name,  font=font, fill=255)
        x = (LINE_WIDTH - len("<<  "+str(self.value)+"  >>")*FONT_WIDTH) // 2
        draw.text((x, 16), "<<  "+str(self.value)+"  >>",  font=font, fill=255)
        return self
    
root_menu = Menu()
menu_ptr = root_menu
menu_temp_ptr = None
menu_temp_obj_arg = {}
menu_temp_obj_arg_key = None
menu_update_ptr = None
def find_menu(root, uuid):
    if type(root) == Menu or type(root) == Variable:
        if root.uuid == uuid:
            return root
    if type(root) == Menu:
        for o in root.obj_list:
            res = find_menu(o, uuid)
            if res:
                return res
    return None
    
while True:
    try:
        conn, addr = menu_socket.accept()
        conn.setblocking(False)
        menu_connection.append({"connection": conn, "recv_data": bytes([])})
    except BlockingIOError:
        pass
    for conn in menu_connection:
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
                                root_menu = Menu()
                                menu_ptr = root_menu
                            elif packet['action'] == 'create_menu':
                                menu_temp_ptr = find_menu(root_menu, packet['arg']['root'])
                                packet['arg']['root'] = menu_temp_ptr
                                menu_temp_ptr.add(Menu(**packet['arg']))
                            elif packet['action'] == 'create_var':
                                menu_temp_ptr = find_menu(root_menu, packet['arg']['root'])
                                packet['arg']['root'] = menu_temp_ptr
                                menu_temp_ptr.add(Variable(**packet['arg']))
                            elif packet['action'] == 'value_update':
                                find_menu(root_menu, packet['uuid']).set_value(packet['value'])
                        else:
                            break
                    else:
                        break
            else:
                # client connection closed
                menu_connection.remove(conn)            
        except BlockingIOError:
            # no client send data
            pass
    if menu_state == MENU_IDLE:
        # Draw a black filled box to clear the image.
        draw.rectangle((0,0,width,height), outline=0, fill=0)
    
        # Shell scripts for system monitoring from here : https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
        cmd = "top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'"
        CPU = subprocess.check_output(cmd, shell = True )
        cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
        MemUsage = subprocess.check_output(cmd, shell = True )
        cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
        Disk = subprocess.check_output(cmd, shell = True )
    
        # Write two lines of text.
    
        draw.text((x, top),       "eth0: " + str(get_ip_address('eth0')),  font=font, fill=255)
        draw.text((x, top+8),     "wlan0: " + str(get_ip_address('wlan0')), font=font, fill=255)
        draw.text((x, top+16),    str(MemUsage.decode('utf-8')),  font=font, fill=255)
        draw.text((x, top+25),    str(Disk.decode('utf-8')),  font=font, fill=255)
    
        # Display image.
        disp.image(image)
        disp.display()
        for i in range(10):
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
                menu_state = MENU_ACTIVE
            time.sleep(0.1)
    else:
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        action = PRESS_NOTHING
        if GPIO.event_detected(UP_CHANNEL):
            action = PRESS_UP
        if GPIO.event_detected(RIGHT_CHANNEL):
            action = PRESS_RIGHT
        if GPIO.event_detected(LEFT_CHANNEL):
            action = PRESS_LEFT
        if GPIO.event_detected(DOWN_CHANNEL):
            action = PRESS_DOWN
        if GPIO.event_detected(CENTER_CHANNEL):
            action = PRESS_CENTER
        if action == PRESS_NOTHING:
            checked_action = PRESS_NOTHING
            if GPIO.input(UP_CHANNEL) == GPIO.HIGH:
                checked_action = PRESS_UP
            elif  GPIO.input(DOWN_CHANNEL) == GPIO.HIGH:
                checked_action = PRESS_DOWN
            elif GPIO.input(LEFT_CHANNEL) == GPIO.HIGH:
                checked_action = PRESS_LEFT
            elif GPIO.input(RIGHT_CHANNEL) == GPIO.HIGH:
                checked_action = PRESS_RIGHT
            if checked_action != das_action:
                das_count = 0
                das_action = checked_action
            elif checked_action != PRESS_NOTHING:
                das_count += 1
            if das_count > 5:
                das_count = 6
                action = das_action
        menu_ptr = menu_ptr.display(draw, action)
        disp.image(image)
        disp.display()
        if menu_ptr == None:
            menu_state = MENU_IDLE
            menu_ptr = root_menu
        time.sleep(0.05)
