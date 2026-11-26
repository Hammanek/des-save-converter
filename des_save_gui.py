"""Small Tkinter front-end for DeS Save Converter."""

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from des_save_converter import ConversionError, convert_save


def default_output_path(input_path: Path) -> Path:
    input_path = Path(input_path)
    return input_path.with_name(f"{input_path.name}_converted")


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeS Save Converter")
        self.geometry("720x285")
        self.minsize(620, 285)
        self.converting = False
        self.results = queue.Queue()

        self.input_var = tk.StringVar()
        self.reference_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Select an incomplete save and a working save to use as the template."
        )

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Demon’s Souls — KytyPS5 to native PC save converter", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16)
        )
        self._path_row(frame, 1, "Incomplete save:", self.input_var, self._choose_input)
        self._path_row(frame, 2, "Working reference:", self.reference_var, self._choose_reference)
        self._path_row(frame, 3, "Output folder:", self.output_var, self._choose_output)

        self.convert_button = ttk.Button(frame, text="Convert save", command=self.start_conversion)
        self.convert_button.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 10))

        self.status_label = ttk.Label(
            frame, textvariable=self.status_var, wraplength=660, foreground="#555555"
        )
        self.status_label.grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Label(
            frame,
            text="Original files remain unchanged. The output must be a new or empty folder.",
            foreground="#777777",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def _path_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=8, pady=4
        )
        ttk.Button(parent, text="Browse…", command=command).grid(
            row=row, column=2, pady=4
        )

    def _choose_input(self):
        selected = filedialog.askdirectory(title="Select the incomplete save")
        if selected:
            self.input_var.set(selected)
            if not self.output_var.get().strip():
                self.output_var.set(str(default_output_path(Path(selected))))

    def _choose_reference(self):
        selected = filedialog.askdirectory(title="Select the working reference save")
        if selected:
            self.reference_var.set(selected)

    def _choose_output(self):
        selected = filedialog.askdirectory(title="Select a new or empty output folder")
        if selected:
            self.output_var.set(selected)

    def start_conversion(self):
        if self.converting:
            return
        paths = tuple(
            variable.get().strip()
            for variable in (self.input_var, self.reference_var, self.output_var)
        )
        if not all(paths):
            self._set_status("Select all three paths first.", error=True)
            return
        self.converting = True
        self.convert_button.configure(state="disabled")
        self._set_status("Converting save…")
        threading.Thread(target=self._convert_worker, args=paths, daemon=True).start()
        self.after(100, self._poll_result)

    def _convert_worker(self, input_path, reference_path, output_path):
        try:
            character = convert_save(Path(input_path), Path(reference_path), Path(output_path))
        except (ConversionError, OSError) as error:
            self.results.put((False, str(error)))
        except Exception as error:
            self.results.put((False, f"Unexpected error: {error}"))
        else:
            self.results.put((
                True,
                f"Done: {character.name}, {character.class_name}, "
                f"Soul Level {character.soul_level}\nSaved to: {output_path}",
            ))

    def _poll_result(self):
        try:
            success, message = self.results.get_nowait()
        except queue.Empty:
            if self.converting:
                self.after(100, self._poll_result)
            return
        self.converting = False
        self.convert_button.configure(state="normal")
        self._set_status(message, error=not success)

    def _set_status(self, message, error=False):
        self.status_var.set(message)
        self.status_label.configure(foreground="#B00020" if error else "#176B2C")


def main():
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
