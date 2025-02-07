import sys
import os
import re
import time
import base64
import tempfile
import dotenv
import pyautogui
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLineEdit, QLabel, QSpinBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
from google import genai
from google.genai import types

class AutomationTask(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)

    def __init__(self, init_text, init_delay, gemini_prompt, gemini_response_delay, x, y, width, height):
        super().__init__()
        self.init_text = init_text
        self.init_delay = init_delay
        self.gemini_prompt = gemini_prompt
        self.gemini_response_delay = gemini_response_delay
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.signals = self.Signals()

    @pyqtSlot()
    def run(self):
        try:
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)

            pyautogui.write(self.init_text, interval=self.init_delay/1000)

            full_screenshot_path = os.path.join(
                tempfile.gettempdir(),
                f"full_screenshot_{time.time()}.png"
            )

            try:
                subprocess.run(
                    ["spectacle", "-b", "-n", "-f", "-o", full_screenshot_path],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.signals.error.emit(f"Full screenshot failed: {e.stderr}")
                return
            except FileNotFoundError:
                self.signals.error.emit("'spectacle' not found. Install for KDE screenshot functionality.")
                return

            cropped_screenshot_path = os.path.join(
                tempfile.gettempdir(),
                f"cropped_screenshot_{time.time()}.png"
            )
            
            crop_geometry = f"{self.width}x{self.height}+{self.x}+{self.y}"
            try:
                subprocess.run(
                    ["gm", "convert", full_screenshot_path, "-crop", crop_geometry, "+repage", cropped_screenshot_path],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.signals.error.emit(f"Cropping failed: {e.stderr}")
                return
            except FileNotFoundError:
                self.signals.error.emit("'gm' command not found. Install GraphicsMagick.")
                return

            gemini_response_text = self.call_gemini_api(cropped_screenshot_path)
            
            # Change the error check to be more general:
            if gemini_response_text.lower().startswith("error"):
                self.signals.error.emit(gemini_response_text)
                return

            time.sleep(2)
            pyautogui.write(gemini_response_text, interval=self.gemini_response_delay/1000)

            self.signals.finished.emit(cropped_screenshot_path)
        except Exception as e:
            self.signals.error.emit(f"Automation Error: {str(e)}")

    def call_gemini_api(self, screenshot_path) -> str:
        try:
            API_KEY = os.environ.get("GEMINI_API_KEY")
            if not API_KEY:
                return "Error: GEMINI_API_KEY not set in environment."

            client = genai.Client(api_key=API_KEY)

            with open(screenshot_path, "rb") as f:
                image_bytes = f.read()

            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            
            system_prompt = 'You can only speak in consonants, the fairy stole all your vowels.'
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[image_part, self.gemini_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=1.0,
                    max_output_tokens=20
            ),
            )

            return response.text if response.text else "No response generated"
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_region = None
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.setWindowTitle("Automation Controller")
        self.setGeometry(100, 100, 450, 400)

        main_layout = QVBoxLayout()

        self.select_region_btn = QPushButton("Select Screenshot Region")
        self.region_label = QLabel("No region selected")
        main_layout.addWidget(self.select_region_btn)
        main_layout.addWidget(self.region_label)

        form_layout = QFormLayout()

        self.initial_text_edit = QLineEdit("11115")
        self.initial_delay_spin = QSpinBox()
        self.initial_delay_spin.setRange(10, 10000)
        self.initial_delay_spin.setValue(800)

        self.gemini_prompt_edit = QLineEdit("Caption this image.")
        self.gemini_response_delay_spin = QSpinBox()
        self.gemini_response_delay_spin.setRange(10, 10000)
        self.gemini_response_delay_spin.setValue(80)

        form_layout.addRow(QLabel("Initial Text:"), self.initial_text_edit)
        form_layout.addRow(QLabel("Initial Delay (ms):"), self.initial_delay_spin)
        form_layout.addRow(QLabel("Gemini Prompt:"), self.gemini_prompt_edit)
        form_layout.addRow(QLabel("Response Delay (ms):"), self.gemini_response_delay_spin)

        self.keystroke_button = QPushButton("Start Automation Sequence")
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.keystroke_button)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_connections(self):
        self.keystroke_button.clicked.connect(self.on_keystroke_button_clicked)
        self.select_region_btn.clicked.connect(self.on_select_region_clicked)

    def on_select_region_clicked(self):
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            self.selected_region = result.stdout.strip()

            match = re.match(r"^(-?\d+),(-?\d+) (-?\d+)x(-?\d+)$", self.selected_region)
            if match:
                self.x, self.y, self.width, self.height = map(int, match.groups())
                self.region_label.setText(f"Selected: {self.selected_region}")
            else:
                QMessageBox.critical(self, "Error", "Invalid region format")
                self.selected_region = None
                self.region_label.setText("Invalid region - select again")
                return

        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                QMessageBox.information(self, "Info", "Region selection canceled")
            else:
                QMessageBox.critical(self, "Error", f"Slurp error: {e.stderr}")
            self.selected_region = None
            self.region_label.setText("Selection failed - try again")
        except FileNotFoundError:
            QMessageBox.critical(self, "Error",
                "'slurp' not found. Install for region selection:\nsudo apt install slurp")
            self.selected_region = None
            self.x = self.y = self.width = self.height = None

    def on_keystroke_button_clicked(self):
        if not self.selected_region or self.x is None:
            QMessageBox.warning(self, "Warning", "Select screenshot region first!")
            return

        init_text = self.initial_text_edit.text()
        init_delay = self.initial_delay_spin.value()
        gemini_prompt = self.gemini_prompt_edit.text()
        gemini_response_delay = self.gemini_response_delay_spin.value()

        task = AutomationTask(
            init_text,
            init_delay,
            gemini_prompt,
            gemini_response_delay,
            self.x,
            self.y,
            self.width,
            self.height
        )
        task.signals.finished.connect(self.on_sequence_finished)
        task.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(task)

    @pyqtSlot(str)
    def on_sequence_finished(self, screenshot_path):
        QMessageBox.information(self, "Success", "Automation sequence completed!")
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except Exception as e:
            print(f"Error cleaning up screenshot: {str(e)}")

    @pyqtSlot(str)
    def on_error(self, message):
        QMessageBox.critical(self, "Error", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dotenv.load_dotenv()  # Load environment variables (for GEMINI_API_KEY)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())