################################################################################
# Import Libraries
import bpy
import numpy as np
import math
from mathutils import Matrix
import importlib.util
import sys
import os

### Load the Render Functions ###
# create module specification based on file path
spec_render_func = importlib.util.spec_from_file_location("render_functions", "phase_2_visualize/src/render_functions.py")
# create module based on specification
render_func = importlib.util.module_from_spec(spec_render_func)
# load module
spec_render_func.loader.exec_module(render_func)

# get arguments
argv = sys.argv
argv = argv[argv.index("--") + 1 :]

### Load the Render Parameters ###
# get path to module from argv
path_to_module = argv[0]
# get module name from argv
module_name = os.path.basename(path_to_module)[:-3]
# create module specification based on file path
spec_params = importlib.util.spec_from_file_location(module_name, path_to_module)
# create module based on specification
params = importlib.util.module_from_spec(spec_params)
# load module
spec_params.loader.exec_module(params)

# Grab arguments
dimensions_file = argv[1]
displacement_file = argv[2]
color_file = argv[3]
apron_file = argv[4]
labels_file = argv[5]
out_file = argv[6]
data_folder = os.path.dirname(displacement_file)

# Make out_dir
out_dir = os.path.dirname(out_file)
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

################################################################################
# Remove everything from the scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

################################################################################
# This sets the render engine to CYCLES.
# In order for TopoBlender to render your topography correctly, you must use
# this render engine. This engine is optimized for GPUs, so if your computer
# lacks a GPU, TopoBlender may be slow.

# Define current scene
scn = bpy.context.scene

# Check the render engine, and change to CYCLES
if not scn.render.engine == "CYCLES":
    scn.render.engine = "CYCLES"

# If cycles, change to gpu rendering if user selects GPU
if scn.render.engine == "CYCLES":
    if params.GPU_boolean:
        scn.cycles.device = "GPU"

################################################################################
# Set up the Topography
width, height, topo_obj = render_func.setup_topo(dimensions_file, displacement_file, color_file)

# Add Layers
for i in range(0, params.number_of_layers):
    render_func.setup_layer(i, dimensions_file, data_folder)

################################################################################
# Set up the surrounding platforms

# Make four platforms to surround data
platform_x = 100.0 * params.plane_size
platform_y = 100.0 * params.plane_size

if width / height > 1.0:
    ud_platform_x = params.plane_size
    ud_platform_y = (platform_y - height / width) / 2.0
    lr_platform_x = (platform_x - params.plane_size) / 2.0
    displace_x = (lr_platform_x + params.plane_size) / 2.0
    displace_y = (ud_platform_y + params.plane_size * height / width) / 2.0
else:
    ud_platform_x = width / height
    ud_platform_y = (platform_y - params.plane_size) / 2.0
    lr_platform_x = (platform_x - width / height) / 2.0
    displace_x = (lr_platform_x + params.plane_size * width / height) / 2.0
    displace_y = (ud_platform_y + params.plane_size) / 2.0

# U & D platforms
render_func.make_platform(
    (0, displace_y, 0), ud_platform_x, ud_platform_y, apron_file, "Apron_North"
)
render_func.make_platform(
    (0, -displace_y, 0), ud_platform_x, ud_platform_y, apron_file, "Apron_South"
)
# L & R platforms
render_func.make_platform(
    (-displace_x, 0.0, 0), lr_platform_x, platform_y, apron_file, "Apron_West"
)
render_func.make_platform((displace_x, 0.0, 0), lr_platform_x, platform_y, apron_file, "Apron_East")

################################################################################
# Add Pin
if labels_file != "NULL":
    import csv, ast
    # Read the CSV file
    with open(labels_file, mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            render_func.add_pin(float(row[0]), float(row[1]), dimensions_file, displacement_file, row[2], ast.literal_eval(row[3]), ast.literal_eval(row[4]))

################################################################################
# Set up the sky

# Add world sky
topo_world = bpy.data.worlds.new("topo_world")
topo_world.use_nodes = True
topo_world_node = topo_world.node_tree.nodes.new("ShaderNodeTexSky")
topo_world_node.sun_elevation = np.radians(params.sun_tilt)
topo_world_node.sun_rotation = np.radians(params.sun_rotation)
topo_world_node.sun_intensity = params.sun_intensity
topo_world.node_tree.nodes["Background"].inputs[1].default_value = params.sun_strength
topo_world.node_tree.links.new(
    topo_world_node.outputs["Color"], topo_world.node_tree.nodes["Background"].inputs[0]
)

bpy.context.scene.world = topo_world

################################################################################
# Set up the camera

# Add camera
cam = bpy.data.cameras.new("topo_cam")
cam_obj = bpy.data.objects.new("topo_cam", cam)
cam_obj.rotation_euler = (
    np.radians(90.0 - params.camera_tilt),
    np.radians(0),
    np.radians(180.0 - params.camera_rotation),
)
cam_obj.matrix_basis @= Matrix.Translation((0.0, 0.0, params.camera_distance))

# Set camera
if params.camera_type == "orthogonal":
    bpy.data.cameras["topo_cam"].type = "ORTHO"
    bpy.data.cameras["topo_cam"].ortho_scale = params.ortho_scale
    bpy.data.cameras["topo_cam"].shift_x = params.shift_x
    bpy.data.cameras["topo_cam"].shift_y =params.shift_y
elif params.camera_type == "perspective":
    bpy.data.cameras["topo_cam"].type = "PERSP"
    bpy.data.cameras["topo_cam"].lens = params.focal_length
    bpy.data.cameras["topo_cam"].shift_x = params.shift_x
    bpy.data.cameras["topo_cam"].shift_y = params.shift_y

# Set depth of field
if params.use_depth_of_field == True:
    bpy.data.cameras["topo_cam"].dof.use_dof = True
    bpy.data.cameras["topo_cam"].dof.aperture_fstop = params.f_stop
    bpy.data.cameras["topo_cam"].dof.focus_distance = params.dof_distance


bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

################################################################################
# Render settings
bpy.context.scene.view_settings.view_transform = params.view_transform
bpy.context.scene.view_settings.exposure = params.exposure
bpy.context.scene.view_settings.gamma = params.gamma
bpy.context.scene.cycles.samples = params.samples
bpy.context.scene.render.resolution_x = int(params.res_x)
if params.res_y == "AUTO":
    bpy.context.scene.render.resolution_y = int(params.res_x * height / width)
else:
    bpy.context.scene.render.resolution_y = int(params.res_y)
bpy.context.scene.render.filepath = os.getcwd() + "/" + out_file

# Render!
bpy.ops.render.render(write_still=True)

# This will make the UI look nice if you choose to open Blender

# prevent opening the intro splash screen if using the UI
bpy.context.preferences.view.show_splash = False

# change viewport view to material preview
for area in bpy.context.screen.areas: 
    if area.type == 'VIEW_3D':
        for space in area.spaces: 
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'

# deselect objects
bpy.context.active_object.select_set(False)

# select the topography
bpy.context.view_layer.objects.active = topo_obj
topo_obj.select_set(True)

# Toggle the camera
area_type = 'VIEW_3D' # change this to use the correct Area Type context you want to process in
areas  = [area for area in bpy.context.window.screen.areas if area.type == area_type]

with bpy.context.temp_override(
    window=bpy.context.window,
    area=areas[0],
    region=[region for region in areas[0].regions if region.type == 'WINDOW'][0],
    screen=bpy.context.window.screen):
    bpy.ops.view3d.view_camera()