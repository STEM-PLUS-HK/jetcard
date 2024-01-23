import ipywidgets
import socket
import threading
import uuid
import time
import json
from traitlets import HasTraits, observe
import jetcard.menu
from jetcard.menu import FloatVariable, IntVariable, BoolVariable, Function, reset_menu

def reset_menu():
    jetcard.menu.reset_menu()

class Menu(jetcard.menu.Menu):
    def __init__(self, *args, root=None, description="", **kwargs):
        super().__init__(*args, root=root, description=description, **kwargs)

class FloatSlider(FloatVariable, ipywidgets.FloatSlider):
    def __init__(self, *args, root=None, **kwargs):
        self.update_from_menu = False
        FloatVariable.__init__(self, *args, root=root, **kwargs)
        ipywidgets.FloatSlider.__init__(self, *args, root=root, **kwargs)
            
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
    def __init__(self, *args, root=None, **kwargs):
        self.update_from_menu = False
        IntVariable.__init__(self, *args, root=root, **kwargs)
        ipywidgets.IntSlider.__init__(self, *args, root=root, **kwargs)
        
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

class Button(Function, ipywidgets.Button):
    def __init__(self, *args, root=None, **kwargs):
        Function.__init__(self, self.gen_menu_callback(), *args, root=root, **kwargs)
        ipywidgets.Button.__init__(self, *args, root=root, **kwargs)
        self.callback_list = []
    
    def gen_menu_callback(self):
        def menu_callback(func_obj):
            print(self.callback_list)
            for cb in self.callback_list:
                cb(func_obj, None)
            return True
        return menu_callback

    def gen_widget_callback(self, callback):
        def widget_callback(b):
            return callback(None, b)
        return widget_callback

    def on_click(self, callback, remove=False):
        '''
        callback(func_obj, b)
        '''
        if remove:
            self.callback_list.remove(callback)
        else:
            self.callback_list.append(callback)
        super().on_click(callback=self.gen_widget_callback(callback), remove=remove)
