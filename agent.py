#!/usr/bin/env python3
import sys
import os
import re
import time
import json
import base64
import tempfile
import dotenv
import pyautogui
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QMessageBox, QCheckBox,
    QPlainTextEdit, QFormLayout, QTabWidget, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, pyqtSlot, QRunnable, QThreadPool

# For the Gemini Automation functionality:
from google import genai
from google.genai import types

# ------------------ Auto Clicker Functionality ------------------

class ClickerThread(QThread):
    update_signal = pyqtSignal(str)
    countdown_signal = pyqtSignal(int)

    def __init__(self, interval, num_clicks, button, click_type, lock_coords):
        super().__init__()
        self.interval = interval
        self.num_clicks = num_clicks
        self.button = button
        self.click_type = click_type
        self.lock_coords = lock_coords
        self.running = False
        self.x, self.y = None, None
        self.current_clicks = 0
        self.start_delay = 3

    def run(self):
        self.running = True
        self.current_clicks = 0
        pyautogui.FAILSAFE = False

        # Countdown phase
        for i in range(self.start_delay, 0, -1):
            if not self.running:
                return
            self.countdown_signal.emit(i)
            time.sleep(1)

        # Capture position after countdown if needed
        if self.lock_coords:
            self.x, self.y = pyautogui.position()
        else:
            self.x, self.y = None, None

        # Clicking loop
        while self.running:
            click_args = {'button': self.button}
            if self.x is not None and self.y is not None:
                click_args['x'] = self.x
                click_args['y'] = self.y

            if self.click_type == 'double':
                pyautogui.doubleClick(**click_args)
            else:
                pyautogui.click(**click_args)
            
            self.current_clicks += 1
            self.update_signal.emit(f"Clicks performed: {self.current_clicks}")
            
            if self.num_clicks > 0 and self.current_clicks >= self.num_clicks:
                self.stop()
            
            start_time = time.time()
            while time.time() - start_time < self.interval and self.running:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()


class AutoClickerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Warning label at the top
        self.warning_label = QLabel(
            "After clicking Start:\n"
            "1. Don't move mouse for 3 seconds\n"
            "2. Keep mouse in desired position\n"
            "(Lock Coordinates to keep position)"
        )
        self.warning_label.setStyleSheet("color: red; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.warning_label)

        # Click settings container
        settings_layout = QVBoxLayout()

        # Number of clicks
        clicks_layout = QHBoxLayout()
        clicks_layout.addWidget(QLabel("Number of clicks (0 for infinite):"))
        self.clicks_input = QSpinBox()
        self.clicks_input.setRange(0, 99999)
        clicks_layout.addWidget(self.clicks_input)
        settings_layout.addLayout(clicks_layout)

        # Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.interval_input = QDoubleSpinBox()
        self.interval_input.setRange(2, 1000)
        self.interval_input.setValue(10.0)
        interval_layout.addWidget(self.interval_input)
        settings_layout.addLayout(interval_layout)

        # Mouse Button selection
        button_layout = QHBoxLayout()
        button_layout.addWidget(QLabel("Mouse button:"))
        self.button_combo = QComboBox()
        self.button_combo.addItems(["left", "right", "middle"])
        button_layout.addWidget(self.button_combo)
        settings_layout.addLayout(button_layout)

        # Click type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Click type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["single", "double"])
        type_layout.addWidget(self.type_combo)
        settings_layout.addLayout(type_layout)

        # Lock Coordinates checkbox
        lock_layout = QHBoxLayout()
        self.lock_checkbox = QCheckBox("Lock Coordinates")
        lock_layout.addWidget(self.lock_checkbox)
        settings_layout.addLayout(lock_layout)

        layout.addLayout(settings_layout)

        # Control buttons
        button_row = QHBoxLayout()
        self.start_stop_btn = QPushButton("Start")
        self.start_stop_btn.clicked.connect(self.toggle_clicking)
        button_row.addWidget(self.start_stop_btn)

        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.handle_exit)
        button_row.addWidget(exit_btn)
        layout.addLayout(button_row)

        # Status label
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def toggle_clicking(self):
        if self.thread and self.thread.isRunning():
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        self.start_stop_btn.setText("Stop")
        self.thread = ClickerThread(
            interval=self.interval_input.value(),
            num_clicks=self.clicks_input.value(),
            button=self.button_combo.currentText(),
            click_type=self.type_combo.currentText(),
            lock_coords=self.lock_checkbox.isChecked()
        )
        self.thread.update_signal.connect(self.update_status)
        self.thread.countdown_signal.connect(self.show_countdown)
        self.thread.finished.connect(self.clicking_finished)
        self.thread.start()
        self.status_label.setText("Status: Starting...")

    def stop_clicking(self):
        if self.thread:
            self.thread.stop()
            self.start_stop_btn.setText("Start")
            self.status_label.setText("Status: Stopped")

    def update_status(self, message):
        self.status_label.setText(f"Status: Running - {message}")

    def show_countdown(self, seconds):
        self.status_label.setText(f"Starting in {seconds}... (Keep mouse still!)")

    def clicking_finished(self):
        self.start_stop_btn.setText("Start")
        self.status_label.setText("Status: Completed")

    def handle_exit(self):
        # Ensure the thread stops before exiting the tab (or application)
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        # In a tabbed interface you might want to simply clear the fields or
        # close the overall application.
        QApplication.quit()

    def cleanup(self):
        # Call this method from the main window's closeEvent to clean up if needed.
        if self.thread and self.thread.isRunning():
            self.thread.stop()


# ------------------ Gemini Automation Task ------------------

class AutomationTask(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)
        
    def __init__(self, init_text, init_delay, gemini_prompt, gemini_response_delay,
                 x, y, width, height, insertion_x, insertion_y,
                 gemini_model, gemini_temperature, gemini_max_output_tokens, gemini_system_prompt):
        super().__init__()
        self.init_text = init_text
        self.init_delay = init_delay
        self.gemini_prompt = gemini_prompt
        self.gemini_response_delay = gemini_response_delay
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.insertion_x = insertion_x
        self.insertion_y = insertion_y
        self.gemini_model = gemini_model
        self.gemini_temperature = gemini_temperature
        self.gemini_max_output_tokens = gemini_max_output_tokens
        self.gemini_system_prompt = gemini_system_prompt
        
        self.signals = self.Signals()
        self._stop = False

    def stop(self):
        self._stop = True

    @pyqtSlot()
    def run(self):
        try:
            # Switch window and type the initial text.
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return
            pyautogui.write(self.init_text, interval=self.init_delay/1000)
            
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Take a full screenshot.
            temp_dir = tempfile.gettempdir()
            full_screenshot_path = os.path.join(temp_dir, f"full_screenshot_{time.time()}.png")
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
            
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Crop the screenshot.
            cropped_screenshot_path = os.path.join(temp_dir, f"cropped_screenshot_{time.time()}.png")
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

            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Call the Gemini API using the cropped screenshot.
            gemini_response_text = self.call_gemini_api(cropped_screenshot_path)
            if gemini_response_text.lower().startswith("error"):
                self.signals.error.emit(gemini_response_text)
                return
            
            time.sleep(2)
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return
            # Click at the designated insertion point before typing the Gemini response.
            pyautogui.click(self.insertion_x, self.insertion_y)
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
            
            response = client.models.generate_content(
                model=self.gemini_model,
                contents=[image_part, self.gemini_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.gemini_system_prompt,
                    temperature=self.gemini_temperature,
                    max_output_tokens=self.gemini_max_output_tokens
                ),
            )
            return response.text if response.text else "No response generated"
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"

# ------------------ Gemini Automation Controller Tab ------------------

class AutomationControllerTab(QWidget):
    CONFIG_FILENAME = ".automation_config.json"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_region = None
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.insertion_x = None
        self.insertion_y = None
        self.current_task = None
        self.setup_ui()
        self.setup_connections()
        self.populate_model_dropdown()
        self.load_config()

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # Region and insertion selection
        self.select_region_btn = QPushButton("Select Screenshot Region")
        self.region_label = QLabel("No region selected")
        self.region_label.setContentsMargins(2, 2, 2, 2)
        main_layout.addWidget(self.select_region_btn)
        main_layout.addWidget(self.region_label)

        self.select_insertion_point_btn = QPushButton("Select Text Insertion Point")
        self.insertion_point_label = QLabel("No insertion point selected")
        self.insertion_point_label.setContentsMargins(2, 2, 2, 2)
        main_layout.addWidget(self.select_insertion_point_btn)
        main_layout.addWidget(self.insertion_point_label)

        # Form for core options.
        form_layout = QFormLayout()
        self.initial_text_edit = QLineEdit("11115")
        self.initial_delay_spin = QSpinBox()
        self.initial_delay_spin.setRange(10, 10000)
        self.initial_delay_spin.setValue(800)

        self.gemini_prompt_edit = QLineEdit("In 8 words or less, why do you feel this is a positive ad for the platform?")
        self.gemini_response_delay_spin = QSpinBox()
        self.gemini_response_delay_spin.setRange(10, 10000)
        self.gemini_response_delay_spin.setValue(80)

        form_layout.addRow(QLabel("Initial Text:"), self.initial_text_edit)
        form_layout.addRow(QLabel("Initial Delay (ms):"), self.initial_delay_spin)
        form_layout.addRow(QLabel("Gemini Prompt:"), self.gemini_prompt_edit)
        form_layout.addRow(QLabel("Response Delay (ms):"), self.gemini_response_delay_spin)

        # Gemini API configuration options.
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItem("Loading...", userData=None)
        form_layout.addRow(QLabel("Gemini API Model:"), self.gemini_model_combo)

        self.gemini_temperature_spin = QDoubleSpinBox()
        self.gemini_temperature_spin.setRange(0.0, 2.0)
        self.gemini_temperature_spin.setSingleStep(0.1)
        self.gemini_temperature_spin.setValue(1.0)
        
        self.gemini_max_output_tokens_spin = QSpinBox()
        self.gemini_max_output_tokens_spin.setRange(1, 1000)
        self.gemini_max_output_tokens_spin.setValue(20)
        
        self.system_prompt_textedit = QPlainTextEdit()
        default_system_prompt = (
            "You are an advanced language model designed to evaluate and respond to questions about advertisements. "
            "When presented with a description or query about an ad, analyze it and provide responses based on the following guidelines:\n\n"
            "1. Emotions and Reactions: Explain what might go through someone's mind when viewing the ad and why it might evoke certain feelings.\n"
            "2. Key Descriptive Words: Provide two words that best encapsulate the reaction to the ad, ensuring they are relevant and insightful.\n"
            "3. Appropriateness and Impact: Evaluate whether the ad is suitable for platforms like Facebook or Instagram, and discuss if elements could be offensive, misleading, or inappropriate.\n"
            "4. Deeper Analysis: Consider the advertiser’s image, analyze the prominence and presentation of products in the ad, and reflect on social reactions.\n\n"
            "Your answer should be one sentence, short, and use informal, natural language."
        )
        self.system_prompt_textedit.setPlainText(default_system_prompt)
        self.system_prompt_textedit.setFixedHeight(130)

        form_layout.addRow(QLabel("Gemini Temperature:"), self.gemini_temperature_spin)
        form_layout.addRow(QLabel("Gemini Max Output Tokens:"), self.gemini_max_output_tokens_spin)
        form_layout.addRow(QLabel("System Prompt:"), self.system_prompt_textedit)

        main_layout.addLayout(form_layout)

        # Start automation button.
        self.keystroke_button = QPushButton("Start Automation Sequence")
        main_layout.addWidget(self.keystroke_button)

        # Automation progress message and Stop button.
        self.in_progress_label = QLabel("Automation in progress...")
        self.in_progress_label.setVisible(False)
        self.stop_button = QPushButton("Stop Automation")
        self.stop_button.setVisible(False)
        main_layout.addWidget(self.in_progress_label)
        main_layout.addWidget(self.stop_button)

        self.setLayout(main_layout)

    def setup_connections(self):
        self.keystroke_button.clicked.connect(self.on_keystroke_button_clicked)
        self.select_region_btn.clicked.connect(self.on_select_region_clicked)
        self.select_insertion_point_btn.clicked.connect(self.on_select_insertion_point_clicked)
        self.stop_button.clicked.connect(self.on_stop_button_clicked)

    def populate_model_dropdown(self):
        try:
            API_KEY = os.environ.get("GEMINI_API_KEY")
            if not API_KEY:
                QMessageBox.critical(self, "Error", "GEMINI_API_KEY not set in environment.")
                return
            client = genai.Client(api_key=API_KEY)
            models = client.models.list()
            # Filter for Gemini models.
            gemini_models = [model for model in models if model.name.startswith("models/gemini-")]
            gemini_models.sort(key=lambda m: m.name)
            self.gemini_model_combo.clear()
            for model in gemini_models:
                self.gemini_model_combo.addItem(model.display_name, model.name)
            # Set default selection if available.
            default_index = self.gemini_model_combo.findData("models/gemini-2.0-flash")
            if default_index != -1:
                self.gemini_model_combo.setCurrentIndex(default_index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error retrieving Gemini models: {e}")

    def on_select_region_clicked(self):
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            self.selected_region = result.stdout.strip()
            match = re.match(r"^(-?\d+),(-?\d+)\s+(-?\d+)x(-?\d+)$", self.selected_region)
            if match:
                self.x, self.y, self.width, self.height = map(int, match.groups())
                self.region_label.setText(f"Selected: {self.selected_region}")
            else:
                QMessageBox.critical(self, "Error", "Invalid region format")
                self.selected_region = None
                self.region_label.setText("Invalid region - select again")
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

    def on_select_insertion_point_clicked(self):
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            insertion_region = result.stdout.strip()
            match = re.match(r"^(-?\d+),(-?\d+)\s+(-?\d+)x(-?\d+)$", insertion_region)
            if match:
                x, y, w, h = map(int, match.groups())
                self.insertion_x = x + w // 2
                self.insertion_y = y + h // 2
                self.insertion_point_label.setText(f"Selected Insertion Point: ({self.insertion_x}, {self.insertion_y})")
            else:
                QMessageBox.critical(self, "Error", "Invalid insertion point format")
                self.insertion_x = self.insertion_y = None
            # End try
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                QMessageBox.information(self, "Info", "Insertion point selection canceled")
            else:
                QMessageBox.critical(self, "Error", f"Slurp error: {e.stderr}")
            self.insertion_x = self.insertion_y = None
        except FileNotFoundError:
            QMessageBox.critical(self, "Error",
                "'slurp' not found. Install for region/insertion selection:\nsudo apt install slurp")
            self.insertion_x = self.insertion_y = None

    def on_keystroke_button_clicked(self):
        if not self.selected_region or self.x is None or self.insertion_x is None:
            QMessageBox.warning(self, "Warning", "Select screenshot region and insertion point first!")
            return

        # Retrieve the Gemini model from the dropdown.
        gemini_model = self.gemini_model_combo.currentData()
        if not gemini_model:
            QMessageBox.warning(self, "Warning", "Please select a valid Gemini model from the dropdown!")
            return

        # Disable start and show in progress UI.
        self.keystroke_button.setEnabled(False)
        self.in_progress_label.setVisible(True)
        self.stop_button.setVisible(True)

        init_text = self.initial_text_edit.text()
        init_delay = self.initial_delay_spin.value()
        gemini_prompt = self.gemini_prompt_edit.text()
        gemini_response_delay = self.gemini_response_delay_spin.value()
        gemini_temperature = self.gemini_temperature_spin.value()
        gemini_max_output_tokens = self.gemini_max_output_tokens_spin.value()
        gemini_system_prompt = self.system_prompt_textedit.toPlainText()
        
        task = AutomationTask(
            init_text,
            init_delay,
            gemini_prompt,
            gemini_response_delay,
            self.x,
            self.y,
            self.width,
            self.height,
            self.insertion_x,
            self.insertion_y,
            gemini_model,
            gemini_temperature,
            gemini_max_output_tokens,
            gemini_system_prompt
        )
        self.current_task = task
        task.signals.finished.connect(self.on_sequence_finished)
        task.signals.error.connect(self.on_task_error)
        QThreadPool.globalInstance().start(task)

    @pyqtSlot()
    def on_stop_button_clicked(self):
        if self.current_task:
            self.current_task.stop()
            self.stop_button.setEnabled(False)
            self.in_progress_label.setText("Stopping automation...")

    @pyqtSlot(str)
    def on_sequence_finished(self, screenshot_path):
        self.in_progress_label.setVisible(False)
        self.stop_button.setVisible(False)
        self.keystroke_button.setEnabled(True)
        self.current_task = None
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except Exception as e:
            print(f"Error cleaning up screenshot: {str(e)}")

    @pyqtSlot(str)
    def on_task_error(self, message):
        self.in_progress_label.setVisible(False)
        self.stop_button.setVisible(False)
        self.keystroke_button.setEnabled(True)
        self.current_task = None
        QMessageBox.critical(self, "Error", message)

    def load_config(self):
        if os.path.exists(self.CONFIG_FILENAME):
            try:
                with open(self.CONFIG_FILENAME, "r", encoding="utf8") as f:
                    config = json.load(f)
                self.initial_text_edit.setText(config.get("initial_text", "11115"))
                self.initial_delay_spin.setValue(config.get("initial_delay", 800))
                self.gemini_prompt_edit.setText(config.get("gemini_prompt", 
                    "In 8 words or less, why do you feel this is a positive ad for the platform?"))
                self.gemini_response_delay_spin.setValue(config.get("gemini_response_delay", 80))
                # Update the dropdown selection based on the saved model.
                saved_model = config.get("gemini_model", "models/gemini-2.0-flash")
                index = self.gemini_model_combo.findData(saved_model)
                if index != -1:
                    self.gemini_model_combo.setCurrentIndex(index)
                self.gemini_temperature_spin.setValue(config.get("gemini_temperature", 1.0))
                self.gemini_max_output_tokens_spin.setValue(config.get("gemini_max_output_tokens", 20))
                self.system_prompt_textedit.setPlainText(config.get("system_prompt", self.system_prompt_textedit.toPlainText()))
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        config = {
            "initial_text": self.initial_text_edit.text(),
            "initial_delay": self.initial_delay_spin.value(),
            "gemini_prompt": self.gemini_prompt_edit.text(),
            "gemini_response_delay": self.gemini_response_delay_spin.value(),
            "gemini_model": self.gemini_model_combo.currentData(),
            "gemini_temperature": self.gemini_temperature_spin.value(),
            "gemini_max_output_tokens": self.gemini_max_output_tokens_spin.value(),
            "system_prompt": self.system_prompt_textedit.toPlainText(),
        }
        try:
            with open(self.CONFIG_FILENAME, "w", encoding="utf8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def cleanup(self):
        # Called by the main window when closing to save config.
        self.save_config()


# ------------------ Combined Main Window with Tabs ------------------

class CombinedMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automation & Auto Clicker")
        self.setGeometry(100, 100, 500, 700)
        self.init_ui()

    def init_ui(self):
        tab_widget = QTabWidget()

        # Create the two tabs.
        self.automation_tab = AutomationControllerTab(self)
        self.autoclicker_tab = AutoClickerTab(self)

        tab_widget.addTab(self.automation_tab, "Gemini Automation")
        tab_widget.addTab(self.autoclicker_tab, "Auto Clicker")

        self.setCentralWidget(tab_widget)

    def closeEvent(self, event):
        # Cleanup in both tabs (if necessary) before closing.
        self.automation_tab.cleanup()
        self.autoclicker_tab.cleanup()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dotenv.load_dotenv()  # Load environment variables (for GEMINI_API_KEY)
    window = CombinedMainWindow()
    window.show()
    sys.exit(app.exec())