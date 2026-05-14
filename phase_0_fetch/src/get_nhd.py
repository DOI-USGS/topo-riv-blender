import os
import geopandas as gpd
from pynhd import NHD
from phase_0_fetch.src.download_dem import (
    snakemake_type_exists,
    get_shapefile_extent,
    estimate_area,
)


def determine_nhd_product(nhd_type, west, east, south, north, render_pixels):
    """Automatically determine nhd type based on the size of the extent and the number of pixels in the final render

    Parameters
    ----------
    west: float
        west long coordinate
    east: float
        east long coordinate
    south: float
        south lat coordinate
    north: float
        north lat coordinate
    render_pixels: int
        number of pixels in the final render image, used to determine the dem resolution

    Returns
    -------
    nhd_type: string
        automated name of the nhd product

    """

    area_m_per_pixel = estimate_area(west, east, south, north, render_pixels)

    # USGS-3DEP-10m threshold, if smaller use HR
    if area_m_per_pixel < 900.0:
        return nhd_type[:-4] + "hr"
    else:
        return nhd_type[:-4] + "mr"


def nhd_download(nhd_type, extent_shpfile, nhd_shpfile, render_pixels):
    """Downloads nhd data (.shp) according to an extent shapefile

    Parameters
    ----------
    nhd_type: string
        name of the nhd product
    extent_shpfile: string
        path of of the extent shapefile
    nhd_shpfile: string
        path of of the nhd shapefile to be outputted
    render_pixels: int
        number of pixels in the final render image, used to determine the dem resolution

    Returns
    -------
    none

    """

    # Make out_dir if it doesn't exist
    out_dir = os.path.dirname(nhd_shpfile)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Load extent shapefile, ensure it's in geographic coordinates
    extent = gpd.read_file(extent_shpfile).to_crs("EPSG:4326")

    # Determine NHD product automatically
    if nhd_type.endswith("auto") == True:

        # Get the boundaries of the extent files assuming a WGS84 CRS
        west, east, length, south, north, height = get_shapefile_extent(extent)

        # Determine NHD resolution
        auto_nhd_type = determine_nhd_product(
            nhd_type, west, east, south, north, render_pixels
        )

        # Set up NHD
        hr = NHD(auto_nhd_type)

    # Use user-specified NHD product
    else:

        # Set up NHD
        hr = NHD(nhd_type)

    try:
        # Download NHD
        nhdp_hr = hr.bygeom(extent.geometry[0].bounds)

    except:
        print ("no nhd data found")
        nhdp_hr = gpd.GeoDataFrame(columns=["id", "geometry"], geometry="geometry", crs="EPSG:4326")

    # Save NHD data as a shapefile
    nhdp_hr.to_file(nhd_shpfile)


if __name__ == "__main__":
    nhd_type = snakemake_type_exists(snakemake.params, "nhd_type", "flowline_mr")
    render_pixels = snakemake_type_exists(snakemake.params, "render_pixels", 1)
    extent_shpfile = snakemake.input["extent_shpfile"]
    nhd_shpfile = snakemake.output["nhd_shpfile"]
    nhd_download(nhd_type, extent_shpfile, nhd_shpfile, render_pixels)
