import tkinter as tk
from tkinter import messagebox
from datetime import datetime

# A simple dictionary to act as our database for this example
user_db = {"admin": "password123"}

def login():
    """Handles the login authentication."""
    username = entry_username.get()
    password = entry_password.get()
    open_main_app()
    # if username in user_db and user_db[username] == password:
    #     messagebox.showinfo("Success", "Login successful!")
    #     open_main_app()
    # else:
    #     messagebox.showerror("Error", "Invalid username and/or password.")

def signup_or_login():
    entry_username.delete(0, tk.END)
    entry_password.delete(0, tk.END)
    entry_comfirm_password.delete(0, tk.END)
    
    if signup_btn['text'] == "Create a New Account":
        login_btn.pack_forget()
        signup_btn.pack_forget()
        lbl_comfirm_password.pack()
        entry_comfirm_password.pack()
        login_btn.pack(pady=(20, 5))
        signup_btn.pack()
        signup_btn['text'] = "Back to Login"
        login_btn['text'] = "Sign Up"
        login_btn['command'] = signup
    else:
        lbl_comfirm_password.pack_forget()
        entry_comfirm_password.pack_forget()
        signup_btn['text'] = "Create a New Account"
        login_btn['text'] = "Login"
        login_btn['command'] = login


def signup():
    """Handles registering a new user."""
    username = entry_username.get()
    password = entry_password.get()
    password2 = entry_comfirm_password.get()

    if username == "" or password == "":
        messagebox.showwarning("Warning", "Username and Password cannot be empty.")
    elif username in user_db:
        messagebox.showerror("Error", "Username already exists. Try logging in.")
    elif password != password2:
        messagebox.showerror("Error", "Passwords do not match. Try again")
    else:
        user_db[username] = password
        messagebox.showinfo("Success", "Signup successful! Logging you in...")
        signup_or_login()
        open_main_app()


def open_main_app():
    """Opens the main application window with fixed headers, mouse scrolling, and Enter-to-send."""
    root.withdraw() 

    main_window = tk.Toplevel()
    main_window.title("Main Application - Chat")
    main_window.geometry("1200x500") 
    main_window.resizable(False, False)
    main_window.protocol("WM_DELETE_WINDOW", root.destroy)

    main_window.grid_rowconfigure(1, weight=1)    
    main_window.grid_columnconfigure(1, weight=1) 

    # ==========================================
    # HELPER FUNCTIONS: Mouse Scrolling
    # ==========================================
    def _on_mousewheel(event, canvas):
        """Cross-platform mouse wheel scrolling."""
        # Windows & Mac (event.delta), Linux (event.num 4/5)
        if event.num == 4 or event.delta > 0:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            canvas.yview_scroll(1, "units")

    def bind_to_mousewheel(event, canvas):
        """Activates scrolling when the mouse hovers over the canvas."""
        main_window.bind_all("<MouseWheel>", lambda e: _on_mousewheel(e, canvas))
        main_window.bind_all("<Button-4>", lambda e: _on_mousewheel(e, canvas)) # Linux scroll up
        main_window.bind_all("<Button-5>", lambda e: _on_mousewheel(e, canvas)) # Linux scroll down

    def unbind_to_mousewheel(event):
        """Deactivates scrolling when the mouse leaves the canvas."""
        main_window.unbind_all("<MouseWheel>")
        main_window.unbind_all("<Button-4>")
        main_window.unbind_all("<Button-5>")

    # ==========================================
    # HELPER FUNCTION: Create Scrollable Areas
    # ==========================================
    def create_scrollable_area(parent_container, bg_color):
        canvas = tk.Canvas(parent_container, bg=bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent_container, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=bg_color)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Bind the hover scrolling events
        canvas.bind("<Enter>", lambda e: bind_to_mousewheel(e, canvas))
        canvas.bind("<Leave>", unbind_to_mousewheel)
        
        return scroll_frame, canvas

    # ==========================================
    # FRAME 1: Header (Top)
    # ==========================================
    frame_header = tk.Frame(main_window, bg="#2c3e50", height=60)
    frame_header.grid(row=0, column=0, columnspan=2, sticky="ew") 
    frame_header.grid_propagate(False) 
    tk.Label(frame_header, text="Chat App", font=("Arial", 18, "bold"), bg="#2c3e50", fg="white").pack(pady=15)

    # ==========================================
    # FRAME 2: Contacts (Left Sidebar)
    # ==========================================
    frame_contacts_container = tk.Frame(main_window, bg="#ecf0f1", width=250)
    frame_contacts_container.grid(row=1, column=0, sticky="nsew") 
    frame_contacts_container.grid_propagate(False) 

    tk.Label(frame_contacts_container, text="Contacts", font=("Arial", 12, "bold"), bg="#ecf0f1").pack(pady=10)

    contacts_scroll_container = tk.Frame(frame_contacts_container, bg="#ecf0f1")
    contacts_scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
    scrollable_contacts, _ = create_scrollable_area(contacts_scroll_container, "#ecf0f1")

    contacts = [f"Contact Name {i}" for i in range(1, 21)]
    for contact in contacts:
        btn = tk.Button(scrollable_contacts, text=contact, command=lambda c=contact: show_chat(c), relief="flat", bg="white")
        btn.pack(fill="x", padx=5, pady=2)

    tk.Button(frame_contacts_container, text="Logout", command=lambda: logout(main_window), bg="#e74c3c", fg="white", relief="flat").pack(side="bottom", fill="x", padx=10, pady=10)

    # ==========================================
    # FRAME 3: Main Chat Area (Right side)
    # ==========================================
    frame_chat_main = tk.Frame(main_window, bg="white")
    frame_chat_main.grid(row=1, column=1, sticky="nsew")

    # --- 3A: FIXED Chat Header ---
    chat_header_container = tk.Frame(frame_chat_main, bg="#f9f9f9", height=50)
    chat_header_container.pack(side="top", fill="x")
    chat_header_container.pack_propagate(False)
    
    lbl_chat_title = tk.Label(chat_header_container, text="Select a contact to start chatting...", font=("Arial", 14, "bold"), bg="#f9f9f9", fg="#333333")
    lbl_chat_title.pack(side="left", padx=20, pady=10)

    # --- 3B: Chat Input Area (Bottom) ---
    chat_input_container = tk.Frame(frame_chat_main, bg="#f1f0f0", height=60, padx=10, pady=10)
    chat_input_container.pack(side="bottom", fill="x")

    text_message = tk.Text(chat_input_container, height=2, wrap="word", font=("Arial", 11))
    text_message.pack(side="left", fill="both", expand=True, padx=(0, 10))

    # --- 3C: Scrollable Chat History (Middle) ---
    # Packed last so it expands into the space between the fixed header and fixed footer
    chat_history_container = tk.Frame(frame_chat_main, bg="white")
    chat_history_container.pack(side="top", fill="both", expand=True, padx=10, pady=10)
    scrollable_chat, chat_canvas = create_scrollable_area(chat_history_container, "white")

    # ==========================================
    # Chat Logic Functions
    # ==========================================
    def add_message_bubble(message_text: str, timestamp: str, is_me=True):
        msg_container = tk.Frame(scrollable_chat, bg="white")
        
        if is_me:
            msg_container.pack(anchor="e", padx=20, pady=5)
            bg_color = "#dcf8c6"
            align = "e"
        else:
            msg_container.pack(anchor="w", padx=20, pady=5)
            bg_color = "#f1f0f0"
            align = "w"

        tk.Label(msg_container, text=message_text, bg=bg_color, padx=10, pady=5, wraplength=300, justify="left").pack(anchor=align)
        tk.Label(msg_container, text=timestamp, bg="white", fg="gray", font=("Arial", 8)).pack(anchor=align)

    def send_message():
        msg = text_message.get("1.0", tk.END).strip()
        timestamp = datetime.now().strftime("%d-%b-%Y, %I:%M %p")
        if msg: 
            add_message_bubble(msg, timestamp, is_me=True)
            text_message.delete("1.0", tk.END)
            chat_canvas.update_idletasks()
            chat_canvas.yview_moveto(1.0)

    def send_on_enter(event):
        """Fires when the Enter key is pressed."""
        # Shift+Enter allows for line breaks if you want to type multi-line messages
        if event.state & 0x0001: 
            return None 
        
        send_message()
        return "break" # Prevents default Tkinter newline behavior

    # Bind the enter key to the text box
    text_message.bind("<Return>", send_on_enter)

    btn_send = tk.Button(chat_input_container, text="Send", bg="#3498db", fg="white", font=("Arial", 10, "bold"), width=8)
    btn_send.pack(side="right", fill="y")

    # ==========================================
    # Function to update Chat Area
    # ==========================================
    def show_chat(contact_name):
        btn_send['command'] = send_message
        lbl_chat_title.config(text=f"Chatting with {contact_name}")
        for widget in scrollable_chat.winfo_children():
            widget.destroy()
        
        timestamp = datetime.now().strftime("%d-%b-%Y, %I:%M %p")
        # Use our helper function for the fake conversation history
        add_message_bubble(f"Hello {contact_name}!", timestamp, is_me=True)
        add_message_bubble("Hi there! How are you?", timestamp, is_me=False)
        
        chat_canvas.yview_moveto(0)

def logout(main_window):
    """Closes the main app and brings back the login screen."""
    main_window.destroy()
    
    # Clear the text fields
    entry_username.delete(0, tk.END)
    entry_password.delete(0, tk.END)
    entry_comfirm_password.delete(0, tk.END)
    
    # Reveal the login window again
    root.deiconify()

# ==========================================
# Setup the Login / Signup Window (Root)
# ==========================================
root = tk.Tk()
root.title("Chat App")
root.resizable(False, False)
root.eval('tk::PlaceWindow . center')
root.geometry("220x310")

# Header Label
tk.Label(root, text="Login / Sign Up", font=("Arial", 16, "bold")).pack(pady=(20, 5))

# Username Label & Entry
tk.Label(root, text="Username:").pack(pady=(20, 5))
entry_username = tk.Entry(root)
entry_username.pack()

# Password Label & Entry (show="*" hides the characters)
tk.Label(root, text="Password:").pack(pady=5)
entry_password = tk.Entry(root, show="*")
entry_password.pack()

lbl_comfirm_password = tk.Label(root, text="Comfirm Password:")
entry_comfirm_password = tk.Entry(root, show="*")

# Login & Signup Buttons
login_btn = tk.Button(root, text="Login", command=login, width=20, bg="lightblue")
login_btn.pack(pady=(20, 5))
signup_btn = tk.Button(root, text="Create a New Account", command=signup_or_login, width=20)
signup_btn.pack()

# Start the application
root.mainloop()