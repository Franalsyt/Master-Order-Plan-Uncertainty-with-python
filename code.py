# ============================================================
# ASSEMBLE-TO-ORDER (ATO) STOCHASTIC OPTIMIZATION MODEL
# ============================================================
#
# This script:
# 1. Loads supply chain data from Excel
# 2. Solves a stochastic ATO optimization model with Gurobi
# 3. Evaluates solutions out-of-sample
# 4. Runs sensitivity analysis on lead-time variability
# 5. Produces visual analysis plots
#
# ============================================================

# ============================================================
# IMPORTS
# ============================================================

import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


# ============================================================
# 1. VISUALIZE INITIAL DATA
# ============================================================

def plot_initial_data(file_path="DATA_ATO.xlsx"):
    """
    Create a dashboard showing the initial supply chain data.

    The dashboard contains:
    - Demand evolution
    - Holding costs
    - Bill of Materials structure
    - Lead-time uncertainty distributions
    """

    FILE = Path(file_path)

    if not FILE.exists():
        print(f"File not found: {FILE.resolve()}")
        return

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    hold_df = pd.read_excel(FILE, sheet_name="Holding costs")
    lt_df   = pd.read_excel(FILE, sheet_name="Lead Times Distirbution")
    bom_df  = pd.read_excel(FILE, sheet_name="BOM")
    dem_df  = pd.read_excel(FILE, sheet_name="Demand")

    # --------------------------------------------------------
    # SETUP FIGURE
    # --------------------------------------------------------

    plt.style.use("seaborn-v0_8-whitegrid")

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    fig.suptitle(
        "Supply Chain Context: Assemble-To-Order Data",
        fontsize=20,
        fontweight="bold"
    )

    # ========================================================
    # PLOT 1 — DEMAND FORECAST
    # ========================================================

    ax1 = axes[0, 0]

    dem_plot = (
        dem_df
        .set_index("End-item\\period")
        .iloc[:5]
        .T
    )

    dem_plot.plot(
        kind="line",
        marker="o",
        linewidth=2,
        ax=ax1,
        colormap="tab10"
    )

    ax1.set_title("1. Market Demand Forecast")
    ax1.set_xlabel("Week")
    ax1.set_ylabel("Demand")

    # ========================================================
    # PLOT 2 — HOLDING COSTS
    # ========================================================

    ax2 = axes[0, 1]

    hold_df["Component"] = hold_df["Component"].astype(str)

    sns.barplot(
        data=hold_df,
        x="Component",
        y="holding costs",
        ax=ax2,
        palette="Blues_d"
    )

    ax2.set_title("2. Component Holding Costs")
    ax2.set_xlabel("Component")
    ax2.set_ylabel("Cost")

    # ========================================================
    # PLOT 3 — BILL OF MATERIALS
    # ========================================================

    ax3 = axes[1, 0]

    bom_plot = bom_df.set_index("Component\\End-item")
    bom_plot.index = bom_plot.index.astype(str)

    sns.heatmap(
        bom_plot,
        cmap="YlGnBu",
        annot=True,
        cbar=False,
        ax=ax3,
        linewidths=0.5
    )

    ax3.set_title("3. Bill of Materials")
    ax3.set_xlabel("End-item")
    ax3.set_ylabel("Component")

    # ========================================================
    # PLOT 4 — LEAD-TIME DISTRIBUTIONS
    # ========================================================

    ax4 = axes[1, 1]

    lt_plot = (
        lt_df
        .set_index("Component\\Lead time")
        .iloc[:5]
        .T
    )

    lt_plot.plot(
        kind="bar",
        ax=ax4,
        colormap="Set2",
        edgecolor="black"
    )

    ax4.set_title("4. Lead-Time Probability Distributions")
    ax4.set_xlabel("Lead Time")
    ax4.set_ylabel("Probability")

    plt.tight_layout()
    plt.show()


# ============================================================
# 2. STOCHASTIC ATO OPTIMIZATION MODEL (MK2)
# ============================================================

def solve_ato_modelMK2(
    hold_df,
    lt_df,
    bom_df,
    dem_df,
    n_scen,
    min_weeks_met,
    time_limit,
    is_stochastic=True
):
    """
    Solve the stochastic Assemble-To-Order optimization problem.

    Goal:
    Minimize expected inventory holding costs while ensuring
    enough weeks achieve full service.

    The same order plan must work across all stochastic scenarios.
    """

    # ========================================================
    # SETS
    # ========================================================

    # Components
    J = hold_df["Component"].astype(int).tolist()

    # End-items
    K = [c for c in bom_df.columns if c != "Component\\End-item"]

    # Time periods
    T = [int(c) for c in dem_df.columns if c != "End-item\\period"]

    # Order periods
    T_ord = list(range(1, max(T) + 1))

    # ========================================================
    # PARAMETERS
    # ========================================================

    # Holding cost for each component
    H = {
        int(r["Component"]): float(r["holding costs"])
        for _, r in hold_df.iterrows()
    }

    # BOM coefficients
    # a[j,k] = quantity of component j required for end-item k
    a = {
        (int(r["Component\\End-item"]), k): float(r[k])
        for _, r in bom_df.iterrows()
        for k in K
    }

    # Demand
    # D[k,i] = demand of end-item k in period i
    D = {
        (r["End-item\\period"], i): float(r[i])
        for _, r in dem_df.iterrows()
        for i in T
    }

    # Component consumption implied by demand
    # Cons[j,i] = total usage of component j during period i
    Cons = {
        (j, i): sum(a[(j, k)] * D[(k, i)] for k in K)
        for j in J
        for i in T
    }

    # ========================================================
    # LEAD-TIME DISTRIBUTIONS
    # ========================================================

    lead_cols = [
        int(c)
        for c in lt_df.columns
        if c != "Component\\Lead time"
    ]

    # P[(j,l)] = probability that component j has lead time l
    P = {}

    for _, r in lt_df.iterrows():

        j = int(r["Component\\Lead time"])

        probs = np.array(
            [float(r[l]) for l in lead_cols],
            dtype=float
        )

        # Normalize probabilities
        probs = probs / probs.sum()

        for l, p in zip(lead_cols, probs):
            P[(j, l)] = p

    # ========================================================
    # BIG-M VALUES
    # ========================================================

    # Used for backlog/binary linking constraints
    M = {
        (j, i): max(1.0, Cons[(j, i)])
        for j in J
        for i in T
    }

    # ========================================================
    # SCENARIO GENERATION
    # ========================================================

    if is_stochastic:

        # Fixed random seed for reproducibility
        rng = np.random.default_rng(42)

        # Generate random lead-time scenarios
        L_scen = [
            {
                (j, t): int(
                    rng.choice(
                        lead_cols,
                        p=[P[(j, l)] for l in lead_cols]
                    )
                )
                for j in J
                for t in T_ord
            }
            for _ in range(n_scen)
        ]

        actual_n_scen = n_scen

    else:

        # Deterministic version:
        # use the most likely lead time (mode)
        mode_lt = {
            j: max(
                lead_cols,
                key=lambda l: P.get((j, l), 0)
            )
            for j in J
        }

        L_scen = [
            {
                (j, t): mode_lt[j]
                for j in J
                for t in T_ord
            }
        ]

        actual_n_scen = 1

    # Equal scenario probability
    p_w = 1.0 / actual_n_scen

    # ========================================================
    # BUILD GUROBI MODEL
    # ========================================================

    with gp.Env(empty=True) as env:

        # Disable solver logs
        env.setParam("OutputFlag", 0)

        env.start()

        with gp.Model("ATO_MK2", env=env) as model:

            # Solver time limit
            model.Params.TimeLimit = time_limit

            # =================================================
            # DECISION VARIABLES
            # =================================================

            # X[j,t]
            # Quantity ordered for component j at week t
            X = model.addVars(
                J,
                T_ord,
                lb=0,
                name="X"
            )

            # Y[w,j,i]
            # Inventory level at end of week i
            Y = model.addVars(
                actual_n_scen,
                J,
                [0] + T,
                lb=0,
                name="Y"
            )

            # B[w,j,i]
            # Backlog / unmet demand
            B = model.addVars(
                actual_n_scen,
                J,
                T,
                lb=0,
                name="B"
            )

            # S[w,j,i]
            # Binary stockout indicator
            S = model.addVars(
                actual_n_scen,
                J,
                T,
                vtype=GRB.BINARY,
                name="S"
            )

            # Z[w,i]
            # 1 if ALL components satisfy demand in week i
            Z = model.addVars(
                actual_n_scen,
                T,
                vtype=GRB.BINARY,
                name="Z"
            )

            # W[i]
            # 1 if service target achieved for week i
            W = model.addVars(
                T,
                vtype=GRB.BINARY,
                name="W"
            )

            # =================================================
            # ARRIVAL FUNCTION
            # =================================================

            def arr_expr(w, j, i):
                """
                Quantity of component j arriving during week i
                in scenario w.
                """

                return gp.quicksum(
                    X[j, t]
                    for t in T_ord
                    if t + L_scen[w][(j, t)] == i
                )

            # =================================================
            # INVENTORY BALANCE CONSTRAINTS
            # =================================================

            for w in range(actual_n_scen):

                for j in J:

                    # Initial inventory
                    model.addConstr(
                        Y[w, j, 0] == 0
                    )

                    for i in T:

                        # Inventory balance equation
                        model.addConstr(
                            Y[w, j, i]
                            ==
                            Y[w, j, i - 1]
                            + arr_expr(w, j, i)
                            - Cons[(j, i)]
                            + B[w, j, i]
                        )

                        # Backlog upper bound
                        model.addConstr(
                            B[w, j, i]
                            <=
                            M[(j, i)] * S[w, j, i]
                        )

                        # Activate binary if backlog exists
                        model.addConstr(
                            B[w, j, i]
                            >=
                            1e-6 * S[w, j, i]
                        )

                # =================================================
                # SERVICE LOGIC
                # =================================================

                for i in T:

                    # If any component has stockout,
                    # Z cannot equal 1
                    for j in J:

                        model.addConstr(
                            Z[w, i]
                            <=
                            1 - S[w, j, i]
                        )

                    # If all S = 0, then Z = 1
                    model.addConstr(
                        Z[w, i]
                        >=
                        1 - gp.quicksum(
                            S[w, j, i]
                            for j in J
                        )
                    )

            # =================================================
            # SERVICE TARGET
            # =================================================

            for i in T:

                model.addConstr(
                    gp.quicksum(
                        p_w * Z[w, i]
                        for w in range(actual_n_scen)
                    )
                    >=
                    W[i]
                )

            # Minimum number of weeks that must achieve service
            model.addConstr(
                gp.quicksum(W[i] for i in T)
                >=
                min_weeks_met
            )

            # =================================================
            # OBJECTIVE FUNCTION
            # =================================================

            # Minimize expected holding cost
            model.setObjective(
                gp.quicksum(
                    p_w * H[j] * Y[w, j, i]
                    for w in range(actual_n_scen)
                    for j in J
                    for i in T
                ),
                GRB.MINIMIZE
            )

            # =================================================
            # SOLVE MODEL
            # =================================================

            model.optimize()

            # =================================================
            # EXTRACT RESULTS
            # =================================================

            if model.Status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:

                # Average inventory across scenarios
                stock = {
                    (j, i): np.mean([
                        Y[w, j, i].X
                        for w in range(actual_n_scen)
                    ])
                    for j in J
                    for i in T
                }

                # Cost contribution by component
                cost_breakdown = {
                    j: sum(
                        H[j] * stock.get((j, i), 0)
                        for i in T
                    )
                    for j in J
                }

                return {
                    "objective": model.ObjVal,

                    "orders": {
                        (j, t): X[j, t].X
                        for j in J
                        for t in T_ord
                    },

                    "service_weeks": {
                        i: W[i].X
                        for i in T
                    },

                    "stock": stock,

                    "cost_breakdown": cost_breakdown
                }

    return None


# ============================================================
# 3. VISUALIZE OPTIMIZATION RESULTS
# ============================================================

def plot_results(results):
    """
    Plot optimization outputs:
    - Order schedule
    - Inventory evolution
    - Service performance
    """

    orders_df = pd.Series(results["orders"]).unstack().fillna(0)

    stock_df = pd.Series(results["stock"]).unstack().fillna(0)

    service_s = pd.Series(results["service_weeks"])

    plt.style.use("seaborn-v0_8-whitegrid")

    fig = plt.figure(figsize=(16, 10))

    fig.suptitle(
        "Optimization Results",
        fontsize=20,
        fontweight="bold"
    )

    # ========================================================
    # LAYOUT
    # ========================================================

    ax1 = plt.subplot2grid((2, 2), (0, 0), colspan=2)

    ax2 = plt.subplot2grid((2, 2), (1, 0))

    ax3 = plt.subplot2grid((2, 2), (1, 1))

    # ========================================================
    # ORDER HEATMAP
    # ========================================================

    sns.heatmap(
        orders_df,
        cmap="Blues",
        annot=True,
        fmt=".0f",
        linewidths=1,
        ax=ax1
    )

    ax1.set_title("Optimal Order Schedule")

    # ========================================================
    # INVENTORY EVOLUTION
    # ========================================================

    for comp in range(1, 6):

        ax2.plot(
            stock_df.columns,
            stock_df.loc[comp],
            marker="o",
            linewidth=2,
            label=f"Comp {comp}"
        )

    ax2.set_title("Expected Inventory Levels")

    ax2.set_xlabel("Week")

    ax2.set_ylabel("Inventory")

    ax2.legend()

    # ========================================================
    # SERVICE ACHIEVEMENT
    # ========================================================

    colors = [
        "#27ae60" if val >= 0.99 else "#e74c3c"
        for val in service_s.values
    ]

    ax3.bar(
        service_s.index,
        service_s.values,
        color=colors,
        edgecolor="black"
    )

    ax3.set_title("Service Achievement")

    ax3.set_ylim(0, 1.2)

    plt.tight_layout()

    plt.show()


# ============================================================
# 4. OUT-OF-SAMPLE EVALUATION
# ============================================================

def evaluate_out_of_sample(
    hold_df,
    lt_df,
    bom_df,
    dem_df,
    optimized_orders,
    test_scen=500
):
    """
    Evaluate a fixed order plan on unseen scenarios.

    This estimates the TRUE expected performance of the policy.
    """

    # ========================================================
    # SETS
    # ========================================================

    J = hold_df["Component"].astype(int).tolist()

    K = [
        c for c in bom_df.columns
        if c != "Component\\End-item"
    ]

    T = [
        int(c)
        for c in dem_df.columns
        if c != "End-item\\period"
    ]

    T_ord = list(range(1, max(T) + 1))

    # ========================================================
    # PARAMETERS
    # ========================================================

    H = {
        int(r["Component"]): float(r["holding costs"])
        for _, r in hold_df.iterrows()
    }

    a = {
        (int(r["Component\\End-item"]), k): float(r[k])
        for _, r in bom_df.iterrows()
        for k in K
    }

    D = {
        (r["End-item\\period"], i): float(r[i])
        for _, r in dem_df.iterrows()
        for i in T
    }

    Cons = {
        (j, i): sum(a[(j, k)] * D[(k, i)] for k in K)
        for j in J
        for i in T
    }

    M = {
        (j, i): max(1.0, Cons[(j, i)])
        for j in J
        for i in T
    }

    # ========================================================
    # LEAD-TIME PROBABILITIES
    # ========================================================

    lead_cols = [
        int(c)
        for c in lt_df.columns
        if c != "Component\\Lead time"
    ]

    P = {}

    for _, r in lt_df.iterrows():

        j = int(r["Component\\Lead time"])

        probs = np.array(
            [float(r[l]) for l in lead_cols]
        )

        probs = probs / probs.sum()

        P.update({
            (j, l): p
            for l, p in zip(lead_cols, probs)
        })

    # ========================================================
    # GENERATE TEST SCENARIOS
    # ========================================================

    rng = np.random.default_rng(999)

    L_test = [
        {
            (j, t): int(
                rng.choice(
                    lead_cols,
                    p=[P[(j, l)] for l in lead_cols]
                )
            )
            for j in J
            for t in T_ord
        }
        for _ in range(test_scen)
    ]

    p_w = 1.0 / test_scen

    # ========================================================
    # BUILD EVALUATION MODEL
    # ========================================================

    with gp.Env(empty=True) as env:

        env.setParam("OutputFlag", 0)

        env.start()

        with gp.Model("Evaluate", env=env) as model:

            # =================================================
            # LOCK ORDER VARIABLES
            # =================================================

            X = model.addVars(
                J,
                T_ord,
                lb=0,
                ub=0,
                name="X"
            )

            # Fix each order variable to optimized value
            for j in J:
                for t in T_ord:

                    X[j, t].lb = optimized_orders[(j, t)]

                    X[j, t].ub = optimized_orders[(j, t)]

            # =================================================
            # OTHER VARIABLES
            # =================================================

            Y = model.addVars(
                test_scen,
                J,
                [0] + T,
                lb=0,
                name="Y"
            )

            B = model.addVars(
                test_scen,
                J,
                T,
                lb=0,
                name="B"
            )

            S = model.addVars(
                test_scen,
                J,
                T,
                vtype=GRB.BINARY,
                name="S"
            )

            Z = model.addVars(
                test_scen,
                T,
                vtype=GRB.BINARY,
                name="Z"
            )

            W = model.addVars(
                T,
                vtype=GRB.CONTINUOUS,
                name="W"
            )

            # =================================================
            # ARRIVAL FUNCTION
            # =================================================

            def arr_expr(w, j, i):

                return gp.quicksum(
                    X[j, t]
                    for t in T_ord
                    if t + L_test[w][(j, t)] == i
                )

            # =================================================
            # INVENTORY FLOW
            # =================================================

            for w in range(test_scen):

                for j in J:

                    model.addConstr(
                        Y[w, j, 0] == 0
                    )

                    for i in T:

                        model.addConstr(
                            Y[w, j, i]
                            ==
                            Y[w, j, i - 1]
                            + arr_expr(w, j, i)
                            - Cons[(j, i)]
                            + B[w, j, i]
                        )

                        model.addConstr(
                            B[w, j, i]
                            <=
                            M[(j, i)] * S[w, j, i]
                        )

                        model.addConstr(
                            B[w, j, i]
                            >=
                            1e-6 * S[w, j, i]
                        )

                # =================================================
                # SERVICE LOGIC
                # =================================================

                for i in T:

                    for j in J:

                        model.addConstr(
                            Z[w, i]
                            <=
                            1 - S[w, j, i]
                        )

                    model.addConstr(
                        Z[w, i]
                        >=
                        1 - gp.quicksum(
                            S[w, j, i]
                            for j in J
                        )
                    )

            # =================================================
            # SERVICE METRIC
            # =================================================

            for i in T:

                model.addConstr(
                    W[i]
                    ==
                    gp.quicksum(
                        p_w * Z[w, i]
                        for w in range(test_scen)
                    )
                )

            # =================================================
            # OBJECTIVE
            # =================================================

            model.setObjective(
                gp.quicksum(
                    p_w * H[j] * Y[w, j, i]
                    for w in range(test_scen)
                    for j in J
                    for i in T
                ),
                GRB.MINIMIZE
            )

            model.optimize()

            return (
                model.ObjVal,
                sum(W[i].X for i in T)
            )


# ============================================================
# 5. SENSITIVITY ANALYSIS
# ============================================================

def run_sensitivity_analysis(
    xls_file,
    n_scen,
    test_scen,
    min_weeks_met,
    time_limit,
    reduction_factor=0.5
):
    """
    Analyze the value of reducing lead-time variability.

    For each component:
    - reduce variability
    - re-optimize
    - evaluate out-of-sample
    - estimate expected savings
    """

    # ========================================================
    # LOAD DATA
    # ========================================================

    hold_df = pd.read_excel(
        xls_file,
        sheet_name="Holding costs"
    )

    lt_df_orig = pd.read_excel(
        xls_file,
        sheet_name="Lead Times Distirbution"
    )

    bom_df = pd.read_excel(
        xls_file,
        sheet_name="BOM"
    )

    dem_df = pd.read_excel(
        xls_file,
        sheet_name="Demand"
    )

    # ========================================================
    # COMPONENT LIST
    # ========================================================

    components_to_test = (
        hold_df["Component"]
        .astype(int)
        .tolist()
    )

    savings_per_component = {}

    # ========================================================
    # BASELINE OPTIMIZATION
    # ========================================================

    print("Calculating baseline solution...")

    baseline_results = solve_ato_modelMK2(
        hold_df,
        lt_df_orig,
        bom_df,
        dem_df,
        n_scen,
        min_weeks_met,
        time_limit,
        is_stochastic=True
    )

    if not baseline_results:
        raise RuntimeError(
            "Baseline optimization failed."
        )

    # ========================================================
    # BASELINE OUT-OF-SAMPLE EVALUATION
    # ========================================================

    print(
        f"Evaluating baseline on {test_scen} unseen scenarios..."
    )

    true_baseline_cost, _ = evaluate_out_of_sample(
        hold_df,
        lt_df_orig,
        bom_df,
        dem_df,
        baseline_results["orders"],
        test_scen
    )

    print(
        f"TRUE Baseline Cost = {true_baseline_cost:.2f}"
    )

    # ========================================================
    # SENSITIVITY LOOP
    # ========================================================

    n = len(components_to_test)

    for idx, comp_id in enumerate(components_to_test):

        print(
            f"\n[{idx+1}/{n}] Component {comp_id}"
        )

        # Copy original lead-time table
        lt_df_modified = lt_df_orig.copy(deep=True)

        # Select row for current component
        comp_row = lt_df_modified.loc[
            lt_df_modified["Component\\Lead time"]
            ==
            comp_id
        ]

        if comp_row.empty:

            print("Skipped")

            continue

        # ====================================================
        # REDUCE VARIABILITY
        # ====================================================

        prob_cols = [
            c for c in comp_row.columns
            if isinstance(c, int)
        ]

        probs = comp_row[prob_cols].iloc[0]

        # Most likely lead time
        mode_lt = probs.idxmax()

        prob_to_shift = 0

        # Reduce probability mass on non-mode values
        for lt in prob_cols:

            if lt != mode_lt:

                original_prob = comp_row.at[
                    comp_row.index[0],
                    lt
                ]

                shifted_prob = (
                    original_prob * reduction_factor
                )

                prob_to_shift += (
                    original_prob - shifted_prob
                )

                lt_df_modified.at[
                    comp_row.index[0],
                    lt
                ] = shifted_prob

        # Transfer removed probability mass to mode
        lt_df_modified.at[
            comp_row.index[0],
            mode_lt
        ] += prob_to_shift

        # ====================================================
        # RE-OPTIMIZE
        # ====================================================

        improved_results = solve_ato_modelMK2(
            hold_df,
            lt_df_modified,
            bom_df,
            dem_df,
            n_scen,
            min_weeks_met,
            time_limit,
            is_stochastic=True
        )

        if improved_results:

            # ================================================
            # OUT-OF-SAMPLE EVALUATION
            # ================================================

            true_improved_cost, _ = (
                evaluate_out_of_sample(
                    hold_df,
                    lt_df_modified,
                    bom_df,
                    dem_df,
                    improved_results["orders"],
                    test_scen
                )
            )

            # Expected savings
            savings = (
                true_baseline_cost
                -
                true_improved_cost
            )

            savings_per_component[comp_id] = savings

            print(
                f"TRUE Savings = {savings:.2f}"
            )

        else:

            print("Optimization failed")

        print(
            f"Progress: {100*(idx+1)/n:.1f}%"
        )

    return savings_per_component
