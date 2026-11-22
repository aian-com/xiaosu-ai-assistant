from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app import dev


@pytest.mark.parametrize("enabled,count", [(True, 6), (False, 4)])
def test_start_and_stop_all_services(monkeypatch, enabled, count):
    monkeypatch.setattr(dev, "get_settings", lambda: SimpleNamespace(
        dingtalk_client_id="test" if enabled else "",
        dingtalk_client_secret=SimpleNamespace(get_secret_value=lambda: "test")))
    monkeypatch.setattr(dev.shutil, "which", lambda _: "node")
    monkeypatch.setattr(dev.Path, "is_file", lambda _: True)
    children = []
    def spawn(command, **kwargs):
        child = Mock(pid=100 + len(children))
        child.poll.return_value = None
        children.append((command, child))
        return child
    monkeypatch.setattr(dev.subprocess, "Popen", spawn)
    stop = Mock()
    monkeypatch.setattr(dev.subprocess, "run", stop)
    monkeypatch.setattr(dev.os, "killpg", stop, raising=False)
    def interrupt(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(dev.time, "sleep", interrupt)
    dev.main()
    assert len(children) == count
    assert stop.call_count == count
    assert all(child.wait.called for _, child in children)
    if enabled:
        assert any("app.im.worker" in command for command, _ in children)
        assert any("im_local.py" in command for command, _ in children)
