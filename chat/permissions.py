from typing import Callable, Optional

RoomPermissionChecker = Callable[[object, object], bool]

_room_permission_checkers: dict[str, RoomPermissionChecker] = {}


def register_room_permission_checker(source_app: str, checker: RoomPermissionChecker) -> None:
    if not callable(checker):
        raise TypeError("Room permission checker must be callable")
    current = _room_permission_checkers.get(source_app)
    if current is not None and current != checker:
        raise ValueError(f"A room permission checker is already registered for {source_app}")
    _room_permission_checkers[source_app] = checker


def get_room_permission_checker(source_app: str) -> Optional[RoomPermissionChecker]:
    return _room_permission_checkers.get(source_app)
