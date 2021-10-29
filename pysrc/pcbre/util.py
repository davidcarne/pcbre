from typing import TYPE_CHECKING, Optional, Any
import time

if TYPE_CHECKING:
    import numpy.typing as npt

def np_print_regular(x: 'npt.NDArray[Any]', caption: Optional[str]=None) -> None:
    border ="-" * (8 * x.shape[1] + 4) 
    if caption:
        print()
        print("%s:"%caption)
        print(border)
    for row in x:
        print("| %s |" % "".join("%7.3f " % f for f in row))
    if caption:
        print(border)


def float_or_None(s: str) -> Optional[float]:
    if s == "":
        return None
    return float(s)


class Timer:
    def __init__(self) -> None:
        self.interval : float= 0

    def __enter__(self) -> 'Timer':
        self.start = time.time()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end = time.time()
        self.interval = self.end - self.start
