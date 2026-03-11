"""Top-level package for the chat application's GUI.

Provides a simple ``run()`` entry point that launches the login screen and
starts the Tk event loop.  Other modules under :mod:`gui` contain
implementation details for the various pieces of the interface.
"""

from . import state
from .login import setup_login_window


def run():
    """Start the GUI application from the very beginning."""
    setup_login_window()
    if state.root is not None:
        state.root.mainloop()


# we also re-export some commonly used names so that scripts can import
# from ``gui`` rather than digging into the submodules.
from .state import chat_client, current_user, current_chat_contact
from .callbacks import handle_incoming_message, handle_network_error, handle_user_list_update
from .main_app import open_main_app
