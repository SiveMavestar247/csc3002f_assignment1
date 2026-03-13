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
    # Store the online users in state
    state.online_users = [u for u in users if u and u != state.current_user]
    
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
                command=lambda c=user: show_chat(c, is_group=False),
                relief="flat",
                bg="white",
            )
            btn.pack(fill="x", padx=5, pady=2)
    
    # Add groups if they exist
    for group_name in sorted(state.groups.keys()):
        if group_name not in state.chat_frames:
            create_chat_frame_for_user(group_name)
        
        btn = tk.Button(
            state.scrollable_contacts,
            text=group_name.upper(),
            command=lambda c=group_name: show_chat(c, is_group=True),
            relief="flat",
            bg="#e8f4f8",
            fg="#0066cc",
        )
        btn.pack(fill="x", padx=5, pady=2)


def handle_group_list_update(groups: dict[str, list[str]]):
    """Called when the server sends an updated list of groups."""
    # if GUI hasn't finished initialisation, cache the list for later
    if not state.gui_ready:
        state.pending_group_list = groups
        return
    
    old_groups = state.groups.copy()
    state.groups = groups
    
    # Detect if the current group was renamed
    renamed_group = None
    if state.current_chat_is_group and state.current_chat_contact:
        old_name = state.current_chat_contact
        if old_name not in groups:
            # Check if a group with the same members exists (it was renamed)
            old_members = old_groups.get(old_name)
            if old_members:
                for new_name, new_members in groups.items():
                    if new_name not in old_groups and set(new_members) == set(old_members):
                        # Found the renamed group - transfer chat history
                        if old_name in state.chat_frames:
                            state.chat_frames[new_name] = state.chat_frames.pop(old_name)
                        if old_name in state.chat_containers:
                            state.chat_containers[new_name] = state.chat_containers.pop(old_name)
                        state.current_chat_contact = new_name
                        renamed_group = new_name
                        print(f"[GUI] Group '{old_name}' renamed to '{new_name}'")
                        break
    
    # Check if current group was removed or user was removed from it
    if state.current_chat_is_group and state.current_chat_contact:
        if state.current_chat_contact not in groups or state.current_user not in groups.get(state.current_chat_contact, []):
            # User is no longer in the group, switch to default view
            state.current_chat_contact = None
            state.current_chat_is_group = False
            if state.lbl_chat_title:
                state.lbl_chat_title.config(text="Select a contact to start chatting...")
            if state.lbl_chat_subtitle:
                state.lbl_chat_subtitle.config(text="")
            if state.btn_group_settings:
                state.btn_group_settings.pack_forget()
            # Hide all chat containers
            for container in state.chat_containers.values():
                container.pack_forget()
        else:
            # Group still exists, update the subtitle with new members
            if state.lbl_chat_subtitle and state.current_chat_contact in groups:
                members = ", ".join(groups[state.current_chat_contact])
                state.lbl_chat_subtitle.config(text=f"Members: {members}")
            # If group was renamed, update the title
            if renamed_group and state.lbl_chat_title:
                state.lbl_chat_title.config(text=f"Group: {renamed_group.upper()}")
    
    # Refresh the contacts list to show the updated groups
    if state.online_users:
        handle_user_list_update(state.online_users + [state.current_user])
    elif state.pending_user_list is not None:
        handle_user_list_update(state.pending_user_list)


def show_chat(contact_name: str, is_group: bool = False):
    """Switch the displayed chat to a different contact or group."""
    if not contact_name:
        return
    state.current_chat_contact = contact_name
    state.current_chat_is_group = is_group
    
    if state.lbl_chat_title:
        if is_group:
            state.lbl_chat_title.config(text=f"Group: {contact_name.upper()}")
            # Show group members in subtitle
            if state.lbl_chat_subtitle and contact_name in state.groups:
                members = ", ".join(state.groups[contact_name])
                state.lbl_chat_subtitle.config(text=f"Members: {members}")
            # Show settings button for groups
            if state.btn_group_settings:
                state.btn_group_settings.pack(side="right", padx=20, pady=10)
        else:
            state.lbl_chat_title.config(text=f"Chatting with {contact_name}")
            # Hide subtitle for individual chats
            if state.lbl_chat_subtitle:
                state.lbl_chat_subtitle.config(text="")
            # Hide settings button for individual chats
            if state.btn_group_settings:
                state.btn_group_settings.pack_forget()

    # hide all chat containers and only display the selected one
    for user, container in state.chat_containers.items():
        if user == contact_name:
            container.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        else:
            container.pack_forget()


def handle_incoming_message(sender: str, message: str, group: str | None = None):
    """This is invoked by the network client when a message arrives.
    
    Args:
        sender: The user who sent the message
        message: The message content
        group: The group name if this is a group message, None for individual messages
    """
    timestamp = datetime.now().strftime("%I:%M %p")
    contact = group if group else sender

    # ensure we have a frame for this sender/group
    if contact not in state.chat_frames:
        create_chat_frame_for_user(contact)

    # update GUI from main thread safely
    state.root.after(0, add_incoming_bubble_safely, contact, sender, message, timestamp, group is not None)


def add_incoming_bubble_safely(contact: str, sender: str, message: str, timestamp: str, is_group: bool = False):
    """Draw an incoming message bubble on the GUI thread."""
    if contact not in state.chat_frames:
        return

    scrollable_chat, chat_canvas = state.chat_frames[contact]
    msg_container = tk.Frame(scrollable_chat, bg="white")
    msg_container.pack(anchor="w", padx=20, pady=5)
    
    # Show sender name for group chats
    if is_group:
        tk.Label(
            msg_container,
            text=sender,
            bg="white",
            fg="#555555",
            font=("Arial", 9, "bold"),
        ).pack(anchor="w")
    
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
    """Called when a file transfer is completed.
    
    Args:
        sender: The user who sent the file
        filename: Name of the file received
        filepath: Path where the file was saved
    """
    timestamp = datetime.now().strftime("%I:%M %p")
    
    # Check if we're currently viewing a group and the sender is in that group
    contact = sender
    is_group = False
    
    if state.current_chat_is_group and state.current_chat_contact in state.groups:
        group_members = state.groups[state.current_chat_contact]
        if sender in group_members:
            # File is from someone in the current group - display in group chat
            contact = state.current_chat_contact
            is_group = True

    # ensure we have a frame for this contact/group
    if contact not in state.chat_frames:
        create_chat_frame_for_user(contact)

    # update GUI from main thread safely
    state.root.after(0, add_file_transfer_bubble, filename, filepath, timestamp, contact, False, sender if is_group else None)


def handle_file_sent(target: str, filename: str):
    """Called when we send a file to another user or group.
    
    Args:
        target: Target user or group name
        filename: Name of the file sent
    """
    timestamp = datetime.now().strftime("%I:%M %p")

    # ensure we have a frame for this contact/group
    if target not in state.chat_frames:
        create_chat_frame_for_user(target)

    # update GUI from main thread safely (filepath=None for sent files)
    state.root.after(0, add_file_transfer_bubble, filename, None, timestamp, target, True)
