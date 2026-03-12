"""Construction of the primary chat interface.

When a user successfully logs in ``open_main_app`` is called; it sets up
the window containing the list of online users, the chat history area,
and the message entry field.
"""

import tkinter as tk
from tkinter import filedialog
from datetime import datetime

from . import state
from .chat_widgets import create_scrollable_area, add_message_bubble
from .callbacks import handle_file_received, handle_file_sent


# helper functions for mouse wheel binding

def _on_mousewheel(event, canvas):
    if event.num == 4 or event.delta > 0:
        canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
        canvas.yview_scroll(1, "units")


def bind_to_mousewheel(canvas):
    state.main_window.bind_all("<MouseWheel>", lambda e: _on_mousewheel(e, canvas))
    state.main_window.bind_all("<Button-4>", lambda e: _on_mousewheel(e, canvas))
    state.main_window.bind_all("<Button-5>", lambda e: _on_mousewheel(e, canvas))


def unbind_to_mousewheel():
    state.main_window.unbind_all("<MouseWheel>")
    state.main_window.unbind_all("<Button-4>")
    state.main_window.unbind_all("<Button-5>")


def open_main_app():
    """Switches from the login window to the primary chat interface."""
    root = state.root
    root.withdraw()

    main_window = tk.Toplevel()
    state.main_window = main_window
    main_window.title(f"My Chat App - Logged in as: {state.current_user}")
    main_window.geometry("1150x500")
    main_window.resizable(False, False)

    def on_closing():
        state.chat_client.disconnect()
        root.destroy()

    main_window.protocol("WM_DELETE_WINDOW", on_closing)

    main_window.grid_rowconfigure(1, weight=1)
    main_window.grid_columnconfigure(1, weight=1)

    # --- header & contacts frame ---
    frame_header = tk.Frame(main_window, bg="#2c3e50", height=60)
    frame_header.grid(row=0, column=0, columnspan=2, sticky="ew")
    frame_header.grid_propagate(False)
    tk.Label(
        frame_header,
        text="My Chat App",
        font=("Arial", 18, "bold"),
        bg="#2c3e50",
        fg="white",
    ).pack(pady=15)

    frame_contacts_container = tk.Frame(main_window, bg="#ecf0f1", width=250)
    frame_contacts_container.grid(row=1, column=0, sticky="nsew")
    frame_contacts_container.grid_propagate(False)

    # Create group button
    def open_create_group_dialog():
        """Open a dialog to create a new group."""
        create_group_window = tk.Toplevel(main_window)
        create_group_window.title("Create New Group")
        create_group_window.geometry("300x400")
        create_group_window.resizable(False, False)

        # Group name entry
        tk.Label(create_group_window, text="Group Name:", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        entry_group_name = tk.Entry(create_group_window, width=30)
        entry_group_name.pack(pady=5)

        # Users list with checkboxes
        tk.Label(create_group_window, text="Select Users:", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        
        users_frame = tk.Frame(create_group_window)
        users_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        users_scroll_container = tk.Frame(users_frame, bg="white")
        users_scroll_container.pack(fill="both", expand=True)
        users_scroll_area, _ = create_scrollable_area(users_scroll_container, "white")
        
        user_vars = {}
        
        # Add checkboxes for all online users (except current user)
        for user in sorted(state.online_users):
            var = tk.BooleanVar()
            user_vars[user] = var
            chk = tk.Checkbutton(
                users_scroll_area, 
                text=user, 
                variable=var, 
                bg="white", 
                anchor="w"
            )
            chk.pack(fill="x", padx=5, pady=2)
        
        # Create button
        def create_group():
            group_name = entry_group_name.get().strip()
            if not group_name:
                from tkinter import messagebox
                messagebox.showwarning("Invalid Input", "Please enter a group name")
                return
            
            selected_users = [user for user, var in user_vars.items() if var.get()]
            if not selected_users:
                from tkinter import messagebox
                messagebox.showwarning("Invalid Input", "Please select at least one user")
                return
            
            # Add the creator to the group members
            group_members = [state.current_user] + selected_users
            
            # Add group to state
            state.groups[group_name] = group_members
            
            # Send group creation to server - server will broadcast to all users
            state.chat_client.create_group(group_name, group_members)
            
            create_group_window.destroy()
        
        tk.Button(create_group_window, text="Create Group", command=create_group, 
                  bg="#2ecc71", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

    btn_create_group = tk.Button(
        frame_contacts_container,
        text="Create Group",
        command=open_create_group_dialog,
        relief="flat",
        bg="#2ecc71",
        fg="white",
        font=("Arial", 9, "bold"),
        height=2,
    )
    btn_create_group.pack(fill="x", padx=5, pady=5)

    tk.Label(
        frame_contacts_container,
        text="Online Users:",
        font=("Arial", 10, "bold"),
        bg="#ecf0f1",
    ).pack(pady=(10, 0))

    contacts_scroll_container = tk.Frame(frame_contacts_container, bg="#ecf0f1")
    contacts_scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
    state.scrollable_contacts, _ = create_scrollable_area(contacts_scroll_container, "#ecf0f1")

    # --- main chat area ---
    frame_chat_main = tk.Frame(main_window, bg="white")
    frame_chat_main.grid(row=1, column=1, sticky="nsew")

    chat_header_container = tk.Frame(frame_chat_main, bg="#f9f9f9", height=70)
    chat_header_container.pack(side="top", fill="x")
    chat_header_container.pack_propagate(False)

    state.lbl_chat_title = tk.Label(
        chat_header_container,
        text="Select a contact to start chatting...",
        font=("Arial", 14, "bold"),
        bg="#f9f9f9",
    )
    state.lbl_chat_title.pack(side="left", padx=20, pady=(10, 0))
    
    state.lbl_chat_subtitle = tk.Label(
        chat_header_container,
        text="",
        font=("Arial", 10),
        bg="#f9f9f9",
        fg="#666666",
    )
    state.lbl_chat_subtitle.pack(side="left", padx=20, pady=(0, 10))

    chat_input_container = tk.Frame(frame_chat_main, bg="#f1f0f0", height=60, padx=10, pady=10)
    chat_input_container.pack(side="bottom", fill="x")

    entry_text = tk.Text(chat_input_container, height=2, width=75, wrap="word", font=("Arial", 11))
    entry_text.pack(side="left", padx=(0, 10))
    state.entry_text = entry_text

    chat_history_container_local = tk.Frame(frame_chat_main, bg="white")
    chat_history_container_local.pack(side="top", fill="both", expand=True, padx=10, pady=10)
    state.chat_history_container = chat_history_container_local

    # --- chat logic inside main app ---
    def send_gui_message():
        if not state.current_chat_contact:
            return
        msg = entry_text.get("1.0", tk.END).strip()
        if msg:
            timestamp = datetime.now().strftime("%I:%M %p")
            state.chat_client.send_message(state.current_chat_contact, msg)
            add_message_bubble(msg, timestamp, state.current_chat_contact, is_me=True)
            entry_text.delete("1.0", tk.END)

    entry_text.bind(
        "<Return>",
        lambda e: "break" if (e.state & 0x0001) else (send_gui_message(), "break")[1],
    )
    tk.Button(chat_input_container, text="Send", command=send_gui_message, bg="#3498db", fg="white").pack(
        side="right", fill="y", padx=2
    )

    def send_file():
        filepath = filedialog.askopenfilename(initialdir="C:\\Downloads",
                                          title="Send a file",
                                          filetypes= (
                                              ("Image Files", ("*.jpg", "*.png", "*,jpeg")),
                                              ("All Files", "*.*")))
        state.chat_client.send_media(filepath, state.current_chat_contact)

    tk.Button(chat_input_container, text="Send File", command=send_file, bg="#3498db", fg="white").pack(
        side="right", fill="y", padx=2
    )

    # mark GUI ready and apply any pending user list and group list
    state.gui_ready = True
    if state.pending_user_list is not None:
        from .callbacks import handle_user_list_update, handle_group_list_update

        handle_user_list_update(state.pending_user_list)
        state.pending_user_list = None
    
    if state.pending_group_list is not None:
        from .callbacks import handle_group_list_update
        handle_group_list_update(state.pending_group_list)
        state.pending_group_list = None
    
    # Register file transfer callbacks with the chat client
    state.chat_client.on_file_received = handle_file_received
    state.chat_client.on_file_sent = handle_file_sent
