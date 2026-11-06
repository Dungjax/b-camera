"""Camera Focus Rig — Blender camera control add-on.

The package entry point deliberately stays small. Feature implementation lives
in focused modules; registration is centralized in :mod:`registration`.
"""

bl_info = {
    "name": "Camera Focus Rig",
    "author": "Camera Focus Rig Contributors",
    "version": (1, 2, 2),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Camera Rig",
    "description": "Camera roll, damping, turntables, and animated target transitions",
    "category": "Camera",
}

from .registration import register, unregister

__all__ = ("register", "unregister")
