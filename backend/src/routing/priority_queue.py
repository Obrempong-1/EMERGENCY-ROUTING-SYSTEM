"""Binary min-heap with decrease-key support."""

from __future__ import annotations

from typing import Hashable

class MinHeap:
    __slots__ = ("_keys", "_items", "_pos")

    def __init__(self) -> None:
        self._keys: list[float] = []
        self._items: list[Hashable] = []
        self._pos: dict[Hashable, int] = {}

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __contains__(self, item: Hashable) -> bool:
        return item in self._pos

    def key_of(self, item: Hashable) -> float:
        return self._keys[self._pos[item]]

    def push(self, item: Hashable, key: float) -> None:
        if item in self._pos:
            raise KeyError(f"{item!r} is already in the heap; use decrease_key")
        self._items.append(item)
        self._keys.append(key)
        index = len(self._items) - 1
        self._pos[item] = index
        self._sift_up(index)

    def decrease_key(self, item: Hashable, new_key: float) -> None:
        index = self._pos[item]
        if new_key > self._keys[index]:
            raise ValueError("decrease_key cannot raise a priority")
        self._keys[index] = new_key
        self._sift_up(index)

    def push_or_decrease(self, item: Hashable, key: float) -> bool:
        """Insert or improve `item`; returns whether the heap changed."""
        index = self._pos.get(item)
        if index is None:
            self.push(item, key)
            return True
        if key < self._keys[index]:
            self._keys[index] = key
            self._sift_up(index)
            return True
        return False

    def pop_min(self) -> tuple[Hashable, float]:
        if not self._items:
            raise IndexError("pop_min from an empty heap")

        min_item = self._items[0]
        min_key = self._keys[0]
        del self._pos[min_item]

        last_item = self._items.pop()
        last_key = self._keys.pop()

        if self._items:
            self._items[0] = last_item
            self._keys[0] = last_key
            self._pos[last_item] = 0
            self._sift_down(0)

        return min_item, min_key

    def _swap(self, i: int, j: int) -> None:
        items, keys, pos = self._items, self._keys, self._pos
        items[i], items[j] = items[j], items[i]
        keys[i], keys[j] = keys[j], keys[i]
        pos[items[i]] = i
        pos[items[j]] = j

    def _sift_up(self, index: int) -> None:
        keys = self._keys
        while index > 0:
            parent = (index - 1) // 2
            if keys[index] >= keys[parent]:
                return
            self._swap(index, parent)
            index = parent

    def _sift_down(self, index: int) -> None:
        keys = self._keys
        size = len(keys)
        while True:
            left = 2 * index + 1
            right = left + 1
            smallest = index

            if left < size and keys[left] < keys[smallest]:
                smallest = left
            if right < size and keys[right] < keys[smallest]:
                smallest = right

            if smallest == index:
                return
            self._swap(index, smallest)
            index = smallest
