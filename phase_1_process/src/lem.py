import numpy as np
from landlab import RasterModelGrid
from landlab.components import (
    FlowAccumulator,
    LinearDiffuser,
    FastscapeEroder,
)
from landlab.io.netcdf import write_raster_netcdf
from phase_0_fetch.src.download_dem import snakemake_type_exists

def run_lem(U, K_sp, n_sp, m_sp, K_d, n_rows, n_cols, n_steps, dx, dt, dt_print, output_file):
    # Set up Grid
    grid = RasterModelGrid((n_rows, n_cols), xy_spacing=dx)

    # Set boundary conditions: open on all edges (fixed-value = 0 m)
    grid.set_closed_boundaries_at_grid_edges(
        right_is_closed=False,
        top_is_closed=False,
        left_is_closed=False,
        bottom_is_closed=False,
    )

    # Initial topography: small random noise to seed drainage network
    rng = np.random.default_rng(123)
    z = grid.add_zeros("topographic__elevation", at="node")
    z += rng.uniform(0, 0.1, size=z.shape)

    # Keep boundaries pinned at 0 m 
    z[grid.boundary_nodes] = 0.0 

    # landlab modules
    fa  = FlowAccumulator(grid, flow_director="FlowDirectorD8", depression_finder="DepressionFinderAndRouter",)
    sp = FastscapeEroder(grid, K_sp=K_sp, m_sp=m_sp, n_sp=n_sp)
    ld  = LinearDiffuser(grid, linear_diffusivity=K_d)
    
    for step in range(0, n_steps+1):

        # Save landscape
        if step%int(dt_print/dt) == 0:
            write_raster_netcdf(output_file,grid,
                append=(step > 0),time=step*dt,       
                names=["topographic__elevation", "drainage_area"],
                format="NETCDF4")

        grid.at_node['topographic__elevation'][grid.core_nodes] += dt * U
        fa.run_one_step()
        sp.run_one_step(dt)
        ld.run_one_step(dt)


if __name__ == "__main__":
    U = snakemake_type_exists(snakemake.params, "U", 0.001)
    K_sp = snakemake_type_exists(snakemake.params, "K_sp", 0.00001)
    n_sp = snakemake_type_exists(snakemake.params, "n_sp", 1.0)
    m_sp = snakemake_type_exists(snakemake.params, "m_sp", 0.5)
    K_d = snakemake_type_exists(snakemake.params, "K_d", 0.01)

    n_rows = snakemake_type_exists(snakemake.params, "n_rows", 200)
    n_cols = snakemake_type_exists(snakemake.params, "n_cols", 200)
    n_steps = snakemake_type_exists(snakemake.params, "n_cols", 1000)

    dx = snakemake_type_exists(snakemake.params, "dx", 100.0)
    dt = snakemake_type_exists(snakemake.params, "dt", 1000.0)
    num_frames = snakemake_type_exists(snakemake.params, "num_frames", 10)
    dt_print = int(n_steps / num_frames) * dt

    output_file = snakemake.output["output_file"]

    run_lem(U, K_sp, n_sp, m_sp, K_d, n_rows, n_cols, n_steps, dx, dt, dt_print, output_file)