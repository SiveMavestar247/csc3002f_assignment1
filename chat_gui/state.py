"""Shared state and widget references for the GUI package.

Rather than scattering a long list of ``global`` declarations across
different modules we centralise them here; other parts of the code
import this module and update or read the attributes as necessary.
"""

import tkinter as tk

from client import ChatClient

# network client singleton
chat_client = ChatClient()

# Tkinter widgets that are shared across modules
root: tk.Tk | None = None          # login window
entry_username: tk.Entry | None = None

# application state
current_user: str | None = None                 # User currently logged in
current_chat_contact: str | None = None         # User currently chatting to
current_chat_is_group: bool = False             # Whether current chat is a group or user
scrollable_contacts: tk.Frame | None = None     # Contact list frame
online_users: list[str] = []                    # Current list of online users

gui_ready: bool = False                   # Flag set when GUI is fully initialised
pending_user_list: list[str] | None = None            # Store pending user list update
pending_group_list: list[tuple[str, list[str]]] | None = None  # Store pending group list update

# Group management
groups: dict[str, list[str]] = {}               # group_name -> list of members
lbl_chat_subtitle: tk.Label | None = None      # For showing group members

# Containers / frames used by chat views
chat_frames: dict[str, tuple] = {}                    # contact/group -> (scrollable_chat, chat_canvas)
chat_containers: dict[str, tk.Frame] = {}             # contact/group -> frame that holds chat history
chat_history_container: tk.Frame | None = None       # Main container for chat frames
main_window: tk.Tk | None = None                    # Main application window
lbl_chat_title: tk.Label | None = None

# Callbacks for file transfers
on_file_received = None  # Called when file is received: (sender, filename, filepath)
on_file_sent = None      # Called when file is sent: (target_user, filename)
