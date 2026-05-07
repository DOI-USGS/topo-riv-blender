import os, importlib
import geopandas as gpd
from osgeo import gdal, osr
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from shapely.geometry import Polygon

from phase_0_fetch.src.download_dem import (
    get_shapefile_extent,
    buffer_shapefile,
    snakemake_type_exists,
)
from phase_1_process.src.process_functions import (
    get_raster_extent,
    clean_border,
    fig_setup,
    project,
    contour,
    make_labels_file,
    make_custom_cmap,
    truncate_colormap,
)

gdal.UseExceptions()


def setup_blender_data(
    map_crs,
    demfile,
    aerialfiles,
    layerfiles,
    extent_shpfile,
    waterbody_shpfile,
    flowlines_shpfile,
    labels_shpfile,
    ocean_boolean,
    ocean_elevation,
    ocean_color,
    mask_boolean,
    custom_min_dem,
    contour_boolean,
    contour_levels,
    convolution_coarsen,
    convolution_stdddev,
    buffer,
    topo_cmap,
    oceanfloor_cmap,
    layers_cmap,
    layers_vlim,
    background_color,
    wall_color,
    wall_thickness,
    river_color,
    river_width,
    river_width_coefficient,
    river_scale_boolean,
    river_scale_coefficient,
    waterbody_colors,
    min_res,
    dimensions_file,
    heightmap_file,
    texturemap_file,
    heightmap_layerfiles,
    texturemap_layerfiles,
    apronmap_file,
    labels_file,
):
    """Sets up the texture and height maps for blender to render. It will create
    an apronmap.png that determines the background in the render, a dimensions.npy
    file that details the geometry of the landscape, a heightmap.png that quantifies
    the topography, and a texturemap.png that determine the color of the topography.

    Parameters
    ----------
    map_crs: string
        coordinate reference system to use for the maps
    demfile: string
        path of the dem file
    aerialfiles: list of strings
        list of the paths of the aerial imagery r, g, b bands, used if provided
    *EXPERIMENTAL* layerfiles: string
        list of paths to additional layer files to be rendered
    extent_shpfile: string
        path of the extent shapefile
    waterbody_shpfile: string
        path of the waterbody shapefile
    flowlines_shpfile: string
        path of the flowline shapefile
    labels_shpfile: string
        path of the labels shapefile
    ocean_boolean: boolean
        allow for ocean, which causes a splitting of the dual-cmap around ocean elevation
    ocean_elevation: float
        elevation of the ocean
    ocean_color: rgba list
        color of the ocean
    mask_boolean: boolean
        option to mask out topography outside the shapefile's extent
    custom_min_dem: float
        value to modify minimum of the DEM color scale.
    contour_boolean: boolean
        option to contour the topography
    contour_levels: int
        number of contour levels
    convolution_coarsen: float
        divisor that coarsens the data for contouring
    convolution_stdddev: float
        standard deviation in grid-lengths for applying the convolution filter
    buffer: float
        a percent buffer around the extent; maintains original aspect
    topo_cmap: matplotlib cmap
        cmap to use on the topography
    oceanfloor_cmap: matplotlib cmap
        cmap to use on the ocean floor
    *EXPERIMENTAL* layers_cmap: list of matplotlib cmap
        cmaps to use for each layer
    *EXPERIMENTAL* layers_vlim: list of 2 element lists
        list of the min and max values for the color maps for each layer
    background_color: rgba list
        color of the background
    wall_color: rgba list
        color of the wall of the dem
    wall_thickness: float
        thickness of the wall of the dem
    river_color: rgba list
        color of the rivers
    river_width: float
        width of the river
    river_width_coefficient: float
        coefficient in the auto river width algorithm, default is 2.2
    river_width_coefficient: float
        coefficient in the auto river width algorithm for scaling rivers based on stream order, default is 0.5
    waterbody_colors: list of colors (named color strings, hexcodes, or rgba tuples)
        list of colors of the waterbodies: playa, icemass, lakepond, reservoir, swampmarsh, esturary
    min_res: int
        minimum pixel resolution of the short side of the image
    dimensions_file: string
        path to the file containing the length, width, and height of the landscape
    heightmap_file: string
        path to the image file showing the height map
    texturemap_file: string
        path to the image file showing the texture map
    *EXPERIMENTAL* heightmap_layerfiles: list of strings
        list of paths to the height maps for the additional layers
    *EXPERIMENTAL* texturemap_layerfiles:  list of strings
        list of paths to the texture maps for the additional layers
    apronmap_file: string
        path to the image file showing the texture map of the background
    labels_file: string
        path to the labels file with a list of the coordinates and labels

    Returns
    -------
    none

    """

    # Make out_dir if it doesn't exist
    out_dir = os.path.dirname(dimensions_file)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Make tmp_dir if it doesn't exist
    tmp_dir = out_dir.replace("/out", "/tmp")
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    # If not MAP CRS is given, get UTM zone closest to the extentn shapefile for reprojection
    if map_crs == "NULL":
        map_crs = gpd.read_file(extent_shpfile).estimate_utm_crs()

    # Read in the dem as a numpy array
    proj_dem, proj_ds, min_dem, max_dem, nan_dem = project(demfile, map_crs, tmp_dir)

    # custom min_dem
    if custom_min_dem != "NULL":
        min_dem_cmap = min_dem  # save min_dem of domain for cmap
        min_dem = custom_min_dem

    # Load extent shapefile
    extent_shp = gpd.read_file(extent_shpfile).to_crs(map_crs)

    # Get the boundaries of the extent files assuming a map_crs
    west, east, length, south, north, height = get_shapefile_extent(extent_shp)

    # Buffer those boundaries (expand) using a user-defined buffering percentage
    # 5x multiplier makes sure this buffer contains all the data
    buff_west, buff_east, buff_south, buff_north = buffer_shapefile(
        west, east, length, south, north, height, buffer * 5.0
    )

    # Create a polygon from the bounding box
    domain_geom = Polygon(
        zip(
            [buff_west, buff_west, buff_east, buff_east, buff_west],
            [buff_north, buff_south, buff_south, buff_north, buff_north],
        )
    )

    # Create a geopandas dataframe from the polygon and set the CRS to map_crs
    domain_polygon = gpd.GeoDataFrame(index=[0], crs=map_crs, geometry=[domain_geom])

    # Mask outside of the extent
    if mask_boolean == True:
        # Invert extent to make mask
        mask = domain_polygon.difference(extent_shp)
    else:
        # Use total extent as mask
        mask = domain_polygon

    # Load flowlines if exists
    if flowlines_shpfile != "NULL":
        flowlines = gpd.read_file(flowlines_shpfile).to_crs(map_crs)
        if flowlines.empty == False:
            flowlines["geometry"] = flowlines.make_valid()
            flowlines = gpd.clip(flowlines, extent_shp)

    # Load waterbody is exists
    if waterbody_shpfile != "NULL":
        waterbody = gpd.read_file(waterbody_shpfile).to_crs(map_crs)
        if waterbody.empty == False:
            waterbody["geometry"] = waterbody.make_valid()
            waterbody = gpd.clip(waterbody, extent_shp)

    # If there is ocean in the domain, we will splice together two colormaps
    # One for the topography and one for the ocean floor.
    # Blender has issues when geometries intersect, so for better render results
    # The topography is bumped 1.5 bits upwards and the ocean is bumped 1.5 bits downwards.
    if ocean_boolean == True:

        # With ocean_boolean, a 2nd layer at elevation = 0.0 m will be made, followed by the layer files
        files = [demfile] + ["OCEAN"] + layerfiles

        # Modify dem to prevent overlap
        overlap_prevention = 1.5 / 256.0  # move by 1.5 values within 8-bit

        # Move ocean floor down and mountains up
        proj_dem_bath = proj_dem
        proj_dem_bath[proj_dem <= ocean_elevation] -= type(proj_dem_bath[0, 0])(
            overlap_prevention * (max_dem - min_dem)
        )
        proj_dem_bath[proj_dem > ocean_elevation] += type(proj_dem_bath[0, 0])(
            overlap_prevention * (max_dem - min_dem)
        )

        # Determine how much proportion of the relief is above ground
        proportion_above_ground = (max_dem - ocean_elevation) / (max_dem - min_dem)

        if proportion_above_ground < 0.0 or proportion_above_ground > 1.0:
            import sys

            sys.exit(
                "Check the 'ocean_elevation' parameter. It does not lie between the minimum and maximum elevations of the DEM."
            )

        # 8 bit portion below water
        cmap1_length = 256 - int(round(proportion_above_ground * 256))
        # 8 bit portion above water
        cmap2_length = int(round(proportion_above_ground * 256))
        # Get color data from ocean floow cmap
        oceanfloor_cmap_data = plt.get_cmap(oceanfloor_cmap)
        # Get color data from topography cmap
        topo_cmap_data = plt.get_cmap(topo_cmap)

        # Set two cmap-cmap
        colors1 = oceanfloor_cmap_data(np.linspace(0.0, 1.0, cmap1_length))
        colors2 = topo_cmap_data(np.linspace(0.0, 1.0, cmap2_length))

        # Combine them and build a new colormap
        colors = np.vstack((colors1, colors2))

        # Update the new topo_cmap
        topo_cmap = mcolors.LinearSegmentedColormap.from_list("my_colormap", colors)

        # make an ocean cmap
        ocean_cmap = mcolors.ListedColormap([ocean_color])

        # Make a list of the cmaps and output texture and height map file locations
        cmaps = [topo_cmap] + [ocean_cmap] + layers_cmap
        hgtmap_files = (
            [heightmap_file] + [heightmap_file[:-4] + "_L0.png"] + heightmap_layerfiles
        )
        txtmap_files = (
            [texturemap_file]
            + [texturemap_file[:-4] + "_L0.png"]
            + texturemap_layerfiles
        )
    else:

        # If there is no ocean region, the files are just the dem file followed by any layer files
        files = [demfile] + layerfiles

        # Make a list of the cmaps and output texture and height map file locations
        cmaps = [topo_cmap] + layers_cmap
        hgtmap_files = [heightmap_file] + heightmap_layerfiles
        txtmap_files = [texturemap_file] + texturemap_layerfiles

    # Iterated through the files, dems, oceans, and additional layers
    for i, file in enumerate(files):

        # Layer setup for DEM
        if file == demfile:

            # Use modified DEM to prevent overlap
            if ocean_boolean == True:
                proj_layer = proj_dem_bath

            # Use unmodified DEM
            else:
                proj_layer = proj_dem

            # Get the min and max values for the dem
            if custom_min_dem == "NULL":
                min_layer = min_dem
            else:
                min_layer = min_dem_cmap
            max_layer = max_dem

            # Modify the layer to have contours if specified
            if contour_boolean == True:
                proj_layer = contour(
                    proj_ds, proj_layer, convolution_coarsen, convolution_stdddev
                )

            # load aerial imagery if it exists:
            if aerialfiles != "NULL":
                # Project red band
                proj_aerial_r, proj_aerial_r_ds, min_aerial_r, max_aerial_r, nan_r = (
                    project(aerialfiles[0], map_crs, tmp_dir)
                )
                # Project green band
                proj_aerial_g, proj_aerial_g_ds, min_aerial_g, max_aerial_g, nan_g = (
                    project(aerialfiles[1], map_crs, tmp_dir)
                )
                # Project blue band
                proj_aerial_b, proj_aerial_b_ds, min_aerial_b, max_aerial_b, nan_b = (
                    project(aerialfiles[2], map_crs, tmp_dir)
                )

                # Convert NaN to min value
                proj_aerial_r[proj_aerial_r == nan_r] = min_aerial_r
                proj_aerial_g[proj_aerial_g == nan_g] = min_aerial_g
                proj_aerial_b[proj_aerial_b == nan_b] = min_aerial_b

                # make rgb array
                # Scale the rgb bands from their minimum to maximum value to aid in viewing
                proj_aerial_rgb = np.stack(
                    (
                        (proj_aerial_r - min_aerial_r) / (max_aerial_r - min_aerial_r),
                        (proj_aerial_g - min_aerial_g) / (max_aerial_g - min_aerial_g),
                        (proj_aerial_b - min_aerial_b) / (max_aerial_b - min_aerial_b),
                    ),
                    axis=-1,
                )

        # Layer setup for ocean, EXPERIMENTAL
        elif file == "OCEAN":

            # Create a layer at zero elevation
            proj_layer = np.ones_like(proj_dem) * ocean_elevation

            # Get the min and max values for the ocean layer
            min_layer = 0.0
            max_layer = 1.0

        # Layer setup for layer files
        else:

            # Project additional layer
            proj_layer, proj_layer_ds, min_layer, max_layer, nan_layer = project(
                file, map_crs, tmp_dir
            )

            # Overwrite default min and max layer is specified by the user
            if layers_vlim:
                if layers_vlim[i - 1] != "NULL":
                    min_layer = layers_vlim[i - 1][0]
                    max_layer = layers_vlim[i - 1][1]

            # Modify the layer is the same way as the DEM if ocean_boolean is selected
            if ocean_boolean == True:
                proj_layer[proj_layer <= 0.0] -= type(proj_layer[0, 0])(
                    overlap_prevention * (max_dem - min_dem)
                )
                proj_layer[proj_layer > 0.0] += type(proj_layer[0, 0])(
                    overlap_prevention * (max_dem - min_dem)
                )

        # Make height map figure starting at 2 and subsequent even numbers
        fig_heightmap, ax_heightmap, dpi_heightmap = fig_setup(
            2 + i * 2, mask, min_res, "k"
        )

        # Create a height map using contours
        if contour_boolean == True and file == demfile:
            ax_heightmap.contourf(
                proj_layer,
                extent=list(get_raster_extent(proj_ds)),
                levels=contour_levels,
                cmap="gray",
                vmin=min_dem,
                vmax=max_dem,
                origin="upper",
            )

        # Create a height map with raw data
        else:
            ax_heightmap.imshow(
                proj_layer,
                extent=list(get_raster_extent(proj_ds)),
                cmap="gray",
                vmin=min_dem,
                vmax=max_dem,
            )

        # Mask area outside the extent
        if mask_boolean == True:
            # Mask outside
            mask.plot(ax=ax_heightmap, alpha=1.0, facecolor="k", edgecolor="none")

            # Draw a black line on the edges to clean up render
            clean_border(
                ax_heightmap,
                buff_west,
                buff_east,
                buff_south,
                buff_north,
                "k",
                1.0,
                map_crs,
            )

        # Save the height map
        fig_heightmap.savefig(hgtmap_files[i], dpi=dpi_heightmap)

        # Make texture map figure starting at 3 and subsequent odd numbers
        fig_texturemap, ax_texturemap, dpi_texturemap = fig_setup(
            3 + i * 2, mask, min_res, background_color
        )

        # Create a texture map using contours
        if contour_boolean == True and file == demfile:
            ax_texturemap.contourf(
                proj_layer,
                extent=list(get_raster_extent(proj_ds)),
                levels=contour_levels,
                cmap=cmaps[i],
                vmin=min_layer,
                vmax=max_layer,
                origin="upper",
            )

        elif aerialfiles != "NULL" and file == demfile:
            ax_texturemap.imshow(
                proj_aerial_rgb,
                extent=list(get_raster_extent(proj_aerial_b_ds)),
                origin="upper",
            )

        # Create a texture map with raw data
        else:
            ax_texturemap.imshow(
                proj_layer,
                extent=list(get_raster_extent(proj_ds)),
                cmap=cmaps[i],
                vmin=min_layer,
                vmax=max_layer,
                zorder=1,
            )

        # Draw Flowlines
        if flowlines_shpfile != "NULL":
            # Get minimum stream order
            if river_scale_boolean == True:
                min_stream_order = flowlines["StreamOrde"].min()
                river_scale = np.exp(
                    (flowlines["StreamOrde"] - min_stream_order)
                    * river_scale_coefficient
                )
            else:
                river_scale = 1.0

            # Automatic NHD drawing parameters
            if river_width == "auto":
                flowlines.plot(
                    ax=ax_texturemap,
                    color=river_color,
                    linewidth=river_width_coefficient
                    * np.exp(
                        -0.00001
                        * np.sqrt((buff_east - buff_west) * (buff_north - buff_south))
                    )
                    * river_scale,
                    zorder=2,
                )

            # User-specified NHD drawing parameters
            else:
                flowlines.plot(
                    ax=ax_texturemap, color=river_color, linewidth=river_width, zorder=2
                )

        # Draw water bodies
        if waterbody_shpfile != "NULL" and waterbody.empty == False:
            # FTYPE codes for Playa, Ecemass, LakePond, Reservior, SwampMarsh, Esturary
            FTYPE_codes = [361, 378, 390, 436, 466, 493]

            # Subset the waterbody geodatabase to the FTYPE codes and color accordingly
            for waterbody_int, waterbody_color in enumerate(waterbody_colors):
                sub_waterbody = waterbody[
                    waterbody["FTYPE"] == FTYPE_codes[waterbody_int]
                ]
                if sub_waterbody.empty == False:
                    sub_waterbody.plot(
                        ax=ax_texturemap, color=waterbody_color, linewidth=0, zorder=2
                    )

        # Mask area outside the extent
        if mask_boolean == True:

            # Mask outside
            mask.plot(
                ax=ax_texturemap,
                alpha=background_color[-1],
                facecolor=background_color,
                edgecolor="none",
                zorder=3,
            )

            # Draw a background-colored line on the edges to clean up render
            clean_border(
                ax_texturemap,
                buff_west,
                buff_east,
                buff_south,
                buff_north,
                background_color,
                1.0,
                map_crs,
            )

            # Draw a line around the extent that's the color of the wall
            extent_shp.plot(
                ax=ax_texturemap,
                alpha=1.0,
                facecolor="none",
                edgecolor=wall_color,
                linewidth=wall_thickness,
                capstyle="round",
                zorder=4,
            )

        # Save the texture map
        fig_texturemap.savefig(txtmap_files[i], dpi=dpi_texturemap)

    # Make apron texture map, this is the background area in the render
    fig_apronmap, ax_apronmap, dpi_apronmap = fig_setup(
        1, mask, min_res, background_color
    )

    # Save the apron texture map
    fig_apronmap.savefig(apronmap_file, dpi=dpi_apronmap)

    # Calculate the relief of the topography
    relief = max_dem - min_dem

    # Dimensions of topography
    dimensions = np.array([buff_east - buff_west, buff_north - buff_south, relief])

    # Save the dimensions for use in the Blender render
    np.save(dimensions_file, dimensions)

    # Save labels file if it exists
    if labels_shpfile != "NULL":
        make_labels_file(
            labels_shpfile, labels_file, list(get_raster_extent(proj_ds)), map_crs
        )


if __name__ == "__main__":
    # Gather the Snakemake Parameters
    map_crs = snakemake_type_exists(snakemake.params, "map_crs", "NULL")
    mask_boolean = snakemake_type_exists(snakemake.params, "mask_boolean", True)
    ocean_boolean = snakemake_type_exists(snakemake.params, "ocean_boolean", False)
    ocean_elevation = snakemake_type_exists(snakemake.params, "ocean_elevation", 0.0)
    ocean_color = snakemake_type_exists(
        snakemake.params, "ocean_color", [0.1294, 0.2275, 0.3608, 1.0]
    )
    custom_min_dem = snakemake_type_exists(snakemake.params, "custom_min_dem", "NULL")
    contour_boolean = snakemake_type_exists(snakemake.params, "contour_boolean", False)
    contour_levels = snakemake_type_exists(snakemake.params, "contour_levels", 20)
    convolution_coarsen = snakemake_type_exists(
        snakemake.params, "convolution_coarsen", 5.0
    )
    convolution_stdddev = snakemake_type_exists(
        snakemake.params, "convolution_stddev", 2.0
    )
    buffer = snakemake_type_exists(snakemake.params, "buffer", 0.0)
    topo_cmap = snakemake_type_exists(snakemake.params, "topo_cmap", "copper")
    topo_cstops = snakemake_type_exists(
        snakemake.params, "topo_cstops", [[0, 0, 0], [255, 255, 255]]
    )
    topo_cmap_vlim = snakemake_type_exists(
        snakemake.params, "topo_cmap_vlim", [0.0, 1.0]
    )
    topo_nstops = snakemake_type_exists(snakemake.params, "topo_nstops", [])
    layers_vlim = snakemake_type_exists(snakemake.params, "layers_vlim", [])
    layers_cmap = snakemake_type_exists(snakemake.params, "layers_cmap", [])
    oceanfloor_cmap = snakemake_type_exists(
        snakemake.params, "oceanfloor_cmap", "Greys"
    )
    background_color = snakemake_type_exists(
        snakemake.params, "background_color", [0.5, 0.5, 0.5, 1.0]
    )
    wall_color = snakemake_type_exists(
        snakemake.params, "wall_color", [0.2, 0.133, 0.0667, 1.0]
    )
    wall_thickness = snakemake_type_exists(snakemake.params, "wall_thickness", 1.0)
    river_color = snakemake_type_exists(
        snakemake.params, "river_color", [0.1294, 0.2275, 0.3608, 1.0]
    )
    river_width = snakemake_type_exists(snakemake.params, "river_width", "auto")
    river_width_coefficient = snakemake_type_exists(
        snakemake.params, "river_width_coefficient", 2.2
    )
    river_scale_boolean = snakemake_type_exists(
        snakemake.params, "river_scale_boolean", False
    )
    river_scale_coefficient = snakemake_type_exists(
        snakemake.params, "river_scale_coefficient", 0.25
    )
    waterbody_colors = snakemake_type_exists(
        snakemake.params,
        "waterbody_colors",
        [
            (0.824, 0.706, 0.549, 0.75),
            (1.0, 1.0, 1.0, 0.75),
            river_color,
            river_color,
            "#3a4c40",
            river_color,
        ],
    )
    min_res = snakemake_type_exists(snakemake.params, "min_res", 2000)

    # Gather the Snakemake Inputs
    extent_shpfile = snakemake.input["extent_shpfile"]
    demfile = snakemake.input["demfile"]
    aerialfiles = snakemake_type_exists(snakemake.input, "aerialfiles", "NULL")
    flowlines_shpfile = snakemake_type_exists(
        snakemake.input, "flowlines_shpfile", "NULL"
    )
    waterbody_shpfile = snakemake_type_exists(
        snakemake.input, "waterbody_shpfile", "NULL"
    )
    layerfiles = snakemake_type_exists(snakemake.input, "layerfiles", [])
    labels_shpfile = snakemake_type_exists(snakemake.input, "labels_shpfile", "NULL")

    # Gather the Snakemake Outputs
    dimensions_file = snakemake.output["dimensions_file"]
    heightmap_file = snakemake.output["heightmap_file"]
    texturemap_file = snakemake.output["texturemap_file"]
    apronmap_file = snakemake.output["apronmap_file"]
    heightmap_layerfiles = snakemake_type_exists(
        snakemake.output, "heightmap_layerfiles", []
    )
    texturemap_layerfiles = snakemake_type_exists(
        snakemake.output, "texturemap_layerfiles", []
    )
    labels_file = snakemake_type_exists(snakemake.output, "labels_file", "NULL")

    # making a custom topo cmap
    if topo_cmap == "custom":
        topo_cmap = make_custom_cmap(topo_cstops, topo_nstops)
    else:
        if topo_cmap_vlim[0] != 0.0 or topo_cmap_vlim[1] != 1.0:
            topo_cmap = truncate_colormap(
                topo_cmap, minval=topo_cmap_vlim[0], maxval=topo_cmap_vlim[1]
            )

    setup_blender_data(
        map_crs,
        demfile,
        aerialfiles,
        layerfiles,
        extent_shpfile,
        waterbody_shpfile,
        flowlines_shpfile,
        labels_shpfile,
        ocean_boolean,
        ocean_elevation,
        ocean_color,
        mask_boolean,
        custom_min_dem,
        contour_boolean,
        contour_levels,
        convolution_coarsen,
        convolution_stdddev,
        buffer,
        topo_cmap,
        oceanfloor_cmap,
        layers_cmap,
        layers_vlim,
        background_color,
        wall_color,
        wall_thickness,
        river_color,
        river_width,
        river_width_coefficient,
        river_scale_boolean,
        river_scale_coefficient,
        waterbody_colors,
        min_res,
        dimensions_file,
        heightmap_file,
        texturemap_file,
        heightmap_layerfiles,
        texturemap_layerfiles,
        apronmap_file,
        labels_file,
    )
