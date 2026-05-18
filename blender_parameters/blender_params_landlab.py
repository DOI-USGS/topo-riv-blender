# For more details about the parameters, please refer to the README in the Github repository:
# https://github.com/DOI-USGS/topo-riv-blender/blob/main/README.md

########## data management ##########
# OpenTopography Products: https://portal.opentopography.org/apidocs/
dem_product = "auto"  # determine automatically (see options here: https://portal.opentopography.org/apidocs/#/)

# NHD products
nhd_flowline = "flowline_auto"  # use auto, mr, or hr
nhd_waterbody = "waterbody_auto"  # use auto, mr, or hr

# Data Buffer
buffer = 1.0  # percent buffer space around watershed

########## map visualization ##########
background_color = [0.5, 0.5, 0.5, 1.0]  # rgba color of the background
wall_color = [0.1, 0.1, 0.01, 1.0]  # rgba color of the wall edge
river_color = [0.1294, 0.2275, 0.3608, 1.0]  # rgba color of the rivers
topo_cmap = "terrain"  # color map of the topography, choose others here: https://matplotlib.org/stable/users/explain/colors/colormaps.html

########## render hardware ##########
GPU_boolean = False  # if you have a GPU, set this to 1 and this will run faster

########## blender scene ##########
# max dimension of plane
plane_size = 1.0  # meters, size of topography. Tt can be anything, but you need to position your camera accordingly.

########## additional data layers ##########
number_of_layers = 0  # number of additional data layers

########## camera settings ##########
# color management
view_transform = "Filmic"  # 'Standard'
exposure = -0.35  # default is 0, -2.0 to 2.0 will make image lighter to darker
gamma = 0.5 # default is 1, 0.25 to 2.0 will make the shadow areas lighter to darker

# camera type
camera_type = "orthogonal"  # orthogonal or perspective

# orthogonal
ortho_scale = 1.45  # when using orthogonal scale, increase to "zoom" out

# perspective
focal_length = 50.0  # mm when using perspective camera, increase to zoom in

# camera location
camera_distance = 1.0  # meters from the center (maximum horizontal axis is assumed to be 1 meter), this needs to be a similar value to the plane_size.
camera_tilt = (
    45.0  # degrees from horizontal: 0.0 is profile view, 90.0 is planform view
)
camera_rotation = 135.0  # camera location degrees clockwise from North: 0.0 is North, 90.0 is East, 180.0, is South, and 270.0 is West.
shift_x = 0.0  # you may need to shift the camera to center the topo in the frame, use small increments like 0.01
shift_y = 0.0  # you may need to shift the camera to center the topo in the frame, use small increments like 0.01

# depth of field
use_depth_of_field = (
    False  # makes things fuzzy when objects are away from the focal plane
)
dof_distance = camera_distance  # where the focal plane is
f_stop = 100.0  # affects depths of field, lower for a shallow dof, higher for wide dof

########## sun properties ##########
sun_tilt = 20.0  # degrees from horizontal
sun_rotation = 225.0  # degrees clockwise from North
sun_intensity = 0.5  # sun intensity, use small increments like 0.1 to adjust
sun_strength = 1.0  # sun strength, use small increments like 0.1 to adjust

########## landscape representation ###########
min_res = 2000  # minimum resolution of the heightmap, larger value increases detail but takes longer to render
number_of_subdivisions = 2000  # number of subdivisions, larger value increases detail but takes longer to render
exaggeration = 3.0  # vertical exaggeration
displacement_method = "DISPLACEMENT"  # "BOTH" #for more exaggerated shadows

########## render settings ##########
res_x = 2000  # x resolution of the render, larger value increases detail but takes longer to render
res_y = 1600  # y resolution of the render, larger value increases detail but takes longer to render
samples = 10  # number of samples that decides how "good" the render looks, larger value increases detail but takes longer to render
