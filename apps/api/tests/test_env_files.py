from edd_platform_api import main


def test_load_env_files_skips_dotenv_in_e2e(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setenv("EDD_PLATFORM_E2E", "1")

    main.load_env_files()

    assert calls == []


def test_load_env_files_lets_env_local_override_outside_e2e(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.delenv("EDD_PLATFORM_E2E", raising=False)

    main.load_env_files()

    assert calls == [{}, {"override": True}]


def test_pytest_session_does_not_load_env_files(monkeypatch):
    # conftest.py must keep the dev .env.local (found by walking up from a
    # worktree) out of the test process.
    calls = []
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: calls.append(kwargs))

    main.load_env_files()

    assert calls == []
