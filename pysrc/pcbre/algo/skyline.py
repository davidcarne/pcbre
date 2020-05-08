"""The skyline algorithm is a clean python implementation of the skyline best fit bin packing algorithm.
(See: http://clb.demon.fi/files/RectangleBinPack.pdf pp 25). It is used in pcbre for packing rectangular sprites into
textures. An example usage is text-sprite generation"""

import math
import itertools
import operator


__author__ = 'davidc'


class _SkyLineNode(object):
    """ A set of skyline nodes describe the skyline. They are organized in a singly linked list.
    Each node has a coordinate (left, height) that describes the upper-left corner edge of a skyline block.
    The width of the block (which continues at 'height') is implicit to either the 'left' of the next block, or to the
    width of the area on which the skyline is being run.
    """
    def __init__(self, left=0, height=0):
        self.left = left
        self.height = height

        self.next = None

    def __repr__(self):
        return "<node: %d,%d>" % (self.left, self.height)


def print_skyline(s):
    return ", ".join("%d,%d" % (s.left, s.height) for s in _node_iter(s))


class _StartHeight(object):
    def __init__(self, startnode, head=False):
        self.height = startnode.height
        self.node = startnode

        self.wasted_width = -1

        self.head = True
        self.reset()
        self.head = head

    def reset(self):
        assert self.head
        self.prev = self
        self.next = self

    def unlink(self):
        assert not self.head
        self.prev.next = self.next
        self.next.prev = self.prev

        self.prev = self
        self.next = self

    def append(self, node):
        node.prev = self
        node.next = self.next

        self.next.prev = node
        self.next = node

    def __repr__(self):
        if self.head:
            nodes = itertools.takewhile(lambda x: x != self, _node_iter(self.next))
            return ", ".join("%s height: %d fw:%d" % (s.node, s.height, s.wasted_width) for s in nodes)
        else:
            return "<%s height: %d fw:%d>" % (self.node, self.height, self.wasted_width)


def _node_iter(node):
    while node is not None:
        yield node
        node = node.next


class SkyLine(object):
    """The SkyLine class represents a mutable 'SkyLine' in area (width, height). Initially, the skyline is zero-height.
    The 'pack' and 'pack_multiple' functions may be used to allocate rectangular areas, and update the skyline.

    The SkyLine class itself does not directly manage any
    """
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.first = _SkyLineNode()

    def first_iter(self):
        """return an iterator that walks the nodes from left to right"""
        return _node_iter(self.first)

    def width(self, node):
        return self.next_left(node) - node.width

    def next_left(self, node):
        if node.next is None:
            return self.width

        return node.next.left

    def merge(self):
        node = self.first

        for node in self.first_iter():
            for next_node in _node_iter(node.next):
                if next_node.height != node.height:
                    break
                node.next = next_node.next

    def split(self, node, splitpoint, height):
        assert splitpoint > node.left
        assert splitpoint <= self.width
        assert height > node.height

        last_height = node.height
        node.height = height

        # If the splitpoint is at the RHS of the packing bin
        # just shortcut out
        if splitpoint == self.width:
            node.next = None
            return

        # walk the nodes ahead
        for next in _node_iter(node.next):

            # If one of the nodes ahead has left == our splitpoint
            # Then we just adopt the node as our next
            if next.left == splitpoint:
                node.next = next
                self.merge()
                return

            # Else if the node ahead has left > our split point
            # we need to insert a node to split the difference
            elif next.left > splitpoint:
                if next.height == last_height:
                    print(next.height, last_height)
                    print(splitpoint, height)
                    print(print_skyline(node))
                    # This case should be impossible
                    # if it occurs, something is wrong with the skyline
                    assert False
                    next.left = splitpoint
                    node.next = next
                    return
                else:
                    newnode = _SkyLineNode(splitpoint, last_height)
                    newnode.next = next
                    node.next = newnode
                    # TODO: This merge shouldn't be needed
                    self.merge()
                    return
            last_height = next.height

        newnode = _SkyLineNode(splitpoint, last_height)
        newnode.next = None
        node.next = newnode
        self.merge()

    def find(self, width, height):
        # We use a left-to-right sweep that tracks the viable
        # candidate start points as seen looking back to the left

        candidates = []

        fake = _SkyLineNode(self.width, self.height)
        # left-to-right pass
        s_h_list = _StartHeight(fake, True)

        # List with fake node at the end for end-of-list
        # Fake node will always fail-to-pack because
        for node in itertools.chain(self.first_iter(), [fake]):

            while node.height > s_h_list.prev.height:
                # If the packing rect doesn't fit inside
                if node.left - s_h_list.prev.node.left < width:
                    s_h_list.prev.height = node.height

                    if s_h_list.prev.height >= s_h_list.prev.prev.height:
                        s_h_list.prev.unlink()
                else:
                    # Packing rect fits inside:
                    s_h_list.prev.wasted_width = node.left - s_h_list.prev.node.left - width

                    assert s_h_list.prev != s_h_list

                    # If we've bumped the height to the point it no longer fits, discard it
                    if height + s_h_list.prev.height <= self.height:
                        candidates.append(s_h_list.prev)

                    # This candidate will be strictly better than any others in flight
                    s_h_list.reset()

            # Otherwise, start a new candidate
            if node.height < s_h_list.prev.height:
                s_h_list.prev.append(_StartHeight(node))

        if len(candidates):
            return sorted(candidates, key=operator.attrgetter("height", "wasted_width"))[0]

        return None

    def pack(self, width, height):
        width = math.ceil(width)
        height = math.ceil(height)
        cand = self.find(width, height)

        if cand is None:
            return None

        self.split(cand.node, cand.node.left + width, cand.height + height)

        return cand.node.left, cand.height

    def pack_multiple(self, tuples):
        packl = list(enumerate(tuples))

        results = [None] * len(tuples)

        while packl:
            scores = []
            for n_l, (n_initial, (width, height)) in enumerate(packl):
                scores.append((n_l, height, self.find(width, height)))

            win_index, glyph_height, win_cand = min(scores, key=lambda x: (x[2].height + x[1], x[2].wasted_width))
            width, height = packl[win_index][1]

            self.split(win_cand.node, win_cand.node.left + width, win_cand.height + height)

            results[packl[win_index][0]] = win_cand.node.left, win_cand.height

            del packl[win_index]

        return results
