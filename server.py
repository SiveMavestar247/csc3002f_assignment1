"""Entry point for the chat server.  The implementation has been
refactored into :mod:`server.core.ChatServer` to keep the public
interface small and easy to reason about.
"""

from server.core import ChatServer


if __name__ == "__main__":
    srv = ChatServer(host="0.0.0.0")
    srv.start()
