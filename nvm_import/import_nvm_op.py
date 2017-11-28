import bpy
import os
from mathutils import Matrix, Vector
import math
from math import radians
import time
from nvm_import.stop_watch import StopWatch

def get_world_matrix_from_translation_vec(translation_vec, rotation):
    t = Vector(translation_vec).to_4d()
    camera_rotation = Matrix()
    for row in range(3):
        camera_rotation[row][0:3] = rotation[row]

    camera_rotation.transpose()  # = Inverse rotation

    camera_center = -(camera_rotation * t)  # Camera position in world coordinates
    camera_center[3] = 1.0

    camera_rotation = camera_rotation.copy()
    camera_rotation.col[3] = camera_center  # Set translation to camera position
    return camera_rotation

def invert_y_and_z_axis(input_matrix_or_vector):
    """
    VisualSFM and Blender use coordinate systems, which differ in the y and z coordinate
    This Function inverts the y and the z coordinates in the corresponding matrix / vector entries
    Iinvert y and z axis <==> rotation by 180 degree around the x axis
    """
    output_matrix_or_vector = input_matrix_or_vector.copy()
    output_matrix_or_vector[1] = -output_matrix_or_vector[1]
    output_matrix_or_vector[2] = -output_matrix_or_vector[2]
    return output_matrix_or_vector

def add_obj(data, obj_name, deselect_others=False):
    scene = bpy.context.scene

    if deselect_others:
        for obj in scene.objects:
            obj.select = False

    new_obj = bpy.data.objects.new(obj_name, data)
    scene.objects.link(new_obj)
    new_obj.select = True

    if scene.objects.active is None or scene.objects.active.mode == 'OBJECT':
        scene.objects.active = new_obj
    return new_obj

def set_object_parent(child_object_name, parent_object_name, keep_transform=False):
    child_object_name.parent = parent_object_name
    if keep_transform:
        child_object_name.matrix_parent_inverse = parent_object_name.matrix_world.inverted()

def add_empty(empty_name):
    empty_obj = bpy.data.objects.new(empty_name, None)
    bpy.context.scene.objects.link(empty_obj)
    return empty_obj

def add_points_as_mesh(points, add_meshes_at_vertex_positions, mesh_type, point_extent):
    print("Adding Points: ...")
    stop_watch = StopWatch()
    name = "Point_Cloud"
    mesh = bpy.data.meshes.new(name)
    mesh.update()
    mesh.validate()

    point_world_coordinates = [tuple(point.coord) for point in points]

    mesh.from_pydata(point_world_coordinates, [], [])
    meshobj = add_obj(mesh, name)

    if add_meshes_at_vertex_positions:
        print("Representing Points in the Point Cloud with Meshes: True")
        print("Mesh Type: " + str(mesh_type))

        # The default size of elements added with 
        #   primitive_cube_add, primitive_uv_sphere_add, etc. is (2,2,2)
        point_scale = point_extent * 0.5 

        bpy.ops.object.select_all(action='DESELECT')
        if mesh_type == "PLANE":
            bpy.ops.mesh.primitive_plane_add(radius=point_scale)
        elif mesh_type == "CUBE":
            bpy.ops.mesh.primitive_cube_add(radius=point_scale)
        elif mesh_type == "SPHERE":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=point_scale)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=point_scale)
        viz_mesh = bpy.context.object

        for index, point in enumerate(points):
            
            if index % 1000 == 0:
                print("Creating Representation for Vertex " + str(index) + " of " + str(len(points)))
            coord = tuple(point.coord)
            color = tuple(point.color)  # must be in between 0 and 1
            
            ob = viz_mesh.copy()
            ob.location = coord
            bpy.context.scene.objects.link(ob)

            mat = bpy.data.materials.new("materialName")
            mat.diffuse_color = [color[0]/255.0, color[1]/255.0, color[2]/255.0]
            ob.active_material = mat
            ob.material_slots[0].link = 'OBJECT'
            ob.material_slots[0].material = mat
        bpy.context.scene.update
    else:
        print("Representing Points in the Point Cloud with Meshes: False")
    print("Duration: " + str(stop_watch.get_elapsed_time()))
    print("Adding Points: Done")

    
def add_cameras(cameras, path_to_images=None,
                add_image_planes=False,
                convert_camera_coordinate_system=True,
                cameras_parent='Cameras',
                camera_group_name='Camera Group',
                image_planes_parent='Image Planes',
                image_plane_group_name='Image Plane Group'):

    """
    ======== The images are currently only shown in BLENDER RENDER ========
    ======== Make sure to enable TEXTURE SHADING in the 3D view to make the images visible ========

    :param cameras:
    :param path_to_images:
    :param add_image_planes:
    :param convert_camera_coordinate_system:
    :param cameras_parent:
    :param camera_group_name:
    :param image_plane_group_name:
    :return:
    """
    print("Adding Cameras: ...")
    stop_watch = StopWatch()
    cameras_parent = add_empty(cameras_parent)
    camera_group = bpy.data.groups.new(camera_group_name)

    if add_image_planes:
        print("Adding image planes: True")
        image_planes_parent = add_empty(image_planes_parent)
        image_planes_group = bpy.data.groups.new(image_plane_group_name)
    else:
        print("Adding image planes: False")

    # Adding cameras and image planes:
    for index, camera in enumerate(cameras):

        start_time = stop_watch.get_elapsed_time()
        assert camera.width is not None and camera.height is not None

        # camera_name = "Camera %d" % index     # original code
        # Replace the camera name so it matches the image name (without extension)
        image_file_name_stem = os.path.splitext(os.path.basename(camera.file_name))[0]
        camera_name = image_file_name_stem + '_cam'

        focal_length = camera.calibration_mat[0][0]

        # Add camera:
        bcamera = bpy.data.cameras.new(camera_name)
        bcamera.angle_x = math.atan(camera.width / (focal_length * 2.0)) * 2.0
        bcamera.angle_y = math.atan(camera.height / (focal_length * 2.0)) * 2.0
        camera_object = add_obj(bcamera, camera_name)

        translation_vec = camera.get_translation_vec()
        rotation_mat = camera.get_rotation_mat()
        # Transform the camera coordinate system from computer vision camera coordinate frames to the computer
        # vision camera coordinate frames
        # That is, rotate the camera matrix around the x axis by 180 degree, i.e. invert the x and y axis
        rotation_mat = invert_y_and_z_axis(rotation_mat)
        translation_vec = invert_y_and_z_axis(translation_vec)
        camera_object.matrix_world = get_world_matrix_from_translation_vec(translation_vec, rotation_mat)
        set_object_parent(camera_object, cameras_parent, keep_transform=True)
        camera_group.objects.link(camera_object)

        if add_image_planes:
            path_to_image = os.path.join(path_to_images, camera.file_name)
            if os.path.isfile(path_to_image):

                # Group image plane and camera:
                camera_image_plane_pair = bpy.data.groups.new(
                    "Camera Image Plane Pair Group %s" % image_file_name_stem)
                camera_image_plane_pair.objects.link(camera_object)

                image_plane_name = image_file_name_stem + '_image_plane'

                # do not add image planes by default, this is slow !
                bimage = bpy.data.images.load(path_to_image)
                image_plane_obj = add_camera_image_plane(
                    rotation_mat, translation_vec, bimage, camera.width, 
                    camera.height, focal_length, name=image_plane_name)
                camera_image_plane_pair.objects.link(image_plane_obj)

                set_object_parent(image_plane_obj, image_planes_parent, keep_transform=True)
                image_planes_group.objects.link(image_plane_obj)

        end_time = stop_watch.get_elapsed_time()

    print("Duration: " + str(stop_watch.get_elapsed_time()))
    print("Adding Cameras: Done")

def add_camera_image_plane(rotation_mat, translation_vec, bimage, width, height, focal_length, name):
    """
    Create mesh for image plane
    """
    mesh = bpy.data.meshes.new(name)
    mesh.update()
    mesh.validate()

    plane_distance = 1.0  # Distance from camera position
    # Right vector in view frustum at plane_distance:
    right = Vector((1, 0, 0)) * (width / focal_length) * plane_distance
    # Up vector in view frustum at plane_distance:
    up = Vector((0, 1, 0)) * (height / focal_length) * plane_distance
    # Camera view direction:
    view_dir = -Vector((0, 0, 1)) * plane_distance
    plane_center = view_dir

    corners = ((-0.5, -0.5),
               (+0.5, -0.5),
               (+0.5, +0.5),
               (-0.5, +0.5))
    points = [(plane_center + c[0] * right + c[1] * up)[0:3] for c in corners]
    mesh.from_pydata(points, [], [[0, 1, 2, 3]])

    # Assign image to face of image plane:
    uvmap = mesh.uv_textures.new()
    face = uvmap.data[0]
    face.image = bimage

    # Add mesh to new image plane object:
    mesh_obj = add_obj(mesh, name)

    image_plane_material = bpy.data.materials.new(name="image_plane_material")
    image_plane_material.use_shadeless = True

    # Assign it to object
    if mesh_obj.data.materials:
        # assign to 1st material slot
        mesh_obj.data.materials[0] = image_plane_material
    else:
        # no slots
        mesh_obj.data.materials.append(image_plane_material)
    world_matrix = get_world_matrix_from_translation_vec(translation_vec, rotation_mat)
    mesh_obj.matrix_world = world_matrix
    mesh.update()
    mesh.validate()
    return mesh_obj


from bpy.props import (CollectionProperty,
                       StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       IntProperty,
                       )

from bpy_extras.io_utils import (ImportHelper,
                                 ExportHelper,
                                 axis_conversion)

class ImportNVM(bpy.types.Operator, ImportHelper):
    """Load a NVM file"""
    bl_idname = "import_scene.nvm"
    bl_label = "Import NVM"
    bl_options = {'UNDO'}

    files = CollectionProperty(
        name="File Path",
        description="File path used for importing the NVM file",
        type=bpy.types.OperatorFileListElement)

    directory = StringProperty()

    import_cameras = BoolProperty(
        name="Import Cameras",
        description = "Import Cameras", 
        default=True)
    default_width = IntProperty(
        name="Default Width",
        description = "Width, which will be used used if corresponding image is not found.", 
        default=1920)
    default_height = IntProperty(
        name="Default Height", 
        description = "Height, which will be used used if corresponding image is not found.",
        default=1080)
    add_image_planes = BoolProperty(
        name="Add an Image Plane for each Camera",
        description = "Add an Image Plane for each Camera", 
        default=False)

    import_points = BoolProperty(
        name="Import Points",
        description = "Import Points", 
        default=True)
    add_meshes_at_vertex_positions = BoolProperty(
        name="Add Meshes at Vertices (This may take a while!)",
        description = "Add a mesh at each vertex position, so it can be easily rendered. In order to scale the meshes, select one of the them, go into edit mode, and scale the object. All other meshes are scaled accordingly.", 
        default=False)
    mesh_items = [
        ("CUBE", "Cube", "", 1),
        ("SPHERE", "Sphere", "", 2),
        ("PLANE", "Plane", "", 3)
        ]
    mesh_type = EnumProperty(
        name="Mesh Type",
        description = "Select the vertex representation mesh type.", 
        items=mesh_items)
    point_extent = FloatProperty(
        name="Initial Point Extent (in Blender Units)", 
        description = "Initial Point Extent for meshes at vertex positions",
        default=0.01)


    filename_ext = ".nvm"
    filter_glob = StringProperty(default="*.nvm", options={'HIDDEN'})

    def execute(self, context):
        paths = [os.path.join(self.directory, name.name)
                 for name in self.files]
        if not paths:
            paths.append(self.filepath)

        from nvm_import.nvm_file_handler import NVMFileHandler

        for path in paths:
            
            path_to_images = os.path.dirname(path)
            cameras, points = NVMFileHandler.parse_nvm_file(path)
            cameras = NVMFileHandler.parse_camera_image_files(
                cameras, path_to_images, self.default_width, self.default_height)
            print("Number cameras: " + str(len(cameras)))
            print("Number points: " + str(len(points)))
            if self.import_points:
                add_points_as_mesh(points, self.add_meshes_at_vertex_positions, self.mesh_type, self.point_extent)
            if self.import_cameras:
                add_cameras(cameras, path_to_images=path_to_images, add_image_planes=self.add_image_planes)
            

        return {'FINISHED'}