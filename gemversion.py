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
        self.root.title("YouTube Audio to Video Converter")
        self.root.geometry("600x550")
        self.root.minsize(500, 450)
        self.log_queue = queue.Queue()

        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        self.audio_files = []
        self.image_file = None
        self.output_dir = None
        self.pad_crop_mode = "pad"

        self.create_widgets()
        self.process_log_queue()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="1. Select Your Files", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        self.audio_button = ttk.Button(input_frame, text="Select Audio Files", command=self.select_audio)
        self.audio_button.pack(fill=tk.X, pady=5)
        self.audio_label = ttk.Label(input_frame, text="No audio files selected.")
        self.audio_label.pack()
        self.image_button = ttk.Button(input_frame, text="Select Cover Image", command=self.select_image)
        self.image_button.pack(fill=tk.X, pady=5)
        self.image_label = ttk.Label(input_frame, text="No image selected.")
        self.image_label.pack()

        output_frame = ttk.LabelFrame(main_frame, text="2. Choose Output Location", padding="10")
        output_frame.pack(fill=tk.X, pady=5)
        self.output_button = ttk.Button(output_frame, text="Select Output Directory", command=self.select_output_dir)
        self.output_button.pack(fill=tk.X, pady=5)
        self.output_label = ttk.Label(output_frame, text="No output directory selected.")
        self.output_label.pack()

        options_frame = ttk.LabelFrame(main_frame, text="3. Conversion Options", padding="10")
        options_frame.pack(fill=tk.X, pady=5)
        self.pad_crop_button = ttk.Button(options_frame, text="Image Sizing (Pad/Crop)", command=self.select_pad_crop)
        self.pad_crop_button.pack(fill=tk.X, pady=5)
        self.pad_crop_label = ttk.Label(options_frame, text="Current setting: Pad (adds black bars)")
        self.pad_crop_label.pack()

        control_frame = ttk.LabelFrame(main_frame, text="4. Start Conversion", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        self.start_button = ttk.Button(control_frame, text="Start Conversion", command=self.start_conversion, state='disabled')
        self.start_button.pack(fill=tk.X, pady=5)
        self.cancel_button = ttk.Button(control_frame, text="Cancel Conversion", command=self.cancel_conversion, state='disabled')
        self.cancel_button.pack(fill=tk.X, pady=5)

        progress_frame = ttk.Frame(main_frame, padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        self.status_label = ttk.Label(progress_frame, text="Ready to convert!")
        self.status_label.pack(fill=tk.X, pady=5)
        self.file_progress = ttk.Progressbar(progress_frame, orient='horizontal', length=100, mode='determinate')
        self.file_progress.pack(fill=tk.X, pady=2)
        self.batch_label = ttk.Label(progress_frame, text="Overall Progress")
        self.batch_label.pack(fill=tk.X, pady=5)
        self.batch_progress = ttk.Progressbar(progress_frame, orient='horizontal', length=100, mode='determinate')
        self.batch_progress.pack(fill=tk.X, pady=2)
        self.details_button = ttk.Button(progress_frame, text="Show Details", command=self.show_details)
        self.details_button.pack(pady=10)
        self.console = None

    def update_start_button_state(self):
        if self.audio_files and self.image_file and self.output_dir:
            self.start_button.config(state='normal')
        else:
            self.start_button.config(state='disabled')

    def select_audio(self):
        files = filedialog.askopenfilenames(title="Select Audio Files", filetypes=[("Audio files", "*.mp3 *.wav *.flac *.aac *.ogg"), ("All files", "*.*")])
        if files:
            self.audio_files = list(files)
            self.audio_label.config(text=f"{len(self.audio_files)} audio file(s) selected.")
            self.log(f"🎵 Selected {len(self.audio_files)} audio file(s).")
        self.update_start_button_state()

    def select_image(self):
        self.image_file = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")])
        if self.image_file:
            self.image_label.config(text=os.path.basename(self.image_file))
            self.log(f"🖼 Selected image: {self.image_file}")
        self.update_start_button_state()

    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory(title="Select Output Directory")
        if self.output_dir:
            self.output_label.config(text=self.output_dir)
            self.log(f"💾 Output directory: {self.output_dir}")
        self.update_start_button_state()

    def select_pad_crop(self):
        popup = tk.Toplevel(self.root)
        popup.title("Image Sizing")
        popup.geometry("300x150")
        ttk.Label(popup, text="How should the image fit the video?").pack(padx=10, pady=10)

        def choose(choice):
            self.pad_crop_mode = choice
            self.pad_crop_label.config(text=f"Current setting: {choice.capitalize()}")
            self.log(f"🖌 Pad/Crop mode: {self.pad_crop_mode}")
            popup.destroy()

        ttk.Button(popup, text="Pad (add black bars)", command=lambda: choose("pad")).pack(pady=5)
        ttk.Button(popup, text="Crop (fill screen)", command=lambda: choose("crop")).pack(pady=5)

    def start_conversion(self):
        self.start_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.file_progress['value'] = 0
        self.batch_progress['value'] = 0
        threading.Thread(target=self.run_batch_conversion, daemon=True).start()

    def run_batch_conversion(self):
        self.cancelled = False
        vf = "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=w=1920:h=1080:x=(ow-iw)/2:y=(oh-ih)/2" if self.pad_crop_mode == "pad" \
            else "scale=w=1920:h=1080:force_original_aspect_ratio=increase,crop=w=1920:h=1080"
        
        for i, audio_file in enumerate(self.audio_files):
            if self.cancelled:
                self.log("🛑 Batch conversion cancelled by user.")
                break
            
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
            self.run_ffmpeg(cmd, i)

        if not self.cancelled:
            self.status_label.config(text="All conversions finished!")
            self.log("\n🎉 Batch conversion finished!")
            messagebox.showinfo("Success", f"All conversions finished!\nOutput directory: {self.output_dir}")

        self.start_button.config(state='normal')
        self.cancel_button.config(state='disabled')

    def run_ffmpeg(self, cmd, file_index):
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        
        for line in self.process.stdout:
            self.log(line.strip())
        
        self.process.wait()
        
        if self.process.returncode != 0 and not self.cancelled:
            self.log(f"❌ Conversion failed for {cmd[-1]}")
            messagebox.showerror("Conversion Error", f"Failed to convert {os.path.basename(cmd[-1])}. Check the details for more information.")
        
        if not self.cancelled:
            self.batch_progress['value'] = ((file_index + 1) / len(self.audio_files)) * 100
        
        self.process = None

    def cancel_conversion(self):
        self.cancelled = True
        if self.process:
            self.process.kill()
            self.log("🛑 Conversion process terminated by user.")
        self.start_button.config(state='normal')
        self.cancel_button.config(state='disabled')


    def log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if self.console and self.console.winfo_exists():
                    self.console.configure(state='normal')
                    self.console.insert(tk.END, message + "\n")
                    self.console.see(tk.END)
                    self.console.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def show_details(self):
        if not self.console or not self.console.winfo_exists():
            details_window = tk.Toplevel(self.root)
            details_window.title("Conversion Details")
            details_window.geometry("700x400")
            self.console = scrolledtext.ScrolledText(details_window, width=80, height=20, state='disabled')
            self.console.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        messagebox.showerror("Error", "FFmpeg is not installed or not in your system's PATH. Please install FFmpeg to use this application.")
    else:
        app = YouTubeAudioBatchConverter()
        app.run()