"""Shared mixin for operators that require an active Camera Focus Rig."""

from ..helpers import get_rig_camera


class _RigOperator:
    @classmethod
    def poll(cls, context):
        cam = get_rig_camera(context)
        return cam is not None and cam.cfr.mover is not None
