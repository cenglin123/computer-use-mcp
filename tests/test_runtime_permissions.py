"""Tests for runtime permission store."""
from __future__ import annotations

import pytest
from computer_use.runtime_permissions import (
    grant_command_permission,
    check_command_permission,
    consume_command_permission,
    grant_window_exception,
    check_window_exception,
    consume_window_exception,
    save_permanent_command,
    clear_runtime_permissions,
    list_runtime_permissions,
)


@pytest.fixture(autouse=True)
def _clean_runtime_state():
    clear_runtime_permissions()
    yield
    clear_runtime_permissions()


class TestCommandPermissions:
    def test_once_grant_and_consume(self):
        grant_command_permission("C:/app/app.exe", "once")
        assert check_command_permission("C:/app/app.exe") is True
        consume_command_permission("C:/app/app.exe")
        assert check_command_permission("C:/app/app.exe") is False

    def test_once_not_consumed_before_explicit_call(self):
        grant_command_permission("C:/app/app.exe", "once")
        assert check_command_permission("C:/app/app.exe") is True
        assert check_command_permission("C:/app/app.exe") is True  # still valid
        consume_command_permission("C:/app/app.exe")
        assert check_command_permission("C:/app/app.exe") is False

    def test_session_grant_persists(self):
        grant_command_permission("C:/app/app.exe", "session")
        assert check_command_permission("C:/app/app.exe") is True
        consume_command_permission("C:/app/app.exe")  # no-op for session
        assert check_command_permission("C:/app/app.exe") is True

    def test_normalized_path_matching(self):
        grant_command_permission("C:/App/App.exe", "session")
        assert check_command_permission("c:\\app\\app.exe") is True

    def test_basename_matching_for_name_only_grants(self):
        grant_command_permission("notepad.exe", "session")
        assert check_command_permission("notepad.exe") is True
        assert check_command_permission("C:/Windows/System32/notepad.exe") is True

    def test_unknown_command_not_granted(self):
        assert check_command_permission("C:/unknown.exe") is False

    def test_consume_non_existent_is_noop(self):
        consume_command_permission("C:/nonexistent.exe")  # should not raise

    def test_clear_runtime_permissions(self):
        grant_command_permission("cmd.exe", "session")
        grant_command_permission("calc.exe", "once")
        clear_runtime_permissions()
        assert check_command_permission("cmd.exe") is False
        assert check_command_permission("calc.exe") is False

    def test_list_permissions(self):
        grant_command_permission("cmd.exe", "session")
        grant_command_permission("calc.exe", "once")
        perms = list_runtime_permissions()
        assert len(perms) == 2
        names = {p["name"] for p in perms}
        assert names == {"cmd.exe", "calc.exe"}


class TestWindowExceptions:
    def test_once_window_exception(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="once")
        assert check_window_exception("saplogon.exe", "#32770") is True
        consume_window_exception("saplogon.exe", "#32770")
        assert check_window_exception("saplogon.exe", "#32770") is False

    def test_session_window_exception(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
        consume_window_exception("saplogon.exe", "#32770")  # no-op for session
        assert check_window_exception("saplogon.exe", "#32770") is True

    def test_window_exception_class_only(self):
        grant_window_exception(class_name="#32770", level="session")
        assert check_window_exception("any.exe", "#32770") is True
        assert check_window_exception("other.exe", "#32770") is True

    def test_window_exception_process_specific(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
        assert check_window_exception("other.exe", "#32770") is False

    def test_window_exception_case_insensitive(self):
        grant_window_exception(process_name="SAPLOGON.EXE", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
