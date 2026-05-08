import numpy as np
from landlab import RasterModelGrid
from landlab.components import (
    FlowAccumulator,
    LinearDiffuser,
    FastscapeEroder,
)

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
fa  = FlowAccumulator(grid, flow_director="FlowDirectorSteepest")
sp = FastscapeEroder(grid, K_sp=K_sp, m_sp=m_sp, n_sp=n_sp)
ld  = LinearDiffuser(grid, linear_diffusivity=K_d)


snapshots = []          # list of (time_yr, elevation_array)
times_kyr = []

print(f"Running {N_STEPS} steps  ({TOTAL_TIME/1e6:.1f} Myr) …")

for step in range(N_STEPS):

    # 1. Uplift interior nodes
    interior = grid.core_nodes
    z[interior] += UPLIFT_RATE * DT

    # 2. Route flow and accumulate drainage area
    fa.run_one_step()

    # 3. Fluvial incision
    spe.run_one_step(DT)

    # 4. Hillslope diffusion
    ld.run_one_step(DT)

    # 5. Keep base-level nodes at 0 m
    z[grid.boundary_nodes] = 0.0

    # Save snapshots
    if (step + 1) % SNAPSHOT_STEPS == 0:
        t_kyr = (step + 1) * DT / 1_000
        snapshots.append((t_kyr, z.copy()))
        times_kyr.append(t_kyr)
        print(f"  t = {t_kyr/1e3:.2f} Myr  |  max elev = {z.max():.1f} m")


if __name__ == "__main__":
    U = snakemake_type_exists(snakemake.params, "U", 0.001)
    K_sp = snakemake_type_exists(snakemake.params, "K_sp", 0.00001)
    n_sp = snakemake_type_exists(snakemake.params, "n_sp", 1.0)
    m_sp = snakemake_type_exists(snakemake.params, "m_sp", 0.5)
    K_d = snakemake_type_exists(snakemake.params, "d", 0.01)

    n_rows = snakemake_type_exists(snakemake.params, "n_rows", 250)
    n_cols = snakemake_type_exists(snakemake.params, "n_cols", 250)

    dx = snakemake_type_exists(snakemake.params, "dx", 100.0)
    dt = snakemake_type_exists(snakemake.params, "dt", 1000.0)