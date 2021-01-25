import attr

@attr.s
class MouseEvent:
    event_name: str = attr.ib()
    X: float = attr.ib()
    Y: float = attr.ib()