import os.path
import ctypes
from .find_so import find_so
dll = ctypes.CDLL(find_so("_edtaa3"))

c_double_p = ctypes.POINTER(ctypes.c_double)
c_short_p = ctypes.POINTER(ctypes.c_short)

compute_gradient = dll.computegradient
compute_gradient.argtypes = [c_double_p, ctypes.c_int, ctypes.c_int, c_double_p, c_double_p]
compute_gradient.restype = ctypes.c_void_p

edtaa3 = dll.edtaa3
edtaa3.argtypes = [c_double_p, c_double_p, c_double_p, ctypes.c_int, ctypes.c_int, c_short_p, c_short_p, c_double_p]
