import ctypes

c_float_p = ctypes.POINTER(ctypes.c_float)

dll = ctypes.CDLL("libGL.so")
glUniformMatrix3fv = dll.glUniformMatrix3fv
glUniformMatrix3fv.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.c_bool, c_float_p]

glUniform4fv = dll.glUniform4fv
glUniform4fv.argtypes = [ctypes.c_long, ctypes.c_long, c_float_p]

glDrawArrays = dll.glDrawArrays
glDrawArrays.argtypes = [ctypes.c_ulong, ctypes.c_long, ctypes.c_long]

glVertexAttribPointer = dll.glVertexAttribPointer
glVertexAttribPointer.argtypes = [
    ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong, ctypes.c_void_p]

glUseProgram = dll.glUseProgram
glUseProgram.argtypes = [ctypes.c_ulong]


glBindBuffer = dll.glBindBuffer
glBindBuffer.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
