import numpy as np
import pytest

from app.check_clinic_csv import bootstrap_uncertainty


def test_bootstrap_reproducible_finite_and_capacity_bounded():
    x = np.arange(56, dtype=float).reshape(-1, 1)
    y = 2 + x[:, 0] / 20 + np.sin(x[:, 0])
    future = np.arange(56, 66, dtype=float).reshape(-1, 1)
    capacities = np.array([8] * 9 + [0])
    result = bootstrap_uncertainty(x, y, future, capacities, draws=80)
    assert result == bootstrap_uncertainty(x, y, future, capacities, draws=80)
    assert np.array(result["coefficient_intervals"]).shape == (2, 2)
    for key in ("mean_intervals", "prediction_intervals"):
        values = np.array(result[key])
        assert values.shape == (10, 2)
        assert np.isfinite(values).all()
        assert (values[:, 0] <= values[:, 1]).all()
        assert (values >= 0).all() and (values <= capacities[:, None]).all()
        assert list(values[-1]) == [0, 0]
    lo, hi = result["monthly_prediction_interval"]
    assert 0 <= lo <= hi <= sum(capacities)


def test_exact_linear_history_has_no_residual_noise():
    x = np.arange(28, dtype=float).reshape(-1, 1)
    result = bootstrap_uncertainty(x, 3 + 2 * x[:, 0], [[28], [29]], [100, 100], draws=30)
    assert np.allclose(result["prediction_intervals"], [[59, 59], [61, 61]])
    assert np.allclose(result["coefficient_intervals"], [[3, 3], [2, 2]])
    with pytest.raises(ValueError):
        bootstrap_uncertainty([[1], [2]], [1, 2], [[3]], [10])
