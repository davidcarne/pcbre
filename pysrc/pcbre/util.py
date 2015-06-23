def np_print_regular(x, caption=None):
    border ="-" * (8 * x.shape[1] + 4) 
    if caption:
        print()
        print("%s:"%caption)
        print(border)
    for row in x:
        print("| %s |" % "".join("%7.3f " % f for f in row))
    if caption:
        print(border)


def float_or_None(s):
    if s == "":
        return None
    return float(s)


import time

class Timer:
    def __enter__(self):
        self.start = time.clock()
        return self

    def __exit__(self, *args):
        self.end = time.clock()
        self.interval = self.end - self.start