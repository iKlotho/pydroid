"""
    Custom fielf for using fields belong to the android device
"""
import attr

ANDROID_METADATA = "__android_metadata"


def android_field(
    default=attr.NOTHING,
    validator=None,
    repr=True,
    eq=True,
    order=None,
    hash=None,
    init=True,
    metadata={},
    type=None,
    converter=None,
    android_field=True,
):
    metadata = dict() if not metadata else metadata
    metadata[ANDROID_METADATA] = android_field
    return attr.ib(
        default=default,
        validator=validator,
        repr=repr,
        eq=eq,
        order=order,
        hash=hash,
        init=init,
        metadata=metadata,
        type=type,
        converter=converter,
    )

