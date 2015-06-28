import os.path
import ctypes
import pkg_resources
import sysconfig

# This terrible hack seems to be able to find the compiled acceleration library
extension = sysconfig.get_config_var('SO')
dllname = pkg_resources.resource_filename('pcbre.accel', '_edtaa3' + extension)

dll = ctypes.CDLL(dllname)

c_double_p = ctypes.POINTER(ctypes.c_double)
c_short_p = ctypes.POINTER(ctypes.c_short)

compute_gradient = dll.computegradient
compute_gradient.argtypes = [c_double_p, ctypes.c_int, ctypes.c_int, c_double_p, c_double_p]
compute_gradient.restype = ctypes.c_void_p

edtaa3 = dll.edtaa3
edtaa3.argtypes = [c_double_p, c_double_p, c_double_p, ctypes.c_int, ctypes.c_int, c_short_p, c_short_p, c_double_p]
