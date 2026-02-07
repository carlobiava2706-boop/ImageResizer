#!/usr/bin/env python3
"""
Image Resizer - Cross Platform
Optimized for Windows packaging, compatible with macOS
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageOps
import os
import sys
import json
import platform
import logging
from pathlib import Path

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class ImageResizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ridimensiona Immagini")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        
        # Platform detection
        self.is_macos = platform.system() == 'Darwin'
        self.is_windows = platform.system() == 'Windows'
        
        # macOS-specific setup
        if self.is_macos:
            self.root.createcommand('tk::mac::Quit', self.quit_app)
            try:
                self.root.tk.call('tk', 'scaling', 2.0)
            except:
                pass
        
        # Windows-specific DPI awareness
        if self.is_windows:
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except:
                pass
        
        # Constants
        self.RECENT_FILES_PATH = Path.home() / ".image_resizer_recent.json"
        self.MAX_RECENT = 5
        self.SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif', '.gif'}
        
        # State variables
        self.filepath = None
        self.original_image = None
        self.processed_image = None
        self.tk_image = None
        self.resize_mode = tk.StringVar(value="fit")
        self.aspect_locked = tk.BooleanVar(value=True)  # Default to locked
        self.preserve_exif = tk.BooleanVar(value=True)
        self.orig_width = 0
        self.orig_height = 0
        self.aspect_ratio = 1.0
        self.mode_desc_widgets = []
        self._preview_job = None
        
        # Setup UI
        self.setup_styles()
        self.setup_ui()
        self.setup_bindings()
        self.setup_menu()
        self.load_recent_files()
        
        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Process command line arguments (for files opened via drag-drop to icon)
        self.root.after(100, self.process_argv)
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", padding=6)
        style.configure("TLabelframe", padding=10)
        style.configure("Header.TLabel", font=("Helvetica", 10, "bold"))
        
    def setup_ui(self):
        # Main container
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left control panel
        left_frame = ttk.Frame(main_paned, padding="10", width=350)
        left_frame.pack_propagate(False)
        main_paned.add(left_frame, weight=0)
        
        # File info section
        file_frame = ttk.LabelFrame(left_frame, text="Immagine Sorgente", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_label = ttk.Label(file_frame, text="Nessuna Immagine Caricata", foreground="gray")
        self.file_label.pack(anchor=tk.W)
        
        self.dims_label = ttk.Label(file_frame, text="Dimensioni: -", font=("Courier", 9))
        self.dims_label.pack(anchor=tk.W, pady=(5, 0))
        
        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Apri...", command=self.load_image).pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        # FIX: Store reference to save button
        self.save_btn = ttk.Button(btn_frame, text="Salva", command=self.save_image, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(5, 0))
        
        # Dimensions section
        dim_frame = ttk.LabelFrame(left_frame, text="Dimensioni Finali", padding=10)
        dim_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Width
        ttk.Label(dim_frame, text="Larghezza:", style="Header.TLabel").grid(row=0, column=0, sticky=tk.W)
        vcmd = (self.root.register(self.validate_dimension_input), '%P')
        self.entry_width = ttk.Spinbox(dim_frame, from_=1, to=99999, width=10, validate='key', validatecommand=vcmd)
        self.entry_width.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        self.entry_width.set("800")
        self.entry_width.bind('<KeyRelease>', lambda e: self.on_dim_change("width"))
        
        # Height
        ttk.Label(dim_frame, text="Altezza:", style="Header.TLabel").grid(row=1, column=0, sticky=tk.W)
        self.entry_height = ttk.Spinbox(dim_frame, from_=1, to=99999, width=10, validate='key', validatecommand=vcmd)
        self.entry_height.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)
        self.entry_height.set("600")
        self.entry_height.bind('<KeyRelease>', lambda e: self.on_dim_change("height"))
        
        # Lock aspect ratio
        ttk.Checkbutton(dim_frame, text="Blocca Proporzioni", variable=self.aspect_locked, 
                       command=self.toggle_aspect_lock).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Quick buttons
        quick_frame = ttk.Frame(dim_frame)
        quick_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(5, 0))
        ttk.Button(quick_frame, text="Originali", command=self.reset_dimensions).pack(side=tk.LEFT, expand=True, padx=(0, 2))
        ttk.Button(quick_frame, text="Scambia", command=self.swap_dimensions).pack(side=tk.LEFT, expand=True, padx=2)
        
        # Resize mode section
        mode_frame = ttk.LabelFrame(left_frame, text="Modalità", padding=10)
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        modes = [
            ("fit", "Adatta", "Mantiene proporzioni, sfondo trasparente/bianco"),
            ("cut", "Ritaglia", "Riempie tagliando i bordi"),
            ("stretch", "Allunga", "Distorce per riempire")
        ]
        
        for val, text, tooltip in modes:
            container = ttk.Frame(mode_frame)
            container.pack(anchor=tk.W, fill=tk.X, pady=2)
            
            rb = ttk.Radiobutton(container, text=text, variable=self.resize_mode, 
                               value=val, command=self.on_mode_change)
            rb.pack(anchor=tk.W)
            
            desc = ttk.Label(container, text=tooltip, font=("Arial", 8), 
                            foreground="gray", wraplength=280)
            
            if val == self.resize_mode.get():
                desc.pack(anchor=tk.W, padx=20, pady=(0, 5))
                
            self.mode_desc_widgets.append((val, desc))
        
        # Options
        opt_frame = ttk.LabelFrame(left_frame, text="Opzioni", padding=10)
        opt_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(opt_frame, text="Correggi rotazione EXIF", variable=self.preserve_exif).pack(anchor=tk.W)
        
        # Recent files
        recent_frame = ttk.LabelFrame(left_frame, text="Recenti", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True)
        
        list_container = ttk.Frame(recent_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.recent_listbox = tk.Listbox(list_container, height=5, activestyle="none", 
                                        yscrollcommand=scrollbar.set)
        self.recent_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.recent_listbox.yview)
        
        self.recent_listbox.bind('<Double-Button-1>', self.on_recent_select)
        
        # Right panel
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # Toolbar
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(toolbar, text="Anteprima:", style="Header.TLabel").pack(side=tk.LEFT)
        self.preview_info = ttk.Label(toolbar, text="", foreground="gray")
        self.preview_info.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Button(toolbar, text="Aggiorna", command=self.update_preview).pack(side=tk.RIGHT)
        
        # Canvas
        self.canvas_frame = ttk.Frame(right_frame, relief="sunken", borderwidth=1)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>', lambda e: self.load_image())
        
        self.update_placeholder()
        
    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        file_menu.add_command(label="Apri", command=self.load_image, accelerator="Ctrl+O" if not self.is_macos else "Cmd+O")
        file_menu.add_command(label="Salva", command=self.save_image, accelerator="Ctrl+S" if not self.is_macos else "Cmd+S")
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.quit_app)
        
    def setup_bindings(self):
        if self.is_macos:
            self.root.bind('<Command-o>', lambda e: self.load_image())
            self.root.bind('<Command-s>', lambda e: self.save_image())
            self.root.bind('<Command-q>', lambda e: self.quit_app())
        else:
            self.root.bind('<Control-o>', lambda e: self.load_image())
            self.root.bind('<Control-s>', lambda e: self.save_image())
            
        self.root.bind('<Escape>', lambda e: self.root.quit())
        self.root.bind('<Configure>', self.on_window_resize)
        
    def process_argv(self):
        """Handle files opened via drag to icon or command line"""
        if len(sys.argv) > 1:
            filepath = sys.argv[1]
            if Path(filepath).exists():
                ext = Path(filepath).suffix.lower()
                if ext in self.SUPPORTED_FORMATS:
                    self.load_image(filepath)
                    
    def validate_dimension_input(self, value):
        """Validate numeric input only"""
        if value == "":
            return True
        try:
            int(value)
            return True
        except ValueError:
            return False
            
    def on_window_resize(self, event):
        """Debounce resize events"""
        if event.widget != self.root:
            return
        if self._preview_job:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(150, self.update_preview)
        
    def update_placeholder(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w < 10 or h < 10:
            self.root.after(100, self.update_placeholder)
            return
            
        text = "Clicca per aprire un'immagine"
        self.canvas.create_text(w//2, h//2, text=text, fill="#888888", 
                               font=("Helvetica", 14), justify=tk.CENTER)
        
    def on_dim_change(self, source):
        """Update dimensions with aspect ratio lock"""
        if not self.original_image:
            return
            
        if self.aspect_locked.get():
            try:
                if source == "width":
                    w = int(self.entry_width.get())
                    new_h = int(w / self.aspect_ratio)
                    self.entry_height.set(str(new_h))
                else:
                    h = int(self.entry_height.get())
                    new_w = int(h * self.aspect_ratio)
                    self.entry_width.set(str(new_w))
            except (ValueError, ZeroDivisionError):
                pass
                
        # Debounce preview update
        if self._preview_job:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(100, self.update_preview)
        
    def on_mode_change(self):
        for val, desc in self.mode_desc_widgets:
            desc.pack_forget()
        for val, desc in self.mode_desc_widgets:
            if val == self.resize_mode.get():
                desc.pack(anchor=tk.W, padx=20, pady=(0, 5))
                break
        self.update_preview()
        
    def toggle_aspect_lock(self):
        if self.aspect_locked.get() and self.original_image:
            try:
                w = int(self.entry_width.get())
                h = int(w * self.aspect_ratio)
                self.entry_height.set(str(h))
                self.update_preview()
            except ValueError:
                pass
                
    def reset_dimensions(self):
        if self.original_image:
            self.entry_width.set(str(self.orig_width))
            self.entry_height.set(str(self.orig_height))
            self.update_preview()
            
    def swap_dimensions(self):
        w, h = self.entry_width.get(), self.entry_height.get()
        self.entry_width.set(h)
        self.entry_height.set(w)
        self.on_dim_change("width")
        
    def get_dimensions(self):
        try:
            w = int(self.entry_width.get())
            h = int(self.entry_height.get())
            if w < 1 or h < 1:
                return None, None
            return w, h
        except ValueError:
            return None, None
            
    def apply_exif_orientation(self, img):
        """Apply EXIF rotation if present"""
        try:
            exif = img._getexif()
            if exif:
                orientation = exif.get(274)
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except:
            pass
        return img
            
    def load_image(self, filepath=None):
        if not filepath:
            filepath = filedialog.askopenfilename(
                filetypes=[
                    ("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tiff;*.tif;*.gif"),
                    ("All Files", "*.*")
                ]
            )
            
        if not filepath:
            return
            
        filepath = Path(filepath)
        
        try:
            self.original_image = Image.open(filepath)
            self.filepath = filepath
            
            # Apply EXIF rotation
            if self.preserve_exif.get():
                self.original_image = self.apply_exif_orientation(self.original_image)
            
            self.orig_width, self.orig_height = self.original_image.size
            self.aspect_ratio = self.orig_width / self.orig_height if self.orig_height else 1.0
            
            self.file_label.config(text=filepath.name, foreground="black")
            self.dims_label.config(text=f"Originali: {self.orig_width} × {self.orig_height}")
            
            self.entry_width.set(str(self.orig_width))
            self.entry_height.set(str(self.orig_height))
            
            self.add_recent_file(str(filepath))
            self.save_btn.config(state=tk.NORMAL)
            
            self.canvas.delete("all")
            self.update_preview()
            self.status_var.set(f"Caricato: {filepath.name}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare:\\n{str(e)}")
            self.status_var.set("Errore di caricamento")
            
    def process_image(self, target_w, target_h):
        if not self.original_image:
            return None
            
        mode = self.resize_mode.get()
        img = self.original_image.copy()
        
        if mode == "stretch":
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
        elif mode == "cut":
            return ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
            
        elif mode == "fit":
            orig_w, orig_h = img.size
            scale = min(target_w/orig_w, target_h/orig_h)
            
            if scale >= 1:
                new_w, new_h = orig_w, orig_h
            else:
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            if img.mode in ('RGBA', 'P'):
                background = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
            else:
                background = Image.new("RGB", (target_w, target_h), (255, 255, 255))
                
            offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
            background.paste(resized, offset)
            return background
            
    def update_preview(self):
        if not self.original_image:
            return
            
        w, h = self.get_dimensions()
        if not w or not h:
            return
            
        try:
            processed = self.process_image(w, h)
            if not processed:
                return
                
            self.processed_image = processed
            
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w < 50 or canvas_h < 50:
                self.root.after(100, self.update_preview)
                return
                
            img_w, img_h = processed.size
            scale = min(canvas_w/img_w, canvas_h/img_h, 1.0)
            
            preview_w = int(img_w * scale)
            preview_h = int(img_h * scale)
            
            if scale < 1.0:
                display_img = processed.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
            else:
                display_img = processed
                
            if display_img.mode == 'RGBA':
                display_img = display_img.convert('RGB')
                
            self.tk_image = ImageTk.PhotoImage(display_img)
            
            x = (canvas_w - preview_w) // 2
            y = (canvas_h - preview_h) // 2
            
            self.canvas.delete("all")
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image, tags="image")
            
            mode_str = self.resize_mode.get().upper()
            self.preview_info.config(text=f"Output: {w}×{h} [{mode_str}]")
            
        except Exception as e:
            self.status_var.set(f"Errore anteprima: {str(e)}")
            
    def save_image(self):
        if not self.processed_image:
            messagebox.showwarning("Attenzione", "Nessuna immagine da salvare")
            return
            
        if self.filepath:
            default_name = self.filepath.stem + "_resized"
        else:
            default_name = "resized_image"
            
        save_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("WebP", "*.webp"),
                ("TIFF", "*.tiff"),
                ("BMP", "*.bmp")
            ]
        )
        
        if not save_path:
            return
            
        try:
            save_path = Path(save_path)
            img = self.processed_image.copy()
            ext = save_path.suffix.lower()
            
            save_kwargs = {}
            
            if ext in ('.jpg', '.jpeg'):
                if img.mode in ('RGBA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                save_kwargs = {'quality': 95, 'optimize': True}
                
            elif ext == '.png':
                save_kwargs = {'optimize': True}
                
            elif ext == '.webp':
                save_kwargs = {'quality': 95}
                
            img.save(save_path, **save_kwargs)
            
            self.add_recent_file(str(save_path))
            self.status_var.set(f"Salvato: {save_path.name}")
            messagebox.showinfo("Successo", f"Immagine salvata:\\n{save_path}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare:\\n{str(e)}")
            self.status_var.set("Salvataggio fallito")
            
    def add_recent_file(self, filepath):
        try:
            recent = []
            if self.RECENT_FILES_PATH.exists():
                with open(self.RECENT_FILES_PATH, 'r') as f:
                    recent = json.load(f)
                    
            if filepath in recent:
                recent.remove(filepath)
            recent.insert(0, filepath)
            recent = recent[:self.MAX_RECENT]
            
            with open(self.RECENT_FILES_PATH, 'w') as f:
                json.dump(recent, f)
                
            self.load_recent_files()
        except:
            pass
            
    def load_recent_files(self):
        self.recent_listbox.delete(0, tk.END)
        self.recent_listbox._paths = {}
        
        try:
            if not self.RECENT_FILES_PATH.exists():
                return
                
            with open(self.RECENT_FILES_PATH, 'r') as f:
                recent = json.load(f)
                
            for f in recent:
                path = Path(f)
                if path.exists():
                    self.recent_listbox.insert(tk.END, path.name)
                    self.recent_listbox.itemconfig(tk.END, {'fg': 'black'})
                    self.recent_listbox._paths[path.name] = f
                else:
                    self.recent_listbox.insert(tk.END, f"{path.name} (mancante)")
                    self.recent_listbox.itemconfig(tk.END, {'fg': 'gray'})
        except:
            pass
                
    def on_recent_select(self, event):
        selection = self.recent_listbox.curselection()
        if not selection:
            return
            
        filename = self.recent_listbox.get(selection[0])
        if "(mancante)" in filename:
            return
            
        paths = getattr(self.recent_listbox, '_paths', {})
        if filename in paths:
            self.load_image(paths[filename])
            
    def quit_app(self):
        self.root.quit()

def main():
    root = tk.Tk()
    app = ImageResizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
