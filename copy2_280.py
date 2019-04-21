#  ***** BEGIN GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see http://www.gnu.org/licenses/
#  or write to the Free Software Foundation, Inc., 51 Franklin Street,
#  Fifth Floor, Boston, MA 02110-1301, USA.
#
#  ***** END GPL LICENSE BLOCK *****

bl_info = {
    "name": "copy2 vertices, edges or faces",
    "author": "Eleanor Howick (elfnor.com)",
    "version": (0, 2),
    "blender": (2,80,0),
    "location": "3D View > Object > Copy 2",
    "description": "Copy one object to the selected vertices, edges or faces of another object",
    "warning": "",
    "category": "Object",
}

import bpy

from mathutils import Vector, Matrix


class VIEW3D_OT_copy2(bpy.types.Operator):
    bl_idname = "mesh.copy2"
    bl_label = "Copy 2"
    bl_options = {"REGISTER", "UNDO"}

    obj_list = None

    def obj_list_cb(self, context):
        return VIEW3D_OT_copy2.obj_list

    def sec_axes_list_cb(self, context):
        if self.priaxes == "X":
            return [("Y", "Y", "Y"), ("Z", "Z", "Z")]

        if self.priaxes == "Y":
            return [("X", "X", "X"), ("Z", "Z", "Z")]

        if self.priaxes == "Z":
            return [("X", "X", "X"), ("Y", "Y", "Y")]
        return None

    copytype: bpy.props.EnumProperty(
        items=(
            ("V", "", "paste to vertices", "VERTEXSEL", 0),
            ("E", "", "paste to edges", "EDGESEL", 1),
            ("F", "", "paste to faces", "FACESEL", 2),
        ),
        description="where to paste to",
    )

    copyfromobject: bpy.props.EnumProperty(items=obj_list_cb, name="Copy from:")

    priaxes: bpy.props.EnumProperty(
        items=(("X", "X", "along X"), ("Y", "Y", "along Y"), ("Z", "Z", "along Z"))
    )

    secaxes: bpy.props.EnumProperty(items=sec_axes_list_cb, name="Secondary Axis")
    edgescale: bpy.props.BoolProperty(name="Scale to fill edge?")
    scale: bpy.props.FloatProperty(default=1.0, min=0.0)

    def execute(self, context):

        copytoobject = context.active_object.name
        axes = self.priaxes + self.secaxes
        copy_to_from(
            context.scene,
            bpy.data.objects[copytoobject],
            bpy.data.objects[self.copyfromobject],
            self.copytype,
            axes,
            self.edgescale,
            self.scale,
        )

        return {"FINISHED"}

    def draw(self, context):

        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "copyfromobject")
        layout.prop(self, "copytype", text="to:", expand=True)
        layout.prop(self, "priaxes", text="primary axis:", expand=True)
        layout.prop(self, "secaxes", text="secondary axis", expand=True)
        if self.copytype == "E":
            layout.prop(self, "edgescale", text="scale to fit edge")
            layout.prop(self, "scale")

        return

    def invoke(self, context, event):
        print("invoke called")
        VIEW3D_OT_copy2.obj_list = [
            (obj.name, obj.name, obj.name) for obj in bpy.data.objects
        ]
        return {"FINISHED"}


def add_to_menu(self, context):
    self.layout.separator()
    self.layout.operator_context = "INVOKE_DEFAULT"
    self.layout.operator(VIEW3D_OT_copy2.bl_idname, icon="DUPLICATE")
    self.layout.separator()
    return


def register():
    bpy.utils.register_class(VIEW3D_OT_copy2)
    bpy.types.VIEW3D_MT_object_specials.prepend(add_to_menu)
    bpy.types.VIEW3D_MT_object.append(add_to_menu)
    return


def unregister():
    bpy.utils.unregister_class(VIEW3D_OT_copy2)
    bpy.types.VIEW3D_MT_object.remove(add_to_menu)
    bpy.types.VIEW3D_MT_object_specials.remove(add_to_menu)
    return


# -----------------------------------
# copying functions


def copy_to_from(scene, to_obj, from_obj, copymode, axes, edgescale, scale):
    """
    selct copying function based on user selection of vertex, edge or face copy mode
    """
    if copymode == "V":
        return vertex_copy(scene, to_obj, from_obj, axes)
    if copymode == "E":
        return edge_copy(scene, to_obj, from_obj, axes, edgescale, scale)
    if copymode == "F":
        return face_copy(scene, to_obj, from_obj, axes)
    return None


axes_dict = {
    "XY": (1, 2, 0),
    "XZ": (2, 1, 0),
    "YX": (0, 2, 1),
    "YZ": (2, 0, 1),
    "ZX": (0, 1, 2),
    "ZY": (1, 0, 2),
}


def copyto(scene, source_obj, pos, xdir, zdir, axes, scale=None):
    """ 
     generic copy function for all copy modes
     copy the source_obj to pos, so its primary axis points in zdir and its 
     secondary axis points in xdir       
     """
    copy_obj = source_obj.copy()
    scene.collection.objects.link(copy_obj)

    xdir = xdir.normalized()
    zdir = zdir.normalized()
    # rotation first
    z_axis = zdir
    x_axis = xdir
    y_axis = z_axis.cross(x_axis)
    # use axes_dict to assign the axis as chosen in panel
    A, B, C = axes_dict[axes]
    rot_mat = Matrix()
    rot_mat[A].xyz = x_axis
    rot_mat[B].xyz = y_axis
    rot_mat[C].xyz = z_axis
    rot_mat.transpose()

    # rotate object
    copy_obj.matrix_world = rot_mat

    # move object into position
    copy_obj.location = pos

    # scale object
    if scale is not None:
        copy_obj.scale = scale

    return copy_obj


def vertex_copy(scene, obj, source_obj, axes):
    # vertex select mode
    sel_verts = []
    copy_list = []
    for v in obj.data.vertices:
        if v.select:
            sel_verts.append(v)

    # make a set for each vertex. The set contains all the connected vertices
    # use sets so the list is unique
    vert_con = [set() for i in range(len(obj.data.vertices))]
    for e in obj.data.edges:
        vert_con[e.vertices[0]].add(e.vertices[1])
        vert_con[e.vertices[1]].add(e.vertices[0])

    for v in sel_verts:
        pos = v.co @ obj.matrix_world.transposed()
        xco = (
            obj.data.vertices[list(vert_con[v.index])[0]].co
            @ obj.matrix_world.transposed()
        )

        zdir = (v.co + v.normal) @ obj.matrix_world.transposed() - pos
        zdir = zdir.normalized()

        edir = pos - xco

        # edir is nor perpendicular to z dir
        # want xdir to be projection of edir onto plane through pos with direction zdir
        xdir = edir - edir.dot(zdir) * zdir
        xdir = -xdir.normalized()

        copy = copyto(scene, source_obj, pos, xdir, zdir, axes)
        copy_list.append(copy)
    # select all copied objects
    for copy in copy_list:
        copy.select_set(state=True, view_layer=None)

    obj.select_set(state=False, view_layer=None)
    return copy_list


def edge_copy(scene, obj, source_obj, axes, es, scale):
    # edge select mode
    sel_edges = []
    copy_list = []
    for e in obj.data.edges:
        if e.select:
            sel_edges.append(e)
    for e in sel_edges:
        # pos is average of two edge vertexs
        v0 = obj.data.vertices[e.vertices[0]].co @ obj.matrix_world.transposed()
        v1 = obj.data.vertices[e.vertices[1]].co @ obj.matrix_world.transposed()
        pos = (v0 + v1) / 2
        # xdir is along edge
        xdir = v0 - v1
        xlen = xdir.magnitude
        xdir = xdir.normalized()
        # project each edge vertex normal onto plane normal to xdir
        vn0 = (
            obj.data.vertices[e.vertices[0]].co @ obj.matrix_world.transposed()
            + obj.data.vertices[e.vertices[0]].normal
        ) - v0
        vn1 = (
            obj.data.vertices[e.vertices[1]].co @ obj.matrix_world.transposed()
            + obj.data.vertices[e.vertices[1]].normal
        ) - v1
        vn0p = vn0 - vn0.dot(xdir) * xdir
        vn1p = vn1 - vn1.dot(xdir) * xdir
        # the mean of the two projected normals is the zdir
        zdir = vn0p + vn1p
        zdir = zdir.normalized()
        escale = None
        if es:
            escale = Vector([1.0, 1.0, 1.0])
            i = list("XYZ").index(axes[1])
            escale[i] = scale * xlen / source_obj.dimensions[i]

        copy = copyto(scene, source_obj, pos, xdir, zdir, axes, scale=escale)
        copy_list.append(copy)
    # select all copied objects
    for copy in copy_list:
        copy.select_set(state=True, view_layer=None)
    obj.select_set(state=False, view_layer=None)
    return copy_list


def face_copy(scene, obj, source_obj, axes):
    # face select mode
    sel_faces = []
    copy_list = []
    for f in obj.data.polygons:
        if f.select:
            sel_faces.append(f)
    for f in sel_faces:
        fco = f.center @ obj.matrix_world.transposed()
        # get first vertex corner of transformed object
        vco = obj.data.vertices[f.vertices[0]].co @ obj.matrix_world.transposed()
        # get face normal of transformed object
        fn = (f.center + f.normal) @ obj.matrix_world.transposed() - fco
        fn = fn.normalized()

        copy = copyto(scene, source_obj, fco, vco - fco, fn, axes)
        copy_list.append(copy)
    # select all copied objects
    for copy in copy_list:
        copy.select_set(state=True, view_layer=None)
    obj.select_set(state=False, view_layer=None)
    return copy_list


if __name__ == "__main__":
    register()
