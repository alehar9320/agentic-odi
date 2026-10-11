import socket

from client.run import is_port_in_use


def test_is_port_in_use_detects_bound_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        s.listen(1)
        port = s.getsockname()[1]

        assert is_port_in_use(port) is True


def test_is_port_in_use_returns_false_for_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    assert is_port_in_use(port) is False
