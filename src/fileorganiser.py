import os
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from organizer_core import Organizer
from tkinter import *
from tkinter import filedialog, messagebox, scrolledtext

# All move paths share the same native no-replace and undo implementation.
organizer = Organizer()
ui_events = Queue()

# ---------------- GUI Root ----------------
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    root = TkinterDnD.Tk()
    dnd_available = True
except ImportError:
    root = Tk()
    dnd_available = False
    print("Drag & drop not available. Install tkinterdnd2 for drag & drop support.")

root.title("Smart File Organizer")
root.geometry("780x600")
root.resizable(False, False)
root.configure(bg="#1f1f2e")

# ---------------- Progress Bar ----------------
progress_frame = Frame(root, bg="#1f1f2e")
progress_frame.pack(pady=10)

canvas = Canvas(progress_frame, width=700, height=30, bg="#444", bd=0, highlightthickness=0, relief='ridge')
canvas.pack()
progress_rect = canvas.create_rectangle(0, 0, 0, 30, fill="#00ff99", width=0)
progress_label = Label(progress_frame, text="0%", font=("Arial", 11, "bold"), bg="#1f1f2e", fg="#fff")
progress_label.pack(pady=5)

# ---------------- Logging ----------------
session_log = []
def log_action(action):
    # Move logs stay in this process; never write personal paths to the source tree.
    session_log.append(action)

# ---------------- Automatic Categorization ----------------
file_categories = {
    "Documents": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov"],
    "Music": [".mp3", ".wav", ".flac"],
    "Archives": [".zip", ".rar", ".7z", ".tar.gz"],
}

name_keywords = {
    "Work": ["report", "project", "assignment"],
    "Personal": ["photo", "selfie", "diary"],
}

def categorize_file(filename):
    lname = filename.lower()
    for category, keywords in name_keywords.items():
        if any(kw in lname for kw in keywords):
            return category
    ext = os.path.splitext(filename)[1].lower()
    for category, exts in file_categories.items():
        if ext in exts:
            return category
    return "Others"

# ---------------- Smooth Progress Update ----------------
def update_progress_smooth(target):
    current_coords = canvas.coords(progress_rect)
    current_width = current_coords[2] if current_coords else 0
    target_width = int(700 * target / 100)
    step = 5
    if current_width < target_width:
        for w in range(int(current_width), target_width + step, step):
            canvas.coords(progress_rect, 0, 0, min(w, target_width), 30)
            progress_label.config(text=f"{int(min(w, target_width)/7)}%")
            root.update_idletasks()
            time.sleep(0.01)
    else:
        canvas.coords(progress_rect, 0, 0, target_width, 30)
        progress_label.config(text=f"{target}%")

# ---------------- Manual Mode ----------------
def manual_mode():
    file_path = filedialog.askopenfilename(title="Select File to Organize")
    if not file_path:
        return
    try:
        folder = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        category = categorize_file(filename)
        status = organizer.move(file_path, category)
        if status == 0:
            messagebox.showinfo("Skipped", "A destination with that name already exists. Both files were kept.")
            return
        if status < 0:
            raise OSError("Move failed. Check permissions and the category directory.")
        log_action(f"Manual: {filename} -> {category}")
        update_progress_smooth(100)
        time.sleep(0.1)
        update_progress_smooth(0)
        messagebox.showinfo("Success", f"{filename} moved to {category}!")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# ---------------- Auto Mode ----------------
watching_folders = []
auto_running = False
folder_status_labels = {}  # folder -> Label

folders_frame = Frame(root, bg="#1f1f2e")
folders_frame.pack(pady=5, fill=X)
Label(folders_frame, text="Watched Folders:", bg="#1f1f2e", fg="#00ff99", font=("Arial", 12, "bold")).pack(anchor=W, padx=10)
folders_list_frame = Frame(folders_frame, bg="#1f1f2e")
folders_list_frame.pack(padx=10, fill=X)

# ---------------- Folder Management ----------------
def refresh_watched_folders():
    for widget in folders_list_frame.winfo_children():
        widget.destroy()
    for folder in tuple(watching_folders):
        folder_frame = Frame(folders_list_frame, bg="#2a2a3a")
        folder_frame.pack(fill=X, pady=2)
        folder_label = Label(folder_frame, text=Path(folder).name, bg="#2a2a3a", fg="#fff", anchor=W)
        folder_label.pack(side=LEFT, padx=5, expand=True, fill=X)
        status_label = Label(folder_frame, text="Idle", bg="#2a2a3a", fg="green", width=15)
        status_label.pack(side=LEFT, padx=5)
        folder_status_labels[folder] = status_label
        btn = Button(folder_frame, text="Remove", bg="#f44336", fg="#222", relief=FLAT, bd=0,
                     activebackground="#555", activeforeground="#fff",
                     command=lambda f=folder: remove_folder(f))
        btn.pack(side=RIGHT, padx=5)

def remove_folder(folder):
    if folder in watching_folders:
        watching_folders.remove(folder)
        folder_status_labels.pop(folder, None)
        refresh_watched_folders()
        log_action(f"Stopped watching folder: {folder}")
        if not watching_folders:
            stop_auto_mode()

# ---------------- Auto Mode Functions ----------------
def scan_new_files(folder):
    try:
        moved = organizer.scan(folder, lambda value: ui_events.put(("progress", value)))
        ui_events.put(("scanned", folder, moved))
    except Exception:
        ui_events.put(("error", "Automatic scan failed; files were left in place."))

def auto_mode():
    global auto_running, watch_thread
    folder = filedialog.askdirectory(title="Select Folder to Organize")
    if not folder:
        return
    if folder not in watching_folders:
        watching_folders.append(folder)
        refresh_watched_folders()
        messagebox.showinfo("Folder Added", f"Folder added for auto organization:\n{folder}")
    if not auto_running:
        auto_running = True
        stop_event.clear()
        stop_auto_btn.pack(pady=5)
        watch_thread = threading.Thread(target=run_auto_watch, daemon=True)
        watch_thread.start()

stop_event = threading.Event()
watch_thread = None

def run_auto_watch():
    while not stop_event.is_set():
        for folder in tuple(watching_folders):
            if stop_event.is_set():
                break
            scan_new_files(folder)
        stop_event.wait(2)
    ui_events.put(("stopped",))

def stop_auto_mode():
    global auto_running, watching_folders
    stop_event.set()
    if watch_thread is not None:
        watch_thread.join()
    auto_running = False
    watching_folders.clear()
    folder_status_labels.clear()
    refresh_watched_folders()
    update_progress_smooth(0)
    progress_label.config(text="Auto Mode Stopped")
    stop_auto_btn.pack_forget()
    select_auto_button.config(state=NORMAL)
    messagebox.showinfo("Stopped", "Auto Mode has been stopped.")

# ---------------- Undo ----------------
def undo_move():
    try:
        status = organizer.undo()
        if status == 1:
            log_action("Undo succeeded")
            messagebox.showinfo("Undo", "Last successful move restored.")
        elif status == 0:
            messagebox.showinfo("Undo", "Nothing restored: no move is available, or the original path is occupied.")
        else:
            messagebox.showerror("Undo", "Nothing restored: the moved file changed or the move could not be reversed.")
        update_progress_smooth(0)
    except Exception as e:
        messagebox.showerror("Error", str(e))

# ---------------- View Log ----------------
def view_log():
    if not session_log:
        messagebox.showinfo("Log", "No log file found.")
        return
    log_window = Toplevel(root)
    log_window.title("Organizer Log")
    log_window.geometry("650x400")
    log_window.configure(bg="#2a2a3a")
    txt = scrolledtext.ScrolledText(log_window, wrap=WORD, bg="#1e1e2e", fg="#f0f0f0", insertbackground="white")
    txt.pack(expand=True, fill=BOTH)
    txt.insert(END, "\n".join(session_log))
    txt.config(state=DISABLED)

# ---------------- Drag & Drop ----------------
def drop(event):
    if not dnd_available:
        return
    try:
        paths = root.tk.splitlist(event.data)
    except TclError:
        return
    for path in paths:
        path = path.strip()
        if os.path.isfile(path):
            folder = os.path.dirname(path)
            filename = os.path.basename(path)
            category = categorize_file(filename)
            status = organizer.move(path, category)
            if status == 1:
                log_action(f"DnD: {filename} -> {category}")
            else:
                messagebox.showinfo("Not moved", "Destination exists or the move failed. Existing files were kept.")
        elif os.path.isdir(path):
            if path not in watching_folders:
                watching_folders.append(path)
                refresh_watched_folders()
                messagebox.showinfo("Folder Added", f"Folder added for auto organization:\n{path}")

# ---------------- GUI Layout ----------------
title_frame = Frame(root, bg="#1f1f2e")
title_frame.pack(pady=10)
Label(title_frame, text="Smart File Organizer", font=("Arial", 20, "bold"), bg="#1f1f2e", fg="#00ff99").pack()
Label(title_frame, text="Manual: single file | Auto: organize folder(s)", font=("Arial", 12), bg="#1f1f2e", fg="#bbb").pack()

button_frame = Frame(root, bg="#1f1f2e")
button_frame.pack(pady=10)

# ---------------- Modern Button with hover & focus fix ----------------
def create_button(text, command, bg):
    btn = Button(
        button_frame,
        text=text,
        command=command,
        font=("Arial", 12, "bold"),
        width=30,
        bg=bg,
        fg="#222",
        activebackground="#555555",
        activeforeground="#fff",
        relief=FLAT,
        bd=0,
        highlightthickness=0
    )
    btn.bind("<Enter>", lambda e: btn.config(bg="#666"))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    btn.bind("<FocusIn>", lambda e: btn.config(bg=bg))
    btn.bind("<FocusOut>", lambda e: btn.config(bg=bg))
    return btn

select_manual_button = create_button("Manual Mode (Auto Categorize)", manual_mode, "#4caf50")
select_manual_button.pack(pady=5)

select_auto_button = create_button("Add Folder for Auto Mode", auto_mode, "#2196f3")
select_auto_button.pack(pady=5)

undo_button = create_button("Undo Last Move", undo_move, "#f44336")
undo_button.pack(pady=5)

view_log_button = create_button("View Log", view_log, "#9c27b0")
view_log_button.pack(pady=5)

# Stop Auto Mode button (hidden by default)
stop_auto_btn = create_button("Stop Auto Mode", stop_auto_mode, "#ff9800")
stop_auto_btn.pack_forget()

# Enable Drag & Drop if available
if dnd_available:
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', drop)

def process_events():
    try:
        while True:
            event = ui_events.get_nowait()
            if event[0] == "progress":
                update_progress_smooth(event[1])
            elif event[0] == "scanned":
                folder, moved = event[1:]
                if folder in folder_status_labels:
                    folder_status_labels[folder].config(text=f"Moved: {max(0, moved)}", fg="gray")
                log_action(f"Auto scan: {max(0, moved)} moved; collisions kept")
            elif event[0] == "error":
                log_action(event[1])
    except Empty:
        pass
    root.after(100, process_events)

def close_app():
    stop_event.set()
    if watch_thread is not None:
        watch_thread.join()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", close_app)
root.after(100, process_events)
root.mainloop()
