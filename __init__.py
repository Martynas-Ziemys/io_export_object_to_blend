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
    "version": (0, 0, 10),
    "location": "",
    "warning": "",
    "category": "Import/Export",
}

import bpy
import os
import subprocess
import tempfile
from bpy_extras.io_utils import ExportHelper
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator

class ExportToBlend(Operator, ExportHelper):
    """Export Selected to .blend"""
    bl_idname = "export_to_blend.export_to_blend"
    bl_label = "Export to .blend"
    filename_ext = ".blend"
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )
    relink_mode: EnumProperty(
        name="Relink Mode",
        items=[
            ('NONE', "None", "Do not relink after export"),
            ('OBJECT', "Relink Objects", "Delete local objects and link exported objects"),
            ('DATA', "Link Data", "Keep local objects and link only their data from exported file"),
        ],
        default='OBJECT',
    )
    mark_asset: BoolProperty(
        name="Mark as Asset",
        default=True,
    )
    export_hierarchy: BoolProperty(
        name="Export Hierarchy",
        description="Include all children recursively",
        default=False,
    )

    def invoke(self, context, event):
        if context.active_object:
            self.filepath = context.active_object.name + self.filename_ext
        elif context.selected_objects:
            self.filepath = context.selected_objects[0].name + self.filename_ext
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        selected_objects = context.selected_objects
        target_objects = set(selected_objects)
        if self.export_hierarchy:
            def collect_children(obj):
                for child in obj.children:
                    target_objects.add(child)
                    collect_children(child)
            for obj in list(selected_objects):
                collect_children(obj)

        linked_objects = [obj for obj in target_objects if obj.library is not None]
        if linked_objects:
            self.report({'ERROR'}, "Cannot export linked objects. Make them local first.")
            return {'CANCELLED'}

        if bpy.data.is_dirty or not bpy.data.filepath:
            self.report({'WARNING'}, "File saved.")
            bpy.ops.wm.save_mainfile()

        addon_dir = os.path.dirname(__file__)
        empty_scene_path = os.path.join(addon_dir, "empty_scene.blend")

        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        obj_names = [obj.name for obj in target_objects]
        source_filepath = bpy.data.filepath
        temp_dir = tempfile.mkdtemp(prefix="blend_export")
        script_path = os.path.join(temp_dir, "blend_export.py")
        script_content = f"""
import bpy
import time

bpy.ops.wm.open_mainfile(filepath={empty_scene_path!r})
object_names = {obj_names!r}
with bpy.data.libraries.load({source_filepath!r}, link=False) as (data_from, data_to):
    data_to.objects = [name for name in object_names if name in data_from.objects]
for obj in data_to.objects:
    bpy.context.collection.objects.link(obj)
if {str(self.mark_asset)!r}:
    for obj in data_to.objects:
        obj.asset_mark()
    time.sleep(0.5)
bpy.ops.wm.save_as_mainfile(filepath={self.filepath!r})
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        try:
            subprocess.run(
                [
                    bpy.app.binary_path, 
                    "-b", 
                    "--factory-startup", 
                    "-P", 
                    script_path
                ], 
                check=True)
        except subprocess.CalledProcessError as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}
        finally:
            try:
                os.remove(script_path)
            except:
                pass
            try:
                os.rmdir(temp_dir)
            except:
                pass

        if os.path.exists(self.filepath):
            if self.relink_mode == 'OBJECT':
                for obj in target_objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                with bpy.data.libraries.load(self.filepath, link=True) as (data_from, data_to):
                    data_to.objects = [name for name in obj_names if name in data_from.objects]
                for obj in data_to.objects:
                    if obj is not None:
                        context.collection.objects.link(obj)

            elif self.relink_mode == 'DATA':
                data_map = {obj: obj.data.name for obj in target_objects if obj.data}
                
                with bpy.data.libraries.load(self.filepath, link=True) as (data_from, data_to):
                    data_to.objects = [name for name in obj_names if name in data_from.objects]

                for linked_obj in data_to.objects:
                    if linked_obj and linked_obj.data:
                        for obj, orig_data_name in list(data_map.items()):
                            if linked_obj.data.name == orig_data_name:
                                old_data = obj.data
                                obj.data = linked_obj.data
                                if old_data and old_data.users == 0:
                                    bpy.data.batch_remove(ids=(old_data,))
                                break
                        bpy.data.objects.remove(linked_obj, do_unlink=True)

        self.report(
            {'INFO'}, 
            f"Successfully exported {len(target_objects)} objects to {os.path.basename(self.filepath)}"
        )
        return {'FINISHED'}

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