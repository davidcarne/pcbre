import enum
import operator
from enum import Enum


class SIDE(Enum):
    Top = 0
    Bottom = 1


class OnSide(Enum):
    One = 0
    Both = 1


class IntersectionClass(enum.Enum):
    NONE = 0
    TRACE = 1
    VIA = 2
    PAD = 3
    POLYGON = 4
    # Object that only intersects at the two instantaneous points at each end
    VIRTUAL_LINE = 5


class _TFF(int):
    def __new__(cls, val: int) -> "_TFF":
        return int.__new__(cls, val)

    def __repr__(self) -> str:
        a = []
        ks = [(k, v) for k, v in
              [(k, getattr(TFF, k)) for k in dir(TFF)]
              if isinstance(v, _TFF)]

        for k, v in sorted(ks, key=operator.itemgetter(1)):
            if self & v:
                a.append(k)
        return " | ".join("TFF_%s" % k for k in a)

    def __or__(self, other: int) -> "_TFF":
        return _TFF(int.__or__(self, other))

    def __add__(self, other: int) -> "_TFF":
        raise NotImplementedError

    def __sub__(self, other: int) -> "_TFF":
        raise NotImplementedError


class TFF:
    HAS_NET = _TFF(1)
    HAS_GEOM = _TFF(2)
    HAS_INST_INFO = _TFF(4)
