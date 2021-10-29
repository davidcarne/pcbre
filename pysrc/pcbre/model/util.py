from typing import TypeVar, Generic, Set, Iterator, List
T = TypeVar('T')


class ImmutableSetProxy(Generic[T]):
    """Proxy class for a set that is 'immutable'; intended to prevent accidental misuse of an internal datastructure"""
    def __init__(self, parent: Set[T]):
        self.parent = parent

    def __iter__(self) -> Iterator[T]:
        return self.parent.__iter__()

    def __len__(self) -> int:
        return self.parent.__len__()


class ImmutableListProxy(Generic[T]):
    """Proxy class for a list that is 'immutable'; intended to prevent accidental misuse of an internal datastructure"""
    def __init__(self, parent: List[T]):
        self.parent = parent

    def __getitem__(self, item: int) -> T:
        return self.parent.__getitem__(item)

    def __iter__(self) -> Iterator[T]:
        return self.parent.__iter__()

    def __len__(self) -> int:
        return self.parent.__len__()

    def index(self, k: T) -> int:
        return self.parent.index(k)
