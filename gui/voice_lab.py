# -*- coding: utf-8 -*-
"""
Voice Lab (Beta) - Type-to-Clone Feature

This module provides a user interface and backend logic for synthesizing voice
clones from text using Coqui XTTSv2, with optional voice conversion via
Replay or RVC.

---
CONFIGURATION:
- The first time you run this, it will create `voice_lab_settings.json` in
  the application's root directory.
- You must review and correct the paths in the "Paths" panel of the UI.
- Default paths are provided but may not match your system.

COMMON ERRORS:
1. "TTS executable not found":
   - Verify the path to `tts.exe` is correct in the settings.
   - Ensure your Coqui TTS virtual environment is correctly set up.

2. "FFmpeg not detected":
   - Install FFmpeg from https://ffmpeg.org/download.html
   - Add the `bin` directory of your FFmpeg installation to your system's
     PATH environment variable.

3. "Conversion failed":
   - Check the specific error in the status log. It's often a missing model
     file or an incorrect path to the Replay/RVC executable/script.
   - Ensure the required Python environment for RVC is activated or the
     correct `python.exe` is specified.

4. "Access Denied" or permission errors running commands:
   - Try running the main application as an administrator.

---
© 2024 - Your Name. All Rights Reserved.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import subprocess
import threading
import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

# --- Constants ---
SETTINGS_FILE = "voice_lab_settings.json"
LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar",
    "zh-cn", "ja", "hu", "ko"
]
DEFAULT_PATHS = {
    "tts_exe": "C:/VoiceLab/env311/Scripts/tts.exe",
    "python_exe": "C:/VoiceLab/env311/Scripts/python.exe",
    "outputs_dir": "C:/VoiceLab/outputs",
    "ref_wav": "C:/VoiceLab/samples/0816_ref.wav",
    "replay_exe": "C:/Program Files/Replay/replay-cli.exe",
    "replay_model": "C:/ReplayModels/YourVoice.rpl",
    "rvc_repo_dir": "C:/RVC",
    "rvc_script": "infer_cli.py",
    "rvc_model": "C:/RVC/models/yourvoice.pth",
    "rvc_index": "C:/RVC/models/yourvoice.index",
}

class VoiceLabSettingsManager:
    """Manages settings for the Voice Lab, stored in a JSON file."""

    def __init__(self, settings_file: str = SETTINGS_FILE):
        self.settings_path = Path(settings_file)
        self.settings = {}
        self.load_settings()

    def get_defaults(self) -> Dict[str, Any]:
        """Returns a dictionary of default settings."""
        return {
            "paths": DEFAULT_PATHS,
            "options": {
                "language": "en",
                "speed": 1.0,
                "pitch": 0.0,
                "last_used_model": "replay" # 'replay' or 'rvc'
            }
        }

    def load_settings(self):
        """Loads settings, merging with defaults to ensure all keys exist."""
        defaults = self.get_defaults()
        if not self.settings_path.exists():
            self.settings = defaults
            self.save_settings()
            return

        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
            self.settings = self._merge_dicts(defaults, user_settings)
        except (json.JSONDecodeError, TypeError):
            self.settings = defaults

        self.save_settings()

    def save_settings(self):
        """Saves current settings to the JSON file."""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Error saving Voice Lab settings: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieves a setting value using a dot-separated path."""
        keys = key_path.split('.')
        value = self.settings
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any):
        """Sets a setting value using a dot-separated path and saves."""
        keys = key_path.split('.')
        d = self.settings
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        self.save_settings()

    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Recursively merges two dictionaries."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key] = self._merge_dicts(base[key], value)
            else:
                base[key] = value
        return base


class VoiceLabPane(tk.Frame):
    """
    A Tkinter Frame containing the UI and logic for the Voice Lab feature.
    """
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.configure(bg="#2c2c2c")

        self.settings_manager = VoiceLabSettingsManager()
        self.last_output_file = None
        self.is_busy = False

        self.path_vars = {key: tk.StringVar() for key in DEFAULT_PATHS.keys()}
        self.language_var = tk.StringVar()
        self.speed_var = tk.DoubleVar(value=1.0)
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.consent_var = tk.BooleanVar()

        self.build_ui()
        self.load_settings_to_ui()

        self.after(250, self.preflight_checks)

    def preflight_checks(self):
        """Performs initial checks for required tools and paths."""
        self.update_status("Performing pre-flight checks...")
        if not check_ffmpeg():
            self.update_status("FFmpeg not detected on PATH. Please install it.", is_error=True)
        else:
            self.update_status("✓ FFmpeg found.")
        outputs_dir = Path(self.path_vars["outputs_dir"].get())
        if not outputs_dir.exists():
            self.update_status(f"Outputs directory not found. Creating it...")
            try:
                outputs_dir.mkdir(parents=True, exist_ok=True)
                self.update_status("✓ Outputs directory created.")
            except Exception as e:
                self.update_status(f"Failed to create outputs directory: {e}", is_error=True)
        else:
            self.update_status("✓ Outputs directory found.")
        if not Path(self.path_vars["tts_exe"].get()).exists():
            self.update_status(f"TTS executable not found. Please check path in Settings.", is_error=True)
        else:
            self.update_status("✓ TTS executable found.")
        self.update_status("Pre-flight checks complete.")

    def build_ui(self):
        """Constructs the user interface."""
        # The TabManager uses .place() on this frame, so we should not call .pack() here.
        paned_window = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned_window.pack(fill="both", expand=True, padx=10, pady=10)

        top_frame = ttk.Frame(paned_window, padding=10)
        paned_window.add(top_frame, weight=3)

        notebook = ttk.Notebook(top_frame)
        notebook.pack(fill="both", expand=True)

        main_tab = ttk.Frame(notebook, padding=(10, 15))
        paths_tab = ttk.Frame(notebook, padding=(10, 15))

        notebook.add(main_tab, text="Clone")
        notebook.add(paths_tab, text="Paths & Settings")

        self._create_main_tab(main_tab)
        self._create_paths_tab(paths_tab)

        status_frame = ttk.Frame(paned_window, padding=10)
        paned_window.add(status_frame, weight=1)
        self._create_status_panel(status_frame)

    def _create_main_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        tk.Label(parent, text="Text to Synthesize:").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        self.text_input = tk.Text(parent, height=8, width=80, wrap="word", relief=tk.SOLID, borderwidth=1)
        self.text_input.grid(row=1, column=0, columnspan=2, sticky="nsew")
        parent.rowconfigure(1, weight=1)
        self._create_path_entry(parent, "Reference WAV:", "ref_wav", 2, file_types=[("WAV files", "*.wav")])
        options_frame = ttk.LabelFrame(parent, text="Options", padding=10)
        options_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        options_frame.columnconfigure(1, weight=1)
        tk.Label(options_frame, text="Language:").grid(row=0, column=0, sticky="w")
        lang_combo = ttk.Combobox(options_frame, textvariable=self.language_var, values=LANGUAGES, state="readonly", width=10)
        lang_combo.grid(row=0, column=1, sticky="w", padx=5)
        tk.Label(options_frame, text="Speed:").grid(row=1, column=0, sticky="w", pady=(5,0))
        ttk.Scale(options_frame, from_=0.8, to=1.2, orient=tk.HORIZONTAL, variable=self.speed_var).grid(row=1, column=1, sticky="ew", padx=5, pady=(5,0))
        tk.Label(options_frame, text="Pitch:").grid(row=2, column=0, sticky="w", pady=(5,0))
        ttk.Scale(options_frame, from_=-4.0, to=4.0, orient=tk.HORIZONTAL, variable=self.pitch_var).grid(row=2, column=1, sticky="ew", padx=5, pady=(5,0))

        consent_check = ttk.Checkbutton(parent, text="I have rights/consent to clone this voice and will not impersonate without permission.", variable=self.consent_var, command=self._toggle_generate_buttons)
        consent_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=10)

        buttons_frame = ttk.Frame(parent)
        buttons_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        for i in range(4): buttons_frame.columnconfigure(i, weight=1)

        self.generate_buttons = {}
        self.generate_buttons["xtts"] = ttk.Button(buttons_frame, text="Generate Base (XTTS)", command=self._start_xtts_only)
        self.generate_buttons["xtts"].grid(row=0, column=0, sticky="ew", padx=2)
        self.generate_buttons["replay"] = ttk.Button(buttons_frame, text="Convert with Replay", command=self._start_replay_only)
        self.generate_buttons["replay"].grid(row=0, column=1, sticky="ew", padx=2)
        self.generate_buttons["rvc"] = ttk.Button(buttons_frame, text="Convert with RVC", command=self._start_rvc_only)
        self.generate_buttons["rvc"].grid(row=0, column=2, sticky="ew", padx=2)
        self.generate_buttons["auto"] = ttk.Button(buttons_frame, text="Type -> Clone (Auto)", command=self._start_auto_pipeline)
        self.generate_buttons["auto"].grid(row=0, column=3, sticky="ew", padx=2)
        self._toggle_generate_buttons()

    def _create_paths_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        path_labels = {"tts_exe": "TTS exe (tts.exe)", "python_exe": "RVC Python (python.exe)", "outputs_dir": "Outputs Directory", "replay_exe": "Replay CLI (replay-cli.exe)", "replay_model": "Replay Model (*.rpl)", "rvc_repo_dir": "RVC Repo Directory", "rvc_script": "RVC Script (e.g., infer_cli.py)", "rvc_model": "RVC Model (*.pth)", "rvc_index": "RVC Index File (*.index)"}
        row = 0
        for key, label in path_labels.items():
            is_dir = "dir" in key
            self._create_path_entry(parent, label, key, row, is_dir=is_dir)
            row += 1
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1
        ttk.Button(parent, text="Save All Path Settings", command=self.save_ui_to_settings).grid(row=row, column=1, sticky="e", padx=5)

    def _create_status_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        log_frame = ttk.LabelFrame(parent, text="Status Log", padding=5)
        log_frame.grid(row=0, column=0, sticky="nsew", columnspan=2)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.status_log = tk.Text(log_frame, height=5, wrap="word", relief=tk.SOLID, borderwidth=1, state="disabled")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.status_log.yview)
        self.status_log['yscrollcommand'] = log_scroll.set
        self.status_log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        buttons_frame = ttk.Frame(parent, padding=(0, 10))
        buttons_frame.grid(row=1, column=0, sticky="ew", columnspan=2)
        self.play_button = ttk.Button(buttons_frame, text="▶️ Play Last Output", state="disabled", command=self._play_last_output)
        self.play_button.pack(side="left")
        ttk.Button(buttons_frame, text="📂 Open Outputs Folder", command=self._open_outputs_folder).pack(side="left", padx=10)

    def _create_path_entry(self, parent, label_text: str, setting_key: str, row: int, is_dir: bool = False, file_types: list = None):
        tk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Entry(parent, textvariable=self.path_vars[setting_key], width=70).grid(row=row, column=1, sticky="ew", pady=2)
        def browse():
            path = filedialog.askdirectory(title=f"Select {label_text}") if is_dir else filedialog.askopenfilename(title=f"Select {label_text}", filetypes=file_types or [("All files", "*.*")])
            if path: self.path_vars[setting_key].set(path.replace("\\", "/"))
        ttk.Button(parent, text="Browse...", command=browse).grid(row=row, column=2, sticky="e", padx=5, pady=2)

    def _toggle_generate_buttons(self):
        state = "normal" if self.consent_var.get() and not self.is_busy else "disabled"
        for button in self.generate_buttons.values():
            button.config(state=state)

    def _play_last_output(self):
        if self.last_output_file and Path(self.last_output_file).exists():
            self.update_status(f"Opening {self.last_output_file}...")
            try: os.startfile(self.last_output_file)
            except Exception as e: messagebox.showerror("Playback Error", f"Could not open file: {e}")
        else: messagebox.showwarning("No File", "No output file has been generated yet.")

    def _open_outputs_folder(self):
        outputs_dir = self.path_vars["outputs_dir"].get()
        if outputs_dir and Path(outputs_dir).exists():
            try: os.startfile(outputs_dir)
            except Exception as e: messagebox.showerror("Error", f"Could not open folder: {e}")
        else: messagebox.showwarning("Directory Not Found", "The outputs directory does not exist.")

    def _start_auto_pipeline(self):
        self.update_status("--- Starting Auto Type-to-Clone Pipeline ---")
        type_to_clone(self)

    def _start_xtts_only(self):
        text, ref_wav, lang = self.text_input.get("1.0", tk.END).strip(), self.path_vars["ref_wav"].get(), self.language_var.get()
        if not text or not ref_wav: return messagebox.showerror("Input Missing", "Please provide text and a reference WAV file.")
        self.update_status("--- Starting XTTS Generation Only ---")
        def on_complete(success, path):
            if success: self.last_output_file, self.play_button.config(state="normal"), self.update_status(f"SUCCESS! Final audio at: {path}")
            else: self.update_status(f"XTTS-only generation failed: {path}", is_error=True)
        run_xtts(self, text, ref_wav, lang, on_complete)

    def _start_replay_only(self):
        if not self.last_output_file or not Path(self.last_output_file).exists(): return messagebox.showerror("Input Missing", "No base file to convert. Please run 'Generate Base' first.")
        self.update_status("--- Starting Replay Conversion Only ---")
        def on_complete(success, path):
            if success: self.last_output_file, self.play_button.config(state="normal"), self.update_status(f"SUCCESS! Final audio at: {path}")
            else: self.update_status(f"Replay conversion failed: {path}", is_error=True)
        run_replay(self, self.last_output_file, on_complete)

    def _start_rvc_only(self):
        if not self.last_output_file or not Path(self.last_output_file).exists(): return messagebox.showerror("Input Missing", "No base file to convert. Please run 'Generate Base' first.")
        self.update_status("--- Starting RVC Conversion Only ---")
        def on_complete(success, path):
            if success: self.last_output_file, self.play_button.config(state="normal"), self.update_status(f"SUCCESS! Final audio at: {path}")
            else: self.update_status(f"RVC conversion failed: {path}", is_error=True)
        run_rvc(self, self.last_output_file, on_complete)

    def load_settings_to_ui(self):
        for key, var in self.path_vars.items(): var.set(self.settings_manager.get(f"paths.{key}", DEFAULT_PATHS.get(key, "")))
        self.language_var.set(self.settings_manager.get("options.language", "en"))
        self.speed_var.set(self.settings_manager.get("options.speed", 1.0))
        self.pitch_var.set(self.settings_manager.get("options.pitch", 0.0))

    def save_ui_to_settings(self):
        for key, var in self.path_vars.items(): self.settings_manager.set(f"paths.{key}", var.get())
        self.settings_manager.set("options.language", self.language_var.get())
        self.settings_manager.set("options.speed", self.speed_var.get())
        self.settings_manager.set("options.pitch", self.pitch_var.get())
        messagebox.showinfo("Settings Saved", "Voice Lab paths and options have been saved.", parent=self)

    def update_status(self, message: str, is_error: bool = False):
        if not self.status_log: return
        def _append():
            self.status_log.config(state="normal")
            self.status_log.insert(tk.END, f"{'ERROR: ' if is_error else ''}{message}\n")
            self.status_log.config(state="disabled")
            self.status_log.see(tk.END)
        self.after(0, _append)

    def _run_command_in_thread(self, command: List[str], on_complete: callable):
        self.is_busy = True
        self._toggle_generate_buttons()
        def task():
            self.update_status(f"Running: {' '.join(command)}")
            try:
                env = os.environ.copy()
                env["COQUI_TOS_AGREED"] = "1"
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, env=env)
                for line in iter(process.stdout.readline, ''): self.update_status(line.strip())
                process.stdout.close()
                rc = process.wait()
                if rc == 0: self.after(0, on_complete, True, "Success")
                else: self.after(0, on_complete, False, f"Command failed with exit code {rc}")
            except Exception as e: self.after(0, on_complete, False, f"An error occurred: {e}")
            finally: self.is_busy = False; self.after(0, self._toggle_generate_buttons)
        threading.Thread(target=task, daemon=True).start()

def check_ffmpeg() -> bool:
    try: subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW); return True
    except: return False

def prepare_ref_wav(ref_wav_path: str, temp_dir: str) -> Optional[str]:
    if not check_ffmpeg(): raise RuntimeError("FFmpeg not found on PATH.")
    out_path = Path(temp_dir) / f"{Path(ref_wav_path).stem}_24khz_mono.wav"
    cmd = ["ffmpeg", "-i", str(ref_wav_path), "-ac", "1", "-ar", "24000", "-y", "-hide_banner", "-loglevel", "error", str(out_path)]
    try: subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW); return str(out_path)
    except Exception as e: print(f"FFmpeg failed: {e}"); return None

def run_xtts(pane: VoiceLabPane, text: str, ref_wav: str, lang: str, on_complete: callable):
    tts_exe, out_dir = pane.path_vars["tts_exe"].get(), Path(pane.path_vars["outputs_dir"].get())
    if not Path(tts_exe).exists(): return on_complete(False, "TTS executable not found.")
    out_path = out_dir / f"base_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    try:
        processed_ref = prepare_ref_wav(ref_wav, str(out_dir))
        if not processed_ref: return on_complete(False, "FFmpeg processing failed.")
    except RuntimeError as e: return on_complete(False, str(e))
    cmd = [tts_exe, "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2", "--language_idx", lang, "--speaker_wav", str(processed_ref), "--text", text, "--out_path", str(out_path)]
    pane._run_command_in_thread(cmd, lambda s, m: on_complete(s, str(out_path) if s else m))

def run_replay(pane: VoiceLabPane, input_wav: str, on_complete: callable):
    exe, model = pane.path_vars["replay_exe"].get(), pane.path_vars["replay_model"].get()
    if not all(Path(p).exists() for p in [exe, model]): return on_complete(False, "Replay not available.")
    out_path = Path(pane.path_vars["outputs_dir"].get()) / f"final_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_replay.wav"
    cmd = [exe, "--model", model, "--input", input_wav, "--output", str(out_path)]
    pane._run_command_in_thread(cmd, lambda s, m: on_complete(s, str(out_path) if s else m))

def run_rvc(pane: VoiceLabPane, input_wav: str, on_complete: callable):
    p = pane.path_vars
    py_exe, repo, script, model, index = p["python_exe"].get(), Path(p["rvc_repo_dir"].get()), p["rvc_script"].get(), Path(p["rvc_model"].get()), Path(p["rvc_index"].get())
    if not all(Path(x).exists() for x in [py_exe, repo, repo/script, model]): return on_complete(False, "RVC not available.")
    out_path = Path(p["outputs_dir"].get()) / f"final_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_rvc.wav"
    cmd = [py_exe, str(repo/script), "--model", str(model), "--input", input_wav, "--output", str(out_path), "--f0", "1", "--transpose", "0"]
    if index.exists(): cmd.extend(["--index", str(index)])
    pane._run_command_in_thread(cmd, lambda s, m: on_complete(s, str(out_path) if s else m))

def type_to_clone(pane: VoiceLabPane):
    text, ref_wav, lang = pane.text_input.get("1.0", tk.END).strip(), pane.path_vars["ref_wav"].get(), pane.language_var.get()
    if not text or not ref_wav: return messagebox.showerror("Input Missing", "Text and reference WAV are required.")

    def on_rvc_done(success, path):
        if success: pane.last_output_file, pane.update_status(f"SUCCESS! Final audio: {path}")
        else: pane.update_status(f"RVC failed. Using base XTTS file.", is_error=True)
        pane.play_button.config(state="normal")

    def on_replay_done(success, path):
        if success: pane.last_output_file, pane.update_status(f"SUCCESS! Final audio: {path}"), pane.play_button.config(state="normal")
        else: run_rvc(pane, pane.last_output_file, on_rvc_done)

    def on_xtts_done(success, path):
        if not success: return pane.update_status(f"XTTS generation failed: {path}", is_error=True)
        pane.last_output_file = path
        pane.update_status(f"Base generation complete: {path}")
        if all(Path(p).exists() for p in [pane.path_vars["replay_exe"].get(), pane.path_vars["replay_model"].get()]):
            run_replay(pane, path, on_replay_done)
        else:
            run_rvc(pane, path, on_rvc_done)

    run_xtts(pane, text, ref_wav, lang, on_xtts_done)
