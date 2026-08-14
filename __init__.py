# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Export Object to .blend",
    "author": "Martynas Žiemys",
    "description": "",
    "blender": (5, 0, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Import/Export",
}


import bpy
import os
import subprocess
import sys
from bpy_extras.io_utils import ExportHelper
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator


def export_object_to_blend(context, filepath, relink):
    addon_dir = os.path.dirname(__file__)
    empty_scene_path = os.path.join(addon_dir, "empty_scene.blend")
    if not os.path.exists(empty_scene_path):
        print(f"Error: empty_scene.blend not found at {empty_scene_path}")
        return {'CANCELLED'}
    selected_objects = context.selected_objects
    if not selected_objects:
        print("Error: No objects selected.")
        return {'CANCELLED'}
    obj_name = selected_objects[0].name
    temp_source_path = os.path.join(addon_dir, "_temp_export_source.blend")
    bpy.ops.wm.save_as_mainfile(filepath=temp_source_path, copy=True)
    script_path = os.path.join(addon_dir, "_temp_export_runner.py")
    script_content = f"""
import bpy

bpy.ops.wm.open_mainfile(filepath={empty_scene_path!r})
with bpy.data.libraries.load({temp_source_path!r}, link=False) as (data_from, data_to):
    if {obj_name!r} in data_from.objects:
        data_to.objects = [{obj_name!r}]
for obj in data_to.objects:
    if obj is not None:
        bpy.context.collection.objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath={filepath!r})
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    blender_executable = sys.executable
    subprocess.run([blender_executable, "--background", "--python", script_path])
    if os.path.exists(temp_source_path):
        os.remove(temp_source_path)
    if os.path.exists(script_path):
        os.remove(script_path)
    if relink and os.path.exists(filepath):
        for obj in selected_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            if obj_name in data_from.objects:
                data_to.objects = [obj_name]
        for obj in data_to.objects:
            if obj is not None:
                context.collection.objects.link(obj)
    return {'FINISHED'}


class ExportToBlend(Operator, ExportHelper):
    """Export Selected Object to .blend"""
    bl_idname = "export_to_blend.export_to_blend"
    bl_label = "Export to .blend"
    filename_ext = ".blend"
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )
    relink: BoolProperty(
        name="Relink to scene",
        description="relink the object back to scene",
        default=True,
    )
    def execute(self, context):
        return export_object_to_blend(context, self.filepath, self.relink)


def menu_func_export(self, context):
    self.layout.operator(ExportToBlend.bl_idname, text="Export to .blend")


def register():
    bpy.utils.register_class(ExportToBlend)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportToBlend)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()