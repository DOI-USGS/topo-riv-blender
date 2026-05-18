import os
import geopandas as gpd
from osgeo import gdal, osr
import numpy as np
import matplotlib.pyplot as plt
import xarray as xr

from phase_0_fetch.src.download_dem import (
    get_shapefile_extent,
    buffer_shapefile,
    snakemake_type_exists,
)
from phase_1_process.src.process_functions import (
    get_raster_extent,
    clean_border,
    fig_setup,
    make_custom_cmap,
    truncate_colormap,
)

gdal.UseExceptions()


def setup_lem_blender_data(
        lem_file,
        topo_cmap,
        background_color,
        wall_color,
        wall_thickness,
        river_color,
        min_res,
        dimensions_file,
        heightmap_files,
        texturemap_files,
        apronmap_file,
):
    """Sets up the texture and height maps for blender to render. It will create
    an apronmap.png that determines the background in the render, a dimensions.npy
    file that details the geometry of the landscape, a heightmap.png that quantifies
    the topography, and a texturemap.png that determine the color of the topography.
    Modified for LEM output from landlab

    Parameters
    ----------
    map_crs: string
        coordinate reference system to use for the maps
    demfile: string
        path of the dem file
    topo_cmap: matplotlib cmap
        cmap to use on the topography
    background_color: rgba list
        color of the background
    wall_color: rgba list
        color of the wall of the dem
    wall_thickness: float
        thickness of the wall of the dem
    river_color: rgba list
        color of the rivers
    min_res: int
        minimum pixel resolution of the short side of the image
    dimensions_file: string
        path to the file containing the length, width, and height of the landscape
    heightmap_file: string
        path to the image file showing the height map
    texturemap_file: string
        path to the image file showing the texture map
        list of paths to the texture maps for the additional layers
    apronmap_file: string
        path to the image file showing the texture map of the background

    Returns
    -------
    none

    """

    # Make out_dir if it doesn't exist
    out_dir = os.path.dirname(dimensions_file)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Default fig size in inches, 10 in, dpi
    fig_width = 10.0
    dpi = min_res / fig_width
    buffer = 0.01

    ds = xr.open_dataset(lem_file)
    final_dem = ds["topographic__elevation"].isel(nt=-1).values
    min_dem, max_dem = np.min(final_dem), np.max(final_dem)
    x = ds["x"].values
    y = ds["y"].values
    extent = [x.min(), x.max(), y.min(), y.max()]
    width = x.max() - x.min()
    height = y.max() - y.min()

    # Make heightmap figure
    fig_heightmap = plt.figure(1, figsize = (fig_width, fig_width * (y.max() - y.min()) / (x.max() - x.min())), facecolor = 'k')
    fig_texturemap = plt.figure(2, figsize = (fig_width, fig_width * (y.max() - y.min()) / (x.max() - x.min())), facecolor = background_color)

    for i in range(len(ds["t"])):
        # Extract the elevation at this timestep as a 2D numpy array
        topo = ds["topographic__elevation"].isel(nt=i).values
        area = ds["drainage_area"].isel(nt=i).values

        # Make the Axis
        ax_heightmap = fig_heightmap.add_axes([0, 0, 1, 1])

        # Set bounds
        ax_heightmap.set_aspect("equal")
        ax_heightmap.set_xlim(x.min() - buffer * width, x.max() + buffer * width)
        ax_heightmap.set_ylim(y.min() - buffer * height, y.max() + buffer * height)

        # Remove axis labels and ticks
        ax_heightmap.axis("off")

        # Create a height map with raw data
        ax_heightmap.imshow(
            topo,
            extent=extent,
            cmap=plt.get_cmap("gray", 2**16),
            vmin=min_dem,
            vmax=max_dem,
        )

        # Save the height map
        fig_heightmap.savefig(heightmap_files[i], dpi=dpi)
        ax_heightmap.remove()

        # Make the Axis
        ax_texturemap = fig_texturemap.add_axes([0, 0, 1, 1])

        # Set bounds
        ax_texturemap.set_aspect("equal")
        ax_texturemap.set_xlim(x.min(), x.max())
        ax_texturemap.set_ylim(y.min(), y.max())

        # Remove axis labels and ticks
        ax_texturemap.axis("off")

        ax_texturemap.imshow(
            topo,
            extent=extent,
            cmap=topo_cmap,
            vmin=min_dem,
            vmax=max_dem,
            zorder=1,
        )

        # Draw a line around the extent that's the color of the wall
        ax_texturemap.plot(
            [x.min(),x.max(),x.max(),x.min(),x.min()],
            [y.min(),y.min(),y.max(),y.max(),y.min()],
            alpha=1.0,
            color=wall_color,
            linewidth=wall_thickness,
            solid_capstyle="round",
            zorder=3,
        )

        # Save the texture map
        # Save the height map
        fig_texturemap.savefig(texturemap_files[i], dpi=dpi)
        ax_texturemap.remove()

    # Make apron texture map, this is the background area in the render
    fig_apronmap = plt.figure(3, figsize = (fig_width, fig_width * (y.max() - y.min()) / (x.max() - x.min())), facecolor = background_color)
    fig_apronmap.savefig(apronmap_file, dpi=dpi)

    # Calculate the relief of the topography
    relief = max_dem - min_dem

    # Dimensions of topography
    dimensions = np.array([width * (1.0 + 2.0 * buffer), height * (1.0 + 2.0 * buffer), relief])

    # Save the dimensions for use in the Blender render
    np.save(dimensions_file, dimensions)

if __name__ == "__main__":
    # Gather the Snakemake Parameters
    map_crs = snakemake_type_exists(snakemake.params, "map_crs", "NULL")
    topo_cmap = snakemake_type_exists(snakemake.params, "topo_cmap", "copper")
    topo_cstops = snakemake_type_exists(
        snakemake.params, "topo_cstops", [[0, 0, 0], [255, 255, 255]]
    )
    topo_cmap_vlim = snakemake_type_exists(
        snakemake.params, "topo_cmap_vlim", [0.0, 1.0]
    )
    topo_nstops = snakemake_type_exists(snakemake.params, "topo_nstops", [])
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
    min_res = snakemake_type_exists(snakemake.params, "min_res", 2000)

    # Gather the Snakemake Inputs
    lem_file = snakemake.input["lem_file"]

    # Gather the Snakemake Outputs
    dimensions_file = snakemake.output["dimensions_file"]
    heightmap_files = snakemake.output["heightmap_files"]
    texturemap_files = snakemake.output["texturemap_files"]
    apronmap_file = snakemake.output["apronmap_file"]

    # making a custom topo cmap
    if topo_cmap == "custom":
        topo_cmap = make_custom_cmap(topo_cstops, topo_nstops)
    else:
        if topo_cmap_vlim[0] != 0.0 or topo_cmap_vlim[1] != 1.0:
            topo_cmap = truncate_colormap(
                topo_cmap, minval=topo_cmap_vlim[0], maxval=topo_cmap_vlim[1]
            )

    setup_lem_blender_data(
        lem_file,
        topo_cmap,
        background_color,
        wall_color,
        wall_thickness,
        river_color,
        min_res,
        dimensions_file,
        heightmap_files,
        texturemap_files,
        apronmap_file,
    )
