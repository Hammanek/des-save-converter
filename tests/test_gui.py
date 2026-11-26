from pathlib import Path
import tempfile
import time
import unittest

from test_converter import populate_input, populate_reference
from des_save_gui import ConverterApp, default_output_path


class GuiTests(unittest.TestCase):
    def test_default_output_is_a_new_sibling_directory(self):
        self.assertEqual(
            default_output_path(Path("example/PPSA01341")),
            Path("example/PPSA01341_converted"),
        )

    def test_convert_button_workflow_creates_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, reference = root / "input", root / "reference"
            output = root / "output"
            populate_input(source)
            populate_reference(reference)
            app = ConverterApp()
            try:
                app.withdraw()
                app.input_var.set(str(source))
                app.reference_var.set(str(reference))
                app.output_var.set(str(output))
                app.start_conversion()
                deadline = time.monotonic() + 5
                while app.converting and time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.01)
                app.update()
                self.assertFalse(app.converting, "GUI conversion did not finish in time")
                self.assertIn("mobus", app.status_var.get())
                self.assertTrue((output / "SAVEDATA0PlayerProfile0" / "USR-DATA").is_file())
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
