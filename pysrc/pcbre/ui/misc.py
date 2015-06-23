__author__ = 'davidc'
import numpy
from PySide import QtCore, QtGui

KEEP = None
def QImage_from_numpy(arr):
    shape = arr.shape

    if len(shape) == 2:
        channels = 1
    elif len(shape) == 3:
        channels = shape[3]
        shape = shape[:2]
    else:
        raise ValueError("Shape of input array is whacko")

    assert channels in [1,3,4]
    assert arr.dtype == numpy.uint8

    if channels != 4:
        new_arr = numpy.zeros(tuple(shape) + (4,), dtype = numpy.uint8)

        if channels > 1:
            new_arr[:,:,:channels] = arr
        else:
            new_arr[:,:,:3] = arr[:,:, numpy.newaxis]

        new_arr[:,:,3].fill(0xFF)

        arr = new_arr

    img = QtGui.QImage(arr.data, shape[1], shape[0], QtGui.QImage.Format_ARGB32)
    img.array_holder = arr

    return img






