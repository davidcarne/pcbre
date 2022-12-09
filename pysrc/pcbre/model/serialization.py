import enum
import typing
import secrets

from typing import Set

SERIALIZATION_VERSION = 0x0001

# When we serialize a project to disk, we need to reference one object from another,
# for example, a Net from geometry that is connected to that Net. We could generate
# identifiers at serialization time; but that would lead to changes that would disrupt
# version control.
#
# PCBRE internally assigns a unique object ID to objects that are referenced during
# serialization time. The persistent ID registry exists to ensure that we never
# generate a duplicate ID; or reuse an ID from a recently deleted and recreated object
#
# The registry intentionally does not track an associated python object. A particular
# logical object may be represented by different python objects over time (for example
# if an object is modified by replacing it with an updated object and saving the old in
# an undo stack)

CLASS_BITS = 6
CLASS_MASK = (1 << CLASS_BITS) - 1

IDENT_BITS = 26
IDENT_MAX = (1 << IDENT_BITS)
IDENT_MASK = IDENT_MAX - 1


class PersistentIDClass(enum.Enum):
    NoClass = 0
    Net = 1
    Layer = 2
    ViaPair = 3
    ImageLayer = 4
    KeyPoint = 5


class PersistentID:
    __slots__ = ["__numeric_value"]
    __numeric_value: int

    def __init__(self, id_class: PersistentIDClass, value: int) -> None:
        assert 0 <= value < (1 << IDENT_BITS)

        id_class_int = typing.cast(int, id_class.value)

        self.__numeric_value = id_class_int << IDENT_BITS | value

    @property
    def id_class(self) -> PersistentIDClass:
        return PersistentIDClass(self.__numeric_value >> IDENT_BITS)

    @property
    def id_value(self) -> int:
        return self.__numeric_value & IDENT_MASK

    @property
    def as_uint32(self) -> int:
        return self.__numeric_value

    def __hash__(self):
        return self.__numeric_value

    def __lt__(self, other):
        return self.__numeric_value < other.__numeric_value

    def __eq__(self, other: 'PersistentID') -> bool:
        return self.__numeric_value == other.__numeric_value


class PersistentIDRegistry:
    def __init__(self) -> None:
        self.__known_ids: Set['PersistentID'] = set()

    def clone(self) -> 'PersistentIDRegistry':
        new_reg = PersistentIDRegistry()
        new_reg.__known_ids = set(self.__known_ids)
        return new_reg

    @staticmethod
    def __decode_uint32(value: int) -> PersistentID:
        if not (0 <= value < (1 << (IDENT_BITS + CLASS_BITS))):
            raise ValueError("Persistent ID value %d is out of range" % value)

        id_class_bits = value >> IDENT_BITS
        value_bits = value & IDENT_MASK

        id_class = PersistentIDClass(id_class_bits)

        return PersistentID(id_class, value_bits)

    def __add(self, existing_id: 'PersistentID') -> None:
        if existing_id in self.__known_ids:
            raise ValueError("Persistent ID %s is already known" % existing_id)

        self.__known_ids.add(existing_id)

    def decode_add_from_uint32(self, value: int) -> PersistentID:
        v = self.__decode_uint32(value)
        self.__add(v)
        return v

    def decode_check_from_uint32(self, value: int) -> PersistentID:
        v = self.__decode_uint32(value)
        if v not in self.__known_ids:
            raise KeyError("ID %s is not known" % v)
        return v

    def generate(self, id_class: PersistentIDClass) -> PersistentID:
        for i in range(100):
            proposed_id = secrets.randbits(IDENT_BITS)
            proposed_ident = PersistentID(id_class, proposed_id)
            if proposed_ident not in self.__known_ids:
                self.__add(proposed_ident)
                return proposed_ident

        raise RuntimeError("Unable to generate a random ID for new object")
