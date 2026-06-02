import importlib

import pytest


@pytest.fixture
def reloadable_config():
    import app.core.config as config

    original_settings = config.settings
    yield config
    config.settings = original_settings


def test_account_budget_defaults(monkeypatch, reloadable_config):
    monkeypatch.delenv("ACTUAL_CASH_ACCOUNT_OFFBUDGET", raising=False)
    monkeypatch.delenv("ACTUAL_DEPOT_ACCOUNT_OFFBUDGET", raising=False)

    reloaded = importlib.reload(reloadable_config)

    assert reloaded.settings.actual_cash_account_offbudget is False
    assert reloaded.settings.actual_depot_account_offbudget is True


def test_account_budget_env_overrides(monkeypatch, reloadable_config):
    monkeypatch.setenv("ACTUAL_CASH_ACCOUNT_OFFBUDGET", "true")
    monkeypatch.setenv("ACTUAL_DEPOT_ACCOUNT_OFFBUDGET", "false")

    reloaded = importlib.reload(reloadable_config)

    assert reloaded.settings.actual_cash_account_offbudget is True
    assert reloaded.settings.actual_depot_account_offbudget is False
