import ipywidgets
import socket
import threading
import uuid
import time
import json
from traitlets import HasTraits, observe
import jetcard.menu
from jetcard.menu import FloatVariable, IntVariable, BoolVariable, reset_menu

def reset_menu():
    jetcard.menu.reset_menu()

class Menu(jetcard.menu.Menu):
    def __init__(self, root=None, description="", *args, **kwargs):
        super().__init__(root=root, description=description, *args, **kwargs)

class FloatSlider(FloatVariable, ipywidgets.FloatSlider):
    def __init__(self, root=None, *args, **kwargs):
        self.update_from_menu = False
        super(FloatVariable, self).__init__(root=root, *args, **kwargs)
        super(ipywidgets.FloatSlider, self).__init__(root=root, *args, **kwargs)
            
    # used by OLEDMenu class only
    def update(self, value):
        super().update(value)
        self.update_from_menu = True
        self.value = self._value
        self.update_from_menu = False
        
    @observe('value')
    def value_change(self, change):
        if not self.update_from_menu:
            self.set_value(change['new'])
            
class IntSlider(IntVariable, ipywidgets.IntSlider):
    def __init__(self, root=None, *args, **kwargs):
        self.update_from_menu = False
        super(IntVariable, self).__init__(*args, **kwargs)
        super(ipywidgets.IntSlider, self).__init__(root=root, *args, **kwargs)
        
    # used by OLEDMenu class only
    def update(self, value):
        super().update(value)
        self.update_from_menu = True
        self.value = self._value
        self.update_from_menu = False
        
    @observe('value')
    def value_change(self, change):
        if not self.update_from_menu:
            self.set_value(change['new'])

# class ToggleButton(ipywidgets.ToggleButton):
#     def __init__(self, root=None, **arg):
#         global oled_menu
#         super().__init__(**arg)
#         self.root = root
