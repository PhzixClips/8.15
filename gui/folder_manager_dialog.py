import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from data.winners_manager import WinnersManager

class FolderManagerDialog(tk.Toplevel):
    def __init__(self, parent, winners_manager: WinnersManager):
        super().__init__(parent)
        self.winners_manager = winners_manager

        self.title("Manage Folders")
        self.geometry("400x500")
        self.configure(bg="#1e1e1e")
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._populate_folders()

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg="#1e1e1e")
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Folder list
        list_frame = tk.Frame(main_frame, bg="#1e1e1e")
        list_frame.pack(fill='both', expand=True, pady=5)

        self.folder_listbox = tk.Listbox(list_frame, bg="#2a2f37", fg="#e6e6e6", selectbackground="#007acc")
        self.folder_listbox.pack(side='left', fill='both', expand=True)

        scrollbar = ttk.Scrollbar(list_frame, command=self.folder_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.folder_listbox.config(yscrollcommand=scrollbar.set)

        # Buttons
        button_frame = tk.Frame(main_frame, bg="#1e1e1e")
        button_frame.pack(fill='x', pady=5)

        ttk.Button(button_frame, text="Add", command=self._add_folder).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Rename", command=self._rename_folder).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete", command=self._delete_folder).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=self.destroy).pack(side='right', padx=5)

    def _populate_folders(self):
        self.folder_listbox.delete(0, tk.END)
        for folder in self.winners_manager.get_all_folders():
            self.folder_listbox.insert(tk.END, folder)

    def _add_folder(self):
        new_name = simpledialog.askstring("New Folder", "Enter new folder name:", parent=self)
        if new_name:
            if self.winners_manager.add_folder(new_name):
                self._populate_folders()
            else:
                messagebox.showerror("Error", f"Folder '{new_name}' already exists.", parent=self)

    def _rename_folder(self):
        selected_index = self.folder_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("No Selection", "Please select a folder to rename.", parent=self)
            return

        old_name = self.folder_listbox.get(selected_index)
        if old_name == "Default":
            messagebox.showerror("Error", "Cannot rename the 'Default' folder.", parent=self)
            return

        new_name = simpledialog.askstring("Rename Folder", f"Enter new name for '{old_name}':", parent=self)
        if new_name:
            if self.winners_manager.rename_folder(old_name, new_name):
                self._populate_folders()
            else:
                messagebox.showerror("Error", f"Folder '{new_name}' already exists or is invalid.", parent=self)

    def _delete_folder(self):
        selected_index = self.folder_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("No Selection", "Please select a folder to delete.", parent=self)
            return

        folder_name = self.folder_listbox.get(selected_index)
        if folder_name == "Default":
            messagebox.showerror("Error", "Cannot delete the 'Default' folder.", parent=self)
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the folder '{folder_name}'?\nAll videos in this folder will be moved to 'Default'.", parent=self):
            if self.winners_manager.remove_folder(folder_name):
                self._populate_folders()
            else:
                messagebox.showerror("Error", "Failed to delete folder.", parent=self)
