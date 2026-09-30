"""
hardware_profiler.py - Moduł automatycznej detekcji sprzętu, doboru modelu i konfiguracji portable dla Whiscribe AI.
"""

import os
import sys
import subprocess
import threading
import logging
from config import get_app_dir, save_config

logger = logging.getLogger("HardwareProfiler")

MODEL_SPECS = {
    "turbo": {
        "name": "Klasa PRO: duży model (large-v3-turbo)",
        "repo_id": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "size_mb": 1500,
        "device": "cuda",
        "compute_type": "float16",
        "desc": "Zalecane dla kart NVIDIA RTX 3060, 4060+ (min. 6GB VRAM). Najwyższa dokładność i natychmiastowe dyktowanie."
    },
    "small": {
        "name": "Klasa Średnia: szybki model (small)",
        "repo_id": "Systran/faster-whisper-small",
        "size_mb": 460,
        "device": "cuda",
        "compute_type": "float16",
        "desc": "Zalecane dla starszych kart GTX (1660, 1060) lub RTX z mniejszą pamięcią. Zrównoważona szybkość i mały rozmiar."
    },
    "base": {
        "name": "Zwykły komputer / Laptop: lekki model (base)",
        "repo_id": "Systran/faster-whisper-base",
        "size_mb": 140,
        "device": "cpu",
        "compute_type": "int8",
        "desc": "Praca wyłącznie na procesorze (CPU). Działa na każdym laptopie biurowym bez dedykowanej karty graficznej."
    }
}

def detect_hardware():
    """Wykrywa dostępność CUDA oraz modele zainstalowanych kart graficznych."""
    has_cuda = False
    try:
        import ctranslate2
        has_cuda = (ctranslate2.get_cuda_device_count() > 0)
    except Exception:
        pass

    gpu_names = []
    try:
        out = subprocess.check_output(['wmic', 'path', 'win32_VideoController', 'get', 'name'], stderr=subprocess.DEVNULL, text=True)
        for line in out.splitlines():
            line = line.strip()
            if line and line.lower() != 'name':
                gpu_names.append(line)
    except Exception:
        pass

    nvidia_gpus = [g for g in gpu_names if any(k in g.lower() for k in ['nvidia', 'geforce', 'rtx', 'gtx'])]
    best_gpu = nvidia_gpus[0] if nvidia_gpus else (gpu_names[0] if gpu_names else 'Zintegrowana grafika / CPU')

    if has_cuda and any('rtx' in g.lower() or any(f' {s}' in g for s in ['30', '40', '50', '20']) for g in nvidia_gpus):
        rec_model = 'turbo'
        rec_device = 'cuda'
        rec_compute = 'float16'
        tier = 'pro'
        desc = 'Wykryto wydajną kartę graficzną NVIDIA RTX. Pełna akceleracja CUDA z modelem large-v3-turbo.'
    elif has_cuda and nvidia_gpus:
        rec_model = 'small'
        rec_device = 'cuda'
        rec_compute = 'float16'
        tier = 'mid'
        desc = 'Wykryto kartę graficzną NVIDIA GTX/RTX. Rekomendowany szybki model small.'
    else:
        rec_model = 'base'
        rec_device = 'cpu'
        rec_compute = 'int8'
        tier = 'cpu'
        desc = 'Praca na procesorze CPU. Rekomendowany zoptymalizowany model base.'

    return {
        'has_cuda': has_cuda,
        'gpu_name': best_gpu,
        'all_gpus': gpu_names,
        'tier': tier,
        'rec_model': rec_model,
        'rec_device': rec_device,
        'rec_compute': rec_compute,
        'desc': desc
    }

def is_model_downloaded(model_alias: str) -> bool:
    """Sprawdza, czy wagi wybranego modelu znajdują się już w folderze lokalnym models/ lub w pamięci podręcznej Hugging Face."""
    app_dir = get_app_dir()
    local_models_dir = os.path.join(app_dir, "models")
    
    spec = MODEL_SPECS.get(model_alias)
    if not spec:
        if os.path.isdir(model_alias) or os.path.isdir(os.path.join(local_models_dir, model_alias)):
            return True
        return False
        
    repo_id = spec["repo_id"]
    # 1. Sprawdź folder lokalny models/
    if os.path.exists(os.path.join(local_models_dir, model_alias)):
        return True
        
    # 2. Sprawdź HuggingFace hub cache
    hf_hub = os.path.expanduser("~/.cache/huggingface/hub")
    repo_dir = "models--" + repo_id.replace("/", "--")
    snapshots = os.path.join(hf_hub, repo_dir, "snapshots")
    if os.path.exists(snapshots) and os.listdir(snapshots):
        return True
        
    return False

def show_first_run_wizard_if_needed(config: dict) -> bool:
    """
    Sprawdza stan konfiguracji i dostępność wag.
    Jeśli aplikacja została uruchomiona po raz pierwszy i brak modelu, wyświetla nowoczesne okno instalatora.
    """
    cur_model = config.get("model_size", "turbo")
    hw = detect_hardware()
    
    # Jeśli model jest już pobrany i first_run_done jest True, nie wyświetlaj instalatora
    if config.get("first_run_done", False) and is_model_downloaded(cur_model):
        return True

    # Jeśli model jest już na dysku (np. użytkownik miał go pobranego wcześniej), zapisz flagę i kontynuuj
    if is_model_downloaded(cur_model):
        config["first_run_done"] = True
        save_config(config)
        return True

    # W przeciwnym razie wyświetl okno instalatora/kreatora pierwszego uruchomienia
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        logger.warning("Brak modułu tkinter. Pomijanie graficznego kreatora.")
        return True

    root = tk.Tk()
    root.title("Whiscribe AI — Konfiguracja pierwszego uruchomienia")
    root.geometry("640x520")
    root.resizable(False, False)

    # Ikonka okna
    ico_path = os.path.join(get_app_dir(), "icon.ico")
    if os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass

    # Kolorystyka Windows 11 Fluent Dark / Slate
    bg_color = "#101827"
    card_bg = "#1f293d"
    text_color = "#f3f4f6"
    sub_text = "#9ca3af"
    accent = "#3b82f6"
    accent_hover = "#2563eb"

    root.configure(bg=bg_color)

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure("TProgressbar", thickness=12, troughcolor=card_bg, background=accent)

    # Nagłówek
    header_frame = tk.Frame(root, bg=bg_color, padx=24, pady=16)
    header_frame.pack(fill="x")

    tk.Label(
        header_frame,
        text="Whiscribe AI — Wybór silnika mowy",
        font=("Segoe UI", 16, "bold"),
        bg=bg_color,
        fg=text_color
    ).pack(anchor="w")

    tk.Label(
        header_frame,
        text=f"Wykryta konfiguracja sprzętowa: {hw['gpu_name']}",
        font=("Segoe UI", 10),
        bg=bg_color,
        fg=accent
    ).pack(anchor="w", pady=(4, 0))

    tk.Label(
        header_frame,
        text=hw['desc'],
        font=("Segoe UI", 9),
        bg=bg_color,
        fg=sub_text
    ).pack(anchor="w", pady=(2, 0))

    # Wybór modelu (Karta opcji)
    content_frame = tk.Frame(root, bg=card_bg, padx=20, pady=16, relief="flat", highlightthickness=1, highlightbackground="#374151")
    content_frame.pack(fill="both", expand=True, padx=24, pady=8)

    selected_choice = tk.StringVar(value=hw['rec_model'])

    options = [
        ("turbo", "Klasa PRO: NVIDIA RTX (large-v3-turbo, ~1.5 GB)", MODEL_SPECS["turbo"]["desc"]),
        ("small", "Klasa Średnia: NVIDIA GTX / zbalansowany (small, ~460 MB)", MODEL_SPECS["small"]["desc"]),
        ("base", "Uniwersalny CPU: Zoptymalizowany dla procesora (base, ~140 MB)", MODEL_SPECS["base"]["desc"]),
    ]

    for val, title, desc in options:
        opt_frame = tk.Frame(content_frame, bg=card_bg, pady=6)
        opt_frame.pack(fill="x", anchor="w")

        is_rec = (val == hw['rec_model'])
        tag = "  [REKOMENDOWANY]" if is_rec else ""
        
        rb = tk.Radiobutton(
            opt_frame,
            text=f"{title}{tag}",
            variable=selected_choice,
            value=val,
            font=("Segoe UI", 10, "bold" if is_rec else "normal"),
            bg=card_bg,
            fg="#60a5fa" if is_rec else text_color,
            selectcolor="#111827",
            activebackground=card_bg,
            activeforeground="#93c5fd"
        )
        rb.pack(anchor="w")

        tk.Label(
            opt_frame,
            text=desc,
            font=("Segoe UI", 8),
            bg=card_bg,
            fg=sub_text,
            wraplength=540,
            justify="left"
        ).pack(anchor="w", padx=28)

    # Sekcja postępu
    progress_frame = tk.Frame(root, bg=bg_color, padx=24, pady=8)
    progress_frame.pack(fill="x")

    lbl_status = tk.Label(
        progress_frame,
        text="Kliknij poniżej, aby pobrać wagi modelu i przygotować Whiscribe do pracy.",
        font=("Segoe UI", 9),
        bg=bg_color,
        fg=sub_text
    )
    lbl_status.pack(anchor="w", pady=(0, 6))

    pbar = ttk.Progressbar(progress_frame, mode='indeterminate', style="TProgressbar")
    pbar.pack(fill="x")

    # Przyciski
    btn_frame = tk.Frame(root, bg=bg_color, padx=24, pady=16)
    btn_frame.pack(fill="x")

    success_event = threading.Event()

    def on_download_click():
        choice = selected_choice.get()
        btn_start.config(state="disabled", text="Pobieranie wag modelu...")
        lbl_status.config(text=f"Pobieranie modelu {choice} z Hugging Face... To potrwa od kilkunastu sekund do minuty.", fg="#60a5fa")
        pbar.start(10)

        def worker():
            try:
                from faster_whisper import download_model
                spec = MODEL_SPECS.get(choice, MODEL_SPECS["turbo"])
                models_dir = os.path.join(get_app_dir(), "models")
                os.makedirs(models_dir, exist_ok=True)
                
                # Pobierz model do katalogu lokalnego
                download_model(choice, output_dir=os.path.join(models_dir, choice))
                
                # Zapisz wybraną konfigurację
                config["model_size"] = choice
                config["device"] = spec["device"] if (spec["device"] == "cuda" and hw["has_cuda"]) else "cpu"
                config["compute_type"] = spec["compute_type"] if config["device"] == "cuda" else "int8"
                config["first_run_done"] = True
                save_config(config)

                root.after(0, on_download_finished, True, None)
            except Exception as e:
                root.after(0, on_download_finished, False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_download_finished(success, err):
        pbar.stop()
        if success:
            success_event.set()
            lbl_status.config(text="Model pobrany pomyślnie! Uruchamianie aplikacji...", fg="#34d399")
            root.after(800, root.destroy)
        else:
            btn_start.config(state="normal", text="Spróbuj ponownie")
            lbl_status.config(text=f"Błąd pobierania: {err}", fg="#f87171")
            messagebox.showerror("Błąd pobierania", f"Nie udało się pobrać wag modelu:\n{err}")

    btn_start = tk.Button(
        btn_frame,
        text="Pobierz i uruchom Whiscribe",
        font=("Segoe UI", 11, "bold"),
        bg=accent,
        fg="#ffffff",
        activebackground=accent_hover,
        activeforeground="#ffffff",
        relief="flat",
        padx=18,
        pady=8,
        cursor="hand2",
        command=on_download_click
    )
    btn_start.pack(side="right")

    root.mainloop()
    return success_event.is_set()
