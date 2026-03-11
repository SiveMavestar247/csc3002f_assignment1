"""Network callback routines invoked by :class:`ChatClient`.

These helpers bridge the gap between the background network thread and
the Tkinter main loop; most of them merely update widgets held in
:mod:`state`.
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from . import state
from .chat_widgets import create_chat_frame_for_user, add_file_transfer_bubble


def handle_network_error(error_msg: str):
    """Display an error message when network connection fails during login."""
    message = f"Could not connect to server.\n{error_msg}"
    messagebox.showerror("Connection Error", message)


def handle_user_list_update(users: list[str]):
    """Called when the server sends an updated list of online users."""
    # if GUI hasn't finished initialisation, cache the list for later
    if not state.gui_ready:
        state.pending_user_list = users
        return

    if state.scrollable_contacts is None:
        return

    # clear existing buttons
    for widget in state.scrollable_contacts.winfo_children():
        widget.destroy()

    # add a button for each user (excluding ourselves)
    for user in users:
        if user and user != state.current_user:
            if user not in state.chat_frames:
                create_chat_frame_for_user(user)

            btn = tk.Button(
                state.scrollable_contacts,
                text=user,
                command=lambda c=user: show_chat(c),
                relief="flat",
                bg="white",
            )
            btn.pack(fill="x", padx=5, pady=2)


def show_chat(contact_name: str):
    """Switch the displayed chat to a different contact."""
    if not contact_name:
        return
    state.current_chat_contact = contact_name
    if state.lbl_chat_title:
        state.lbl_chat_title.config(text=f"Chatting with {contact_name}")

    # hide all chat containers and only display the selected one
    for user, container in state.chat_containers.items():
        if user == contact_name:
            container.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        else:
            container.pack_forget()


def handle_incoming_message(sender: str, message: str):
    """This is invoked by the network client when a message arrives."""
    timestamp = datetime.now().strftime("%I:%M %p")

    # ensure we have a frame for this sender
    if sender not in state.chat_frames:
        create_chat_frame_for_user(sender)

    # update GUI from main thread safely
    state.root.after(0, add_incoming_bubble_safely, sender, message, timestamp)


def add_incoming_bubble_safely(sender: str, message: str, timestamp: str):
    """Draw an incoming message bubble on the GUI thread."""
    if sender not in state.chat_frames:
        return

    scrollable_chat, chat_canvas = state.chat_frames[sender]
    msg_container = tk.Frame(scrollable_chat, bg="white")
    msg_container.pack(anchor="w", padx=20, pady=5)
    tk.Label(
        msg_container,
        text=message,
        bg="#f1f0f0",
        padx=10,
        pady=5,
        wraplength=300,
        justify="left",
    ).pack(anchor="w")
    tk.Label(
        msg_container,
        text=timestamp,
        bg="white",
        fg="gray",
        font=("Arial", 8),
    ).pack(anchor="w")
    chat_canvas.update_idletasks()
    chat_canvas.yview_moveto(1.0)


def handle_file_received(sender: str, filename: str, filepath: str):
    """Called when a file transfer is completed."""
    timestamp = datetime.now().strftime("%I:%M %p")

    # ensure we have a frame for this sender
    if sender not in state.chat_frames:
        create_chat_frame_for_user(sender)

    # update GUI from main thread safely
    state.root.after(0, add_file_transfer_bubble, filename, filepath, timestamp, sender, False)


def handle_file_sent(target_user: str, filename: str):
    """Called when we send a file to another user."""
    timestamp = datetime.now().strftime("%I:%M %p")

    # ensure we have a frame for this contact
    if target_user not in state.chat_frames:
        create_chat_frame_for_user(target_user)

    # update GUI from main thread safely (filepath=None for sent files)
    state.root.after(0, add_file_transfer_bubble, filename, None, timestamp, target_user, True)
