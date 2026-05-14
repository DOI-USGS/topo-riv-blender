import bpy
import numpy as np
import math
from mathutils import Matrix
import importlib.util
import sys
import os

parent = os.getcwd()

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


def setup_topo(dimensions_file, displacement_file, color_file):
    """Sets up the topography node in blender

    Parameters
    ----------
    dimensions_file: string
        path to numpy array file containing the length, width, and height of topography
    displacement_file: string
        path to image file containing the height map
    color_file: string
        path to image file containing the texture map

    Returns
    -------
    width: int
        pixel width of height map
    height: int
        pixel height of height map

    """

    # Create an image from the datafile
    displacement_image = bpy.data.images.load(parent + "/" + displacement_file)
    color_image = bpy.data.images.load(parent + "/" + color_file)

    # make plane
    topo_mesh = bpy.ops.mesh.primitive_plane_add(
        size=params.plane_size, location=(0.0, 0.0, 0.0)
    )
    bpy.context.active_object.name = "Topography"
    topo_obj = bpy.context.active_object

    # Rename the collection
    bpy.data.collections.get("Collection").name = "Topographic Data"

    # Change the shape of the object to match data_aspect
    width, height = displacement_image.size
    if width / height > 1.0:
        topo_obj.scale = (1, height / width, 1)
    else:
        topo_obj.scale = (width / height, 1, 1)

    # get dimensions of topography
    x_length, y_length, relief = get_dimensions(dimensions_file, width, height)

    # add material
    topo_mat = bpy.data.materials.new("topo_mat")
    if bpy.app.version < (4, 1, 0):  # change in attribute structure with new version
        topo_mat.cycles.displacement_method = params.displacement_method
    else:
        topo_mat.displacement_method = params.displacement_method

    topo_mat.use_nodes = True

    # calculate subdivisions
    order_of_magnitude = math.floor(math.log10(params.number_of_subdivisions))
    first_digit = int(
        np.round(params.number_of_subdivisions / (10.0**order_of_magnitude))
    )

    topo_obj.data.materials.append(topo_mat)
    bpy.ops.object.mode_set(mode="EDIT")
    for i in range(0, order_of_magnitude):
        bpy.ops.mesh.subdivide(number_cuts=10)
    bpy.ops.mesh.subdivide(number_cuts=first_digit)
    bpy.ops.object.mode_set(mode="OBJECT")

    # add image node - determines the displacement
    displacement_image_node = topo_mat.node_tree.nodes.new("ShaderNodeTexImage")
    # assign png to image to node
    displacement_image_node.image = displacement_image
    # change colorspace to b&w
    displacement_image_node.image.colorspace_settings.name = "Non-Color"

    # add image node - determines the color of the lanscape
    color_image_node = topo_mat.node_tree.nodes.new("ShaderNodeTexImage")
    # assign png to image to node
    color_image_node.image = color_image
    # change colorspace to b&w
    color_image_node.image.colorspace_settings.name = "sRGB"

    # calculate vertical scale
    v_scale = get_v_scale(params.exaggeration, x_length, y_length, relief)

    # add displacement node
    displacement_node = topo_mat.node_tree.nodes.new("ShaderNodeDisplacement")
    displacement_node.inputs.get("Scale").default_value = v_scale
    displacement_node.inputs.get("Midlevel").default_value = 0.0

    # connect nodes
    topo_mat.node_tree.links.new(
        displacement_image_node.outputs["Color"], displacement_node.inputs["Height"]
    )
    topo_mat.node_tree.links.new(
        displacement_node.outputs["Displacement"],
        topo_mat.node_tree.nodes["Material Output"].inputs["Displacement"],
    )
    topo_mat.node_tree.links.new(
        color_image_node.outputs["Color"],
        topo_mat.node_tree.nodes["Principled BSDF"].inputs[0],
    )

    # change material properties
    topo_mat.node_tree.nodes["Principled BSDF"].inputs.get("IOR").default_value = 1.0
    topo_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Strength"
    ).default_value = 0.0
    topo_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Roughness"
    ).default_value = 1.0

    # organize nodes
    displacement_image_node.location.x, displacement_image_node.location.y = -500, 500
    color_image_node.location.x, color_image_node.location.y = -500, 0
    displacement_node.location.x, displacement_node.location.y = -200, 500
    topo_mat.node_tree.nodes["Principled BSDF"].location = (-100, 0)
    topo_mat.node_tree.nodes["Material Output"].location = (300, 0)

    return width, height, topo_obj


################################################################################
# Set up the layer
def setup_layer(layer, dimensions_file, data_folder):
    """Sets up the layer nodes in blender

    Parameters
    ----------
    layer: int
        layer index
    dimensions_file: string
        path to numpy array file containing the length, width, and height of topography
    data_folder: str
        path to folder containing the layer height and texture maps

    Returns
    -------
    none

    """

    # Create an image from the datafile
    displacement_image = bpy.data.images.load(
        parent + "/" + data_folder + "/heightmap_L" + str(layer) + ".png"
    )
    color_image = bpy.data.images.load(
        parent + "/" + data_folder + "/texturemap_L" + str(layer) + ".png"
    )

    # make plane
    layer_mesh = bpy.ops.mesh.primitive_plane_add(
        size=params.plane_size, location=(0.0, 0.0, 0.0)
    )
    bpy.context.active_object.name = "Layer_" + str(layer)
    layer_obj = bpy.context.active_object

    # Change the shape of the object to match data_aspect
    width, height = displacement_image.size
    if width / height > 1.0:
        layer_obj.scale = (1, height / width, 1)
    else:
        layer_obj.scale = (width / height, 1, 1)

    # get dimensions of topography
    x_length, y_length, relief = get_dimensions(dimensions_file, width, height)

    # add material
    layer_mat = bpy.data.materials.new("layer_mat_" + str(layer))
    if bpy.app.version < (4, 1, 0):  # change in attribute structure with new version
        layer_mat.cycles.displacement_method = params.displacement_method
    else:
        layer_mat.displacement_method = params.displacement_method
    layer_mat.use_nodes = True

    # calculate subdivisions
    order_of_magnitude = math.floor(math.log10(params.number_of_subdivisions))
    first_digit = int(
        np.round(params.number_of_subdivisions / (10.0**order_of_magnitude))
    )

    layer_obj.data.materials.append(layer_mat)
    bpy.ops.object.mode_set(mode="EDIT")
    for i in range(0, order_of_magnitude):
        bpy.ops.mesh.subdivide(number_cuts=10)
    bpy.ops.mesh.subdivide(number_cuts=first_digit)
    bpy.ops.object.mode_set(mode="OBJECT")

    # add image node - determines the displacement
    displacement_image_node = layer_mat.node_tree.nodes.new("ShaderNodeTexImage")
    # assign png to image to node
    displacement_image_node.image = displacement_image
    # change colorspace to b&w
    displacement_image_node.image.colorspace_settings.name = "Non-Color"

    # add image node - determines the color of the lanscape
    color_image_node = layer_mat.node_tree.nodes.new("ShaderNodeTexImage")
    # assign png to image to node
    color_image_node.image = color_image
    # change colorspace to b&w
    color_image_node.image.colorspace_settings.name = "sRGB"

    # add math nodes
    greater_than_node = layer_mat.node_tree.nodes.new("ShaderNodeMath")
    greater_than_node.operation = "GREATER_THAN"
    greater_than_node.inputs[1].default_value = 0.0
    add_node = layer_mat.node_tree.nodes.new("ShaderNodeMath")
    add_node.operation = "ADD"
    subtract_node = layer_mat.node_tree.nodes.new("ShaderNodeMath")
    subtract_node.operation = "SUBTRACT"
    subtract_node.inputs[1].default_value = 1.0

    # calculate vertical scale
    v_scale = get_v_scale(params.exaggeration, x_length, y_length, relief)

    # add displacement node
    displacement_node = layer_mat.node_tree.nodes.new("ShaderNodeDisplacement")
    displacement_node.inputs.get("Scale").default_value = v_scale
    displacement_node.inputs.get("Midlevel").default_value = 0.0

    # connect nodes
    layer_mat.node_tree.links.new(
        displacement_image_node.outputs["Color"], greater_than_node.inputs[0]
    )
    layer_mat.node_tree.links.new(
        greater_than_node.outputs["Value"], add_node.inputs[0]
    )
    layer_mat.node_tree.links.new(
        displacement_image_node.outputs["Color"], add_node.inputs[1]
    )
    layer_mat.node_tree.links.new(add_node.outputs["Value"], subtract_node.inputs[0])
    layer_mat.node_tree.links.new(
        subtract_node.outputs["Value"], displacement_node.inputs["Height"]
    )
    layer_mat.node_tree.links.new(
        displacement_node.outputs["Displacement"],
        layer_mat.node_tree.nodes["Material Output"].inputs["Displacement"],
    )
    layer_mat.node_tree.links.new(
        color_image_node.outputs["Color"],
        layer_mat.node_tree.nodes["Principled BSDF"].inputs[0],
    )

    # change material properties
    layer_mat.node_tree.nodes["Principled BSDF"].inputs.get("IOR").default_value = 1.0
    layer_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Strength"
    ).default_value = 0.0
    layer_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Roughness"
    ).default_value = 1.0
    layer_mat.node_tree.nodes["Principled BSDF"].inputs.get("Alpha").default_value = (
        params.layers_alpha[layer]
    )

    displacement_image_node.location.x, displacement_image_node.location.y = -500, 500
    color_image_node.location.x, color_image_node.location.y = -500, 0
    displacement_node.location.x, displacement_node.location.y = -400, 300
    greater_than_node.location.x, greater_than_node.location.y = -200, 600
    add_node.location.x, add_node.location.y = 0, 500
    subtract_node.location.x, subtract_node.location.y = 200, 400
    layer_mat.node_tree.nodes["Principled BSDF"].location = (-100, 0)
    layer_mat.node_tree.nodes["Material Output"].location = (300, 0)


def make_platform(loc, platform_size_x, platform_size_y, apron_file, name):
    """Sets up the platform node in blender

    Parameters
    ----------
    loc: 3 element tuple
        xyz center coordinate of the platform
    platform_size_x: float
        x-width of platform
    platform_size_y: float
        y-width of platform
    apron_file: string
        path to apron file containing the texture map (i.e., color of the background)
    name:
        name of the platform node

    Returns
    -------
    none

    """

    # load apron map
    color_image = bpy.data.images.load(parent + "/" + apron_file)

    # set platform
    platform_mesh = bpy.ops.mesh.primitive_plane_add(size=params.plane_size)
    bpy.context.active_object.name = name
    platform_obj = bpy.context.active_object
    platform_obj.scale = (platform_size_x, platform_size_y, 1)
    platform_obj.location = loc

    # edit platform material
    platform_mat = bpy.data.materials.new("platform_mat")
    platform_mat.use_nodes = True
    platform_obj.data.materials.append(platform_mat)

    # add image node - determines the color of the lanscape
    color_image_node = platform_mat.node_tree.nodes.new("ShaderNodeTexImage")
    # assign png to image to node
    color_image_node.image = color_image
    # change colorspace to b&w
    color_image_node.image.colorspace_settings.name = "sRGB"

    # connect nodes and change default values
    platform_mat.node_tree.links.new(
        color_image_node.outputs["Color"],
        platform_mat.node_tree.nodes["Principled BSDF"].inputs[0],
    )
    platform_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Roughness"
    ).default_value = 1.0
    platform_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Strength"
    ).default_value = 0.0
    platform_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "IOR"
    ).default_value = 1.0

    # organize nodes
    color_image_node.location.x, color_image_node.location.y = -500, 0
    platform_mat.node_tree.nodes["Principled BSDF"].location = (-100, 0)
    platform_mat.node_tree.nodes["Material Output"].location = (300, 0)


def get_v_scale(exaggeration, x_length, y_length, relief):
    """Calculates the vertical scale

    Parameters
    ----------
    exaggeration: string or float
        amount of exaggeration or "auto" to determine automatically
    x_length: float
        x-width of topography
    x_length: float
        y-width of topography
    relief: float
        relief of topography

    Returns
    -------
    v_scale: float
        total vertical height in blender space

    """
    # auto calculation of exaggeration
    if exaggeration == "auto":
        R = relief / np.sqrt(x_length * y_length)
        return (
            (1.0 + 4.0 * np.exp(-200.0 * R))
            * params.plane_size
            * relief
            / max(x_length, y_length)
        )
    else:
        return exaggeration * params.plane_size * relief / max(x_length, y_length)


def get_dimensions(dimensions_file, width, height):
    """Gets the dimensions of the topography

    Parameters
    ----------
    dimensions_file: string
        path dimensions of the topography from the process step

    Returns
    -------
    x_length: float
        x-width of topography
    x_length: float
        y-width of topography
    relief: float
        relief of topography

    """
    # dimensions if exists
    if dimensions_file != "NULL":
        dimensions = np.load(parent + "/" + dimensions_file)
        x_length = dimensions[0]
        y_length = dimensions[1]
        relief = dimensions[2]
    else:
        x_length = width
        y_length = height
        relief = 1.0  # if no dimensions given, relief is assumed to be equal to the exaggeration parameter

    return x_length, y_length, relief


def sample_texture_at_coords(displacement_image, width, height, norm_x, norm_y):
    """Gets an interpolated value from the displacement image

    Parameters
    ----------
    displacement_image: string
        path to the height map image
    width: int
        number of horizontal pixels in the image
    height: int
        number of vertical pixels in the image
    norm_x: float
        normalized x location on the height map
    norm_y: float
        normalized y location on the height map

    Returns
    -------
    z_height: float
        maximum pixel value of the surrounding four pixels at norm_x and norm_y

    """

    # change range from -0.5 to 0.5 to 0 to 1
    norm_x += 0.5
    norm_y += 0.5

    # change to pixel dimensions
    left = int(norm_x * width)
    lower = int(norm_y * height)
    right = left + 1
    upper = lower + 1

    # Get max of four pixels
    pixels = list(displacement_image.pixels)

    # just use R-band. R, G, and B are all the same because it's gray scale.
    index_ll = (lower * width + left) * 4  # 4 channels (RGBA)
    index_lr = (lower * width + right) * 4  # 4 channels (RGBA)
    index_ul = (upper * width + left) * 4  # 4 channels (RGBA)
    index_ur = (upper * width + right) * 4  # 4 channels (RGBA)

    # return the max
    return max(pixels[index_ll], pixels[index_lr], pixels[index_ul], pixels[index_ur])


def add_pin(
    norm_x, norm_y, dimensions_file, displacement_file, label, pin_color, label_color
):
    """Adds the pin and label to the blender scene

    Parameters
    ----------
    norm_x: float
        normalized x location on the height map
    norm_y: float
        normalized y location on the height map
    dimensions_file: string
        path to numpy array file containing the length, width, and height of topography
    displacement_file: string
        path to image file containing the height map
    label: string
        label of the pin
    pin_color: list of floats
        rgba of the pin
    label_color: list of floats
        rgba of the label

    Returns
    -------
    none

    """

    # Get the height of the plane at the (x, y) position
    displacement_image = bpy.data.images.load(parent + "/" + displacement_file)

    # Get the image data
    width, height = displacement_image.size

    # get dimensions of topography
    x_length, y_length, relief = get_dimensions(dimensions_file, width, height)

    # calculate vertical scale
    v_scale = get_v_scale(params.exaggeration, x_length, y_length, relief)

    # Sample the height from the texture
    z_height = (
        sample_texture_at_coords(displacement_image, width, height, norm_x, norm_y)
        * v_scale
    )

    # scale norm_x and norm_x to fit on the topography
    if width / height > 1.0:
        norm_y *= height / width
    else:
        norm_x *= width / height

    label_collection = bpy.data.collections.new(label)
    bpy.context.scene.collection.children.link(label_collection)

    pin_mesh = bpy.ops.mesh.primitive_cone_add(
        vertices=params.pin_sides,
        radius1=params.pin_radius1,
        radius2=params.pin_radius2,
        depth=params.pin_height,
        location=(norm_x, norm_y, z_height + params.pin_height / 2.0),
    )
    bpy.context.active_object.name = "Pin-" + label
    pin_obj = bpy.context.active_object

    # edit pin material
    pin_mat = bpy.data.materials.new("pin_mat")
    pin_mat.use_nodes = True
    pin_obj.data.materials.append(pin_mat)
    pin_mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = pin_color
    pin_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Roughness"
    ).default_value = 1.0
    pin_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Strength"
    ).default_value = 0.0
    pin_mat.node_tree.nodes["Principled BSDF"].inputs.get("IOR").default_value = 1.0

    # remove shadows and interaction with topography
    if params.shadow_boolean == False:
        pin_obj.visible_diffuse = False
        pin_obj.visible_glossy = False
        pin_obj.visible_transmission = False
        pin_obj.visible_volume_scatter = False
        pin_obj.visible_shadow = False

    # organize nodes
    pin_mat.node_tree.nodes["Principled BSDF"].location = (-100, 0)
    pin_mat.node_tree.nodes["Material Output"].location = (300, 0)

    # organize collection
    label_collection.objects.link(pin_obj)
    bpy.data.collections.get("Topographic Data").objects.unlink(pin_obj)

    # set label
    label_mesh = bpy.data.meshes.new("Label-" + label + "-mesh")
    label_obj = bpy.data.objects.new("Label-" + label, label_mesh)

    # set location
    label_obj.scale = (params.label_scale, params.label_scale, 1.0)
    label_obj.location = (norm_x, norm_y, z_height + params.pin_height)
    label_obj.rotation_euler = (np.radians(90.0), np.radians(0.0), np.radians(0.0))

    # edit label material
    label_mat = bpy.data.materials.new("Label-" + label + "-mat")
    label_mat.use_nodes = True
    label_obj.data.materials.append(label_mat)
    label_mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = label_color
    label_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Roughness"
    ).default_value = 1.0
    label_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Color"
    ).default_value = label_color
    label_mat.node_tree.nodes["Principled BSDF"].inputs.get(
        "Emission Strength"
    ).default_value = 2.5
    label_mat.node_tree.nodes["Principled BSDF"].inputs.get("IOR").default_value = 1.0

    # remove shadows and interaction with topography
    if params.shadow_boolean == False:
        label_obj.visible_diffuse = False
        label_obj.visible_glossy = False
        label_obj.visible_transmission = False
        label_obj.visible_volume_scatter = False
        label_obj.visible_shadow = False

    # make modifier
    label_mod = label_obj.modifiers.new("Label-" + label + "-mod", "NODES")

    # Create a new node tree for the modifier
    node_group = bpy.data.node_groups.new(
        "Label-" + label + "-tree", "GeometryNodeTree"
    )
    label_mod.node_group = node_group

    # Setup output
    node_group.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    output_node = node_group.nodes.new(type="NodeGroupOutput")

    # string nodes
    string2curve = label_mod.node_group.nodes.new(type="GeometryNodeStringToCurves")
    fillcurve = label_mod.node_group.nodes.new(type="GeometryNodeFillCurve")
    setmaterial = label_mod.node_group.nodes.new(type="GeometryNodeSetMaterial")

    # add label
    string2curve.inputs["String"].default_value = label
    if bpy.app.version <= (5, 1, 0):  # new font socket in 5.1
        string2curve.inputs["Align Y"].default_value = "Bottom"
        string2curve.inputs["Align X"].default_value = "Center"
    else:
        string2curve.align_y = "BOTTOM"
        string2curve.align_x = "CENTER"
    try:
        font = bpy.data.fonts.load(
            "fonts/" + params.label_font.replace(" ", "_") + ".ttf"
        )
        if bpy.app.version <= (5, 1, 0):  # new font socket in 5.1
            string2curve.inputs["Font"].default_value = font
        else:
            string2curve.font = font
    except:
        print("using default font")

    # add material
    setmaterial.inputs["Material"].default_value = label_mat

    # connect nodes
    label_mod.node_group.links.new(
        string2curve.outputs["Curve Instances"], fillcurve.inputs["Curve"]
    )
    label_mod.node_group.links.new(
        fillcurve.outputs["Mesh"], setmaterial.inputs["Geometry"]
    )
    label_mod.node_group.links.new(
        setmaterial.outputs["Geometry"], output_node.inputs["Geometry"]
    )

    # organize nodes
    output_node.location = (700, 0)
    setmaterial.location = (300, 0)
    fillcurve.location = (-100, 0)
    string2curve.location = (-500, 0)

    # apply modifier
    bpy.ops.object.modifier_apply(modifier="Label-" + label + "-mod")
    # organize collection
    label_collection.objects.link(label_obj)
