"""Login window construction and authentication helpers.

This module is responsible for building the initial prompt where the user
enters their username and for driving the :class:`ChatClient` connection
attempt.  Upon successful connection the main chat window is displayed.
"""

import tkinter as tk
from tkinter import messagebox

from . import state
from .callbacks import handle_incoming_message, handle_network_error, handle_user_list_update, handle_group_list_update
from .main_app import open_main_app

def setup_login_window():
    """Builds the login window and wires up the callbacks."""
    root = tk.Tk()
    state.root = root
    root.title("Login System")
    root.geometry("300x150")
    root.resizable(False, False)

    tk.Label(root, text="Enter a Username to Connect:").pack(pady=(20, 5))
    entry_username = tk.Entry(root)
    entry_username.pack()
    state.entry_username = entry_username

    tk.Button(root, text="Connect to Server", command=login, bg="lightblue").pack(pady=15)



def login():
    """Attempt to connect to the server using the provided username."""
    username = state.entry_username.get().lower().strip()

    if not username:
        messagebox.showerror("Error", "Please enter a username.")
        return

    success = state.chat_client.connect(
        username=username,
        message_callback=handle_incoming_message,
        error_callback=handle_network_error,
        user_list_callback=handle_user_list_update,
        group_list_callback=handle_group_list_update,
    )

    if success:
        state.current_user = username
        open_main_app()
