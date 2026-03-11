"""Utility functions for constructing and manipulating chat widgets.

The functions in this module are intentionally GUI‑agnostic; they simply
create frame hierarchies and message bubbles.  They are consumed by
``main_app.py`` and ``callbacks.py``.
"""

import tkinter as tk
from PIL import Image, ImageTk
import os

from . import state


def create_scrollable_area(parent_container: tk.Widget, bg_color: str):
    """Helper to create a canvas-based scrollable frame."""
    canvas = tk.Canvas(parent_container, bg=bg_color, highlightthickness=0)
    scrollbar = tk.Scrollbar(parent_container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=bg_color)

    scroll_frame.bind(
        "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # mouse wheel bindings need to be attached by the caller if desired
    return scroll_frame, canvas


def create_chat_frame_for_user(contact_name: str):
    """Make the internal widgets that will display a conversation."""
    if state.chat_history_container is None:
        return

    contact_container = tk.Frame(state.chat_history_container, bg="white")
    state.chat_containers[contact_name] = contact_container

    canvas = tk.Canvas(contact_container, bg="white", highlightthickness=0)
    scrollbar = tk.Scrollbar(contact_container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="white")

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    state.chat_frames[contact_name] = (scroll_frame, canvas)


def add_message_bubble(message_text: str, timestamp: str, contact: str, is_me: bool = True):
    """Insert a message bubble into the appropriate conversation frame."""
    if contact not in state.chat_frames:
        return
    scrollable_chat, chat_canvas = state.chat_frames[contact]
    msg_container = tk.Frame(scrollable_chat, bg="white")
    if is_me:
        msg_container.pack(anchor="e", padx=20, pady=5)
        tk.Label(
            msg_container,
            text=message_text,
            bg="#dcf8c6",
            padx=10,
            pady=5,
            wraplength=300,
            justify="left",
        ).pack(anchor="e")
        tk.Label(
            msg_container,
            text=timestamp,
            bg="white",
            fg="gray",
            font=("Arial", 8),
        ).pack(anchor="e")
    else:
        msg_container.pack(anchor="w", padx=20, pady=5)
        tk.Label(
            msg_container,
            text=message_text,
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


def add_file_transfer_bubble(filename: str, filepath: str | None, timestamp: str, contact: str, is_me: bool = True):
    """Insert a file transfer bubble into the appropriate conversation frame.
    
    Args:
        filename: Name of the file being transferred
        filepath: Full path to the file (None for sent files)
        timestamp: Time the transfer occurred
        contact: Name of the contact involved
        is_me: True if we sent the file, False if we received it
    """
    if contact not in state.chat_frames:
        return
    
    scrollable_chat, chat_canvas = state.chat_frames[contact]
    msg_container = tk.Frame(scrollable_chat, bg="white")
    
    # Get file extension to determine if it's an image
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    if ext in image_extensions and filepath and os.path.isfile(filepath):
        # Display image
        try:
            img = Image.open(filepath)
            # Resize image to fit in chat (max 300px width)
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            if is_me:
                msg_container.pack(anchor="e", padx=20, pady=5)
                img_label = tk.Label(msg_container, image=photo, bg="#dcf8c6", padx=5, pady=5)
                img_label.image = photo  # Keep a reference to prevent garbage collection
                img_label.pack(anchor="e")
            else:
                msg_container.pack(anchor="w", padx=20, pady=5)
                img_label = tk.Label(msg_container, image=photo, bg="#f1f0f0", padx=5, pady=5)
                img_label.image = photo  # Keep a reference to prevent garbage collection
                img_label.pack(anchor="w")
        except Exception as e:
            # Fallback to text if image can't be loaded
            _add_generic_file_bubble(filename, msg_container, is_me)
            print(f"Could not display image: {e}")
    else:
        # Display generic file bubble
        _add_generic_file_bubble(filename, msg_container, is_me)
    
    # Add timestamp below the file
    if is_me:
        msg_container.pack(anchor="e", padx=20, pady=5)
        tk.Label(
            msg_container,
            text=timestamp,
            bg="white",
            fg="gray",
            font=("Arial", 8),
        ).pack(anchor="e")
    else:
        msg_container.pack(anchor="w", padx=20, pady=5)
        tk.Label(
            msg_container,
            text=timestamp,
            bg="white",
            fg="gray",
            font=("Arial", 8),
        ).pack(anchor="w")
    
    chat_canvas.update_idletasks()
    chat_canvas.yview_moveto(1.0)


def _add_generic_file_bubble(filename: str, msg_container: tk.Frame, is_me: bool):
    """Helper function to display a generic file bubble with icon and filename."""
    # File icon as unicode character
    file_icon = "📄"
    file_text = f"{file_icon} {filename}"
    
    if is_me:
        tk.Label(
            msg_container,
            text=file_text,
            bg="#dcf8c6",
            padx=10,
            pady=5,
            wraplength=300,
            justify="left",
            font=("Arial", 10),
        ).pack(anchor="e")
    else:
        tk.Label(
            msg_container,
            text=file_text,
            bg="#f1f0f0",
            padx=10,
            pady=5,
            wraplength=300,
            justify="left",
            font=("Arial", 10),
        ).pack(anchor="w")
