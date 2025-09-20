import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import os
import re
import queue

class YouTubeAudioBatchConverter:
    def __init__(self):
        self.process = None
        self.cancelled = False
        self.root = tk.Tk()
        self.root.title("Audio → Video Utility")
        self.root.geometry("600x400")
        self.root.minsize(500, 350)
        self.log_queue = queue.Queue()

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use('vista')
        except tk.TclError:
            self.style.theme_use('clam')

        self.audio_files = []
        self.image_file = None
        self.output_dir = None

        self.create_widgets()
        self.process_log_queue()

    def create_widgets(self):
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="+ Audio", command=self.select_audio).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="− Remove", command=self.remove_selected_audio).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="× Clear", command=self.clear_all_audio).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Image…", command=self.select_image).pack(side=tk.LEFT, padx=10)
        ttk.Button(toolbar, text="Output…", command=self.select_output_dir).pack(side=tk.LEFT, padx=2)

        # File list and info
        info_frame = ttk.Frame(self.root, padding=5)
        info_frame.pack(fill=tk.BOTH, expand=True)

        self.audio_listbox = tk.Listbox(info_frame, height=5, selectmode=tk.EXTENDED)
        self.audio_listbox.pack(fill=tk.X, pady=3)

        self.image_label = ttk.Label(info_frame, text="Image: (none)")
        self.image_label.pack(anchor="w", pady=2)

        self.output_label = ttk.Label(info_frame, text="Output: (none)")
        self.output_label.pack(anchor="w", pady=2)

        # Controls row
        control_frame = ttk.Frame(self.root, padding=5)
        control_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(control_frame, text="▶ Start", command=self.start_conversion)
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.cancel_button = ttk.Button(control_frame, text="⏹ Cancel", command=self.cancel_conversion, state='disabled')
        self.cancel_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Progress
        self.status_label = ttk.Label(self.root, text="Ready.")
        self.status_label.pack(fill=tk.X, padx=5, pady=2)

        self.file_progress = ttk.Progressbar(self.root, orient='horizontal', length=100, mode='determinate')
        self.file_progress.pack(fill=tk.X, padx=5, pady=2)

        self.batch_progress = ttk.Progressbar(self.root, orient='horizontal', length=100, mode='determinate')
        self.batch_progress.pack(fill=tk.X, padx=5, pady=2)

        # Logs
        console_frame = ttk.LabelFrame(self.root, text="Logs", padding=5)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.console = scrolledtext.ScrolledText(console_frame, width=80, height=8, state='disabled')
        self.console.pack(fill=tk.BOTH, expand=True)

    def select_audio(self):
        files = filedialog.askopenfilenames(title="Select Audio Files", filetypes=[("Audio files", "*.mp3 *.wav *.flac *.aac *.ogg"), ("All files", "*.*")])
        if files:
            self.audio_files.extend(files)
            for f in files:
                self.audio_listbox.insert(tk.END, os.path.basename(f))
            self.log(f"🎵 Added {len(files)} audio file(s).")

    def select_image(self):
        self.image_file = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
        if self.image_file:
            self.image_label.config(text=f"Image: {os.path.basename(self.image_file)}")
            self.log(f"🖼 Selected image: {self.image_file}")

    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory(title="Select Output Directory")
        if self.output_dir:
            self.output_label.config(text=f"Output: {self.output_dir}")
            self.log(f"💾 Output directory: {self.output_dir}")

    def remove_selected_audio(self):
        selected_indices = self.audio_listbox.curselection()
        if not selected_indices:
            return
        selected_files = [self.audio_listbox.get(i) for i in selected_indices]
        self.audio_files = [f for f in self.audio_files if os.path.basename(f) not in selected_files]
        for i in sorted(selected_indices, reverse=True):
            self.audio_listbox.delete(i)
        self.log(f"🗑️ Removed {len(selected_files)} audio file(s).")

    def clear_all_audio(self):
        self.audio_files = []
        self.audio_listbox.delete(0, tk.END)
        self.log("🗑️ Cleared all audio files.")

    def start_conversion(self):
        if not self.audio_files or not self.image_file or not self.output_dir:
            messagebox.showwarning("Missing Info", "Please select at least one audio file, an image, and an output folder.")
            return

        self.start_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.file_progress['value'] = 0
        self.batch_progress['value'] = 0
        threading.Thread(target=self.run_batch_conversion, daemon=True).start()

    def run_batch_conversion(self):
        self.cancelled = False
        vf = "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=w=1920:h=1080:x=(ow-iw)/2:y=(oh-ih)/2"
        
        for i, audio_file in enumerate(self.audio_files):
            if self.cancelled:
                self.log("🛑 Batch conversion cancelled.")
                break

            self.file_progress['value'] = 0
            output_file = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(audio_file))[0]}.mp4")
            self.status_label.config(text=f"Converting: {os.path.basename(audio_file)}")
            self.log(f"\n🚀 Converting {audio_file} → {output_file}")

            cmd = [
                "ffmpeg", "-y", "-i", audio_file,
                "-loop", "1", "-i", self.image_file,
                "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest",
                "-vf", vf, output_file
            ]
            duration = self.get_audio_duration(audio_file)
            self.run_ffmpeg(cmd, i, duration)

        if not self.cancelled:
            self.status_label.config(text="All conversions finished!")
            self.log("\n🎉 Batch conversion finished!")
            messagebox.showinfo("Success", f"All conversions finished!\nOutput directory: {self.output_dir}")

        self.start_button.config(state='normal')
        self.cancel_button.config(state='disabled')

    def get_audio_duration(self, audio_file):
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            self.log(f"Could not get duration for {audio_file}: {e}")
            return None

    def run_ffmpeg(self, cmd, file_index, duration):
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)

        def log_output(pipe):
            for line in iter(pipe.readline, ''):
                self.log(line.strip())
            pipe.close()

        threading.Thread(target=log_output, args=(self.process.stdout,), daemon=True).start()

        time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

        for line in iter(self.process.stderr.readline, ''):
            self.log(line.strip())
            if duration:
                match = time_re.search(line)
                if match:
                    hours, minutes, seconds, ms = map(int, match.groups())
                    current_time = hours * 3600 + minutes * 60 + seconds + ms / 100
                    progress = (current_time / duration) * 100
                    self.root.after(0, self.file_progress.config, {'value': progress})

        self.process.stderr.close()
        self.process.wait()

        if self.process.returncode != 0 and not self.cancelled:
            self.log(f"❌ Conversion failed for {cmd[-1]}")
            messagebox.showerror("Conversion Error", f"Failed to convert {os.path.basename(cmd[-1])}.")

        if not self.cancelled:
            self.batch_progress['value'] = ((file_index + 1) / len(self.audio_files)) * 100
            self.file_progress['value'] = 100

        self.process = None

    def cancel_conversion(self):
        self.cancelled = True
        if self.process:
            self.process.kill()
            self.log("🛑 Conversion process terminated.")
        self.start_button.config(state='normal')
        self.cancel_button.config(state='disabled')

    def log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if self.console:
                    self.console.configure(state='normal')
                    self.console.insert(tk.END, message + "\n")
                    self.console.see(tk.END)
                    self.console.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        subprocess.run(["ffprobe", "-version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        messagebox.showerror("Error", "FFmpeg or ffprobe not found. Please install FFmpeg to use this app.")
    else:
        app = YouTubeAudioBatchConverter()
        app.run()
