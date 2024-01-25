from jetcard.menu import Menu, FloatVariable, IntVariable, BoolVariable, Function, reset_menu
from typing import Union
import time

def callback1(func: Function) -> Union[bool, None]:
    func.callback_print("Calling callback1")
    time.sleep(0.3)
    for i in range(10):
        func.callback_print("printing line {num}".format(num=i))
        time.sleep(0.3)
    return True     # return immediately

def callback2(func: Function) -> Union[bool, None]:
    func.callback_print("Calling callback2")
    time.sleep(0.3)
    for i in range(10):
        func.callback_print("printing line {num}".format(num=i))
        time.sleep(0.3)
    return False    # not immediately return, return None and no return did the same thing

def inc_a(func: Function) -> Union[bool, None]:
    func.callback_print("increasing variable a")
    time.sleep(0.5)
    ea.set_value(ea.get_value()+0.01)
    return True
def dec_a(func: Function) -> Union[bool, None]:
    func.callback_print("decreasing variable a")
    time.sleep(0.5)
    ea.set_value(ea.get_value()-0.01)
    return True

reset_menu()

a = FloatVariable(description='a')
b = IntVariable(description='b')
c = BoolVariable(description='c')
d = Function(description="func d", callback_func=callback1)
e = Menu(description='e menu')
ea = FloatVariable(description='a', root=e, value=0.1, step=0.001)
eb = IntVariable(description='b', root=e, value=1)
ec = BoolVariable(description='c', root=e, value=False)
ed = Function(description="func d", callback_func=callback2, root=e)
einc = Function(description="inc a", callback_func=inc_a, root=e)
edec = Function(description="dec a", callback_func=dec_a, root=e)

import time
while True:
    pass
