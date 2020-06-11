import time
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd
from scipy import sparse as sps

from .sklearn_fork import (
    GeneralizedLinearRegressor,
    GeneralizedLinearRegressorCV,
    TweedieDistribution,
)
from .util import benchmark_convergence_tolerance, runtime

random_seed = 110


def build_and_fit(model_args, fit_args, cv: bool):
    if cv:
        return GeneralizedLinearRegressorCV(**model_args).fit(**fit_args)
    return GeneralizedLinearRegressor(**model_args).fit(**fit_args)


def sklearn_fork_bench(
    dat: Dict[str, Union[np.ndarray, sps.spmatrix]],
    distribution: str,
    alpha: float,
    l1_ratio: float,
    iterations: int,
    cv: bool,
    print_diagnostics: bool = True,
    reg_multiplier: Optional[float] = None,
    **kwargs,
):
    result = dict()

    X = dat["X"]
    fit_args = dict(X=X, y=dat["y"])
    if "weights" in dat.keys():
        fit_args.update({"sample_weight": dat["weights"]})
    if "offset" in dat.keys():
        fit_args.update({"offset": dat["offset"]})

    family = distribution
    if family == "gaussian":
        family = "normal"
    elif "tweedie" in family:
        tweedie_p = float(family.split("-p=")[1])
        family = TweedieDistribution(tweedie_p)  # type: ignore

    model_args = dict(
        family=family,
        l1_ratio=l1_ratio,
        max_iter=1000,
        random_state=random_seed,
        copy_X=False,
        selection="cyclic",
        # TODO: try tightening this later
        gradient_tol=1 if cv else benchmark_convergence_tolerance,
        step_size_tol=0.01 * benchmark_convergence_tolerance,
        force_all_finite=False,
    )
    if not cv:
        model_args["alpha"] = (
            alpha if reg_multiplier is None else alpha * reg_multiplier
        )

    model_args.update(kwargs)

    result["runtime"], m = runtime(build_and_fit, iterations, model_args, fit_args, cv)

    result["intercept"] = m.intercept_
    result["coef"] = m.coef_
    result["n_iter"] = m.n_iter_
    if cv:
        alphas: np.ndarray = m.alphas_
        result["n_alphas"] = len(alphas)
        result["max_alpha"] = alphas.max()
        result["min_alpha"] = alphas.min()
        result["best_alpha"] = m.alpha_

    if print_diagnostics:
        with pd.option_context(
            "display.expand_frame_repr", False, "max_columns", None, "max_rows", None
        ):
            m.report_diagnostics()
    return result


def compute_path(niters, model_args, fit_args):
    step_model_args = model_args.copy()
    step_model_args["max_iter"] = 1
    step_model_args["warm_start"] = True
    m = GeneralizedLinearRegressor(**step_model_args)
    path = []
    for i in range(niters):
        start = time.time()
        m.fit(**fit_args)
        print(time.time() - start)
        path.append(m.coef_.copy())
    return path