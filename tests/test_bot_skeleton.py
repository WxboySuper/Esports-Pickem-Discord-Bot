import importlib
import pkgutil
import pytest
import inspect


def test_commands_package_importable():
    """The src.commands package should be importable and have a __path__."""
    import src.commands as commands_pkg

    assert hasattr(commands_pkg, "__path__")


def test_each_command_module_has_setup():
    """Each command module in src.commands should define a setup() function."""
    import src.commands as commands_pkg

    failures = []
    for module_info in pkgutil.iter_modules(commands_pkg.__path__):
        name = module_info.name
        if name.startswith("_"):
            continue
        full_name = f"{commands_pkg.__name__}.{name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception as e:
            failures.append(f"import failed: {full_name}: {e}")
            continue
        if not hasattr(mod, "setup"):
            failures.append(f"no setup(): {full_name}")
    assert not failures, "Module issues:\n" + "\n".join(failures)


def test_bot_can_instantiate(monkeypatch):
    """Bot class can instantiate with minimal env (no crash)."""
    # Patch env so DISCORD_TOKEN is present
    monkeypatch.setenv("DISCORD_TOKEN", "dummy")
    from src.app import EsportsBot

    bot = EsportsBot()
    assert bot is not None


@pytest.mark.asyncio
async def test_ping_command_loads(monkeypatch):
    """
    Checks that the ping command cog can be loaded without error.
    Properly awaits async setup functions to avoid warnings.
    """
    monkeypatch.setenv("DISCORD_TOKEN", "dummy")
    from src.app import EsportsBot

    bot = EsportsBot()
    import src.commands.ping as ping_mod

    setup_fn = getattr(ping_mod, "setup", None)
    assert setup_fn is not None

    if inspect.iscoroutinefunction(setup_fn):
        await setup_fn(bot)
    else:
        setup_fn(bot)
