#!/usr/bin/env python3
import shutil
import json, tomllib    
import sys

from contextlib import contextmanager
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtCore import QObject, Signal

from mib.utils import cmd_exec, dscl, launchctl, pkgutil


class StepFailedError(Exception):
    pass


class UninstallerWorker(QObject):
    finished = Signal()
    failed = Signal(str)
    progress = Signal(int, str)

    @contextmanager
    def step(self, description):
        try:
            yield
        except StepFailedError as e:
            self.step_failed(str(e))
        else:
            self.step_finished(description)

    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.steps_finished = 0

    def step_finished(self, message):
        self.steps_finished += 1
        self.progress.emit(self.steps_finished, message)
    
    def step_failed(self, error_msg):
        self.failed.emit(error_msg)

    def run(self):
        daemon_id = self.product.get('identifier')
        app_name = self.product.get('name').lower()
        user_app_data_dirs = (
            Path(f'/opt/{app_name}'),
            Path.home() / Path(f"Library/Application Support/{app_name}")
        )
        gui_prompt = "{app_name} Uninstaller".format(
            app_name=self.product.get('name')
        )

        with self.step("Stopping and unloading daemon from launchd"):
            # Stopping and unloading daemon from launchd
            daemon_path = Path(f"/Library/LaunchDaemons/{daemon_id}.plist")
            user_daemon_path = Path(f"/Library/LaunchAgents/{daemon_id}.plist")
            if not daemon_path.exists():
                daemon_path = Path.home() / user_daemon_path
            if not daemon_path.exists():
                daemon_path = Path("/Users/pikesquares") / user_daemon_path
                unload_result = launchctl(
                    "unload", str(daemon_path.resolve()), 
                    as_superuser_gui=True,
                    gui_prompt=gui_prompt
                )
                if unload_result.error:
                    raise StepFailedError(unload_result.stderr)
            else:
                raise StepFailedError(f"Daemon {daemon_id} not found in system!")

            # Removing daemon plist file
            res = cmd_exec(
                "rm",
                "-f",
                daemon_path,
                as_superuser_gui=True,
                gui_prompt=gui_prompt
            )

        # Forget package from package db
        with self.step("Forget package from package db"):
            packages = pkgutil(pkgs=True, as_superuser_gui=True,
                               gui_prompt=gui_prompt)
            if packages.success:
                for pkg in packages.stdout.splitlines():
                    if daemon_id not in pkg:
                        continue
                    res = pkgutil(forget=pkg, as_superuser_gui=True, gui_prompt=gui_prompt)
                    if res.error:
                        raise StepFailedError(res.stderr)
        
        # Remove pikesquares user
        with self.step("Remove pikesquares internal user"):
            # sudo /usr/bin/dscl . -delete /Users/dylan
            # list all users
            users = dscl(list="/Users")
            for user in users.stdout.splitlines():
                if "pikesquares" in user:
                    dscl(
                        delete=f"/Users/{user}",
                        as_superuser_gui=True,
                        gui_prompt=gui_prompt
                    )

        # Remove app data dir
        with self.step("Remove application data (certificates, configs and so on)"):
            for dir_ in user_app_data_dirs:
                if dir_.exists() and dir_.is_dir():
                    res = cmd_exec(
                        "rm",
                        "-rf",
                        dir_,
                        as_superuser_gui=True,
                        gui_prompt=gui_prompt
                    )

        self.finished.emit()

class IntroPage(QtWidgets.QWizardPage):
    def __init__(self, product, parent=None):
        super(IntroPage, self).__init__(parent)

        self.setTitle("Introduction")
        self.setSubTitle(f"This wizard will remove {product['name']} from your computer. ")
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)


class UninstallPage(QtWidgets.QWizardPage):
    def setup_ui(self, product):
        self.setTitle(f"Uninstalling {product['name']}...")
        
        # self.description_label = QtWidgets.QLabel("Uninstall page. ")
        # self.description_label.setWordWrap(True)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(3)

        self.list_widget = QtWidgets.QListWidget()

        self.page_layout = QtWidgets.QVBoxLayout()
        self.page_layout.addWidget(self.progress_bar)
        # self.page_layout.addWidget(self.description_label)
        self.page_layout.addWidget(self.list_widget)
        
        self.setLayout(self.page_layout)
        # self.back_button = self.wizard().button(QtWidgets.QWizard.WizardButton.BackButton)
        # self.next_button = self.wizard().button(QtWidgets.QWizard.WizardButton.NextButton)
        # self.back_button.setEnabled(False)
        # self.next_button.setEnabled(False)
        self.next_btn = QtWidgets.QPushButton("Next")


    def __init__(self, product, parent=None):
        super(UninstallPage, self).__init__(parent)
        self.is_uninstall_failed = False
        self.is_uninstall_finished = False
        self.worker = UninstallerWorker(product)
        self.setup_ui(product)

        self.worker.progress.connect(self.step_completed)
        self.worker.failed.connect(self.step_failed)
        self.worker.finished.connect(self.work_finished)

    def work_finished(self):
        self.uninstall_finished()
        self.wizard().next()
        # last_page_id = self.wizard().pageIds()[-1]
        # # last_page = 
        # self.wizard().setPage(last_page_id, self.wizard().page(last_page_id))
        # self.pageself.nextId()

        # self.validatePage()

    def step_completed(self, value, msg):
        self.progress_bar.setValue(value)
        self.list_widget.addItem(f"[success] {msg}")

    def step_failed(self, m):
        self.list_widget.addItem(f"[error] {m}")
        self.is_uninstall_failed = True
    
    def uninstall_finished(self):
        self.is_uninstall_finished = True
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self.is_uninstall_finished

    def validatePage(self) -> bool:
        return not self.is_uninstall_failed

    def initializePage(self):
        self.list_widget.clear()
        self.wizard().setButtonLayout([
            QtWidgets.QWizard.WizardButton.FinishButton,
        ])
        self.worker.run()


class ConclusionPage(QtWidgets.QWizardPage):
    def __init__(self, product, parent=None):
        super(ConclusionPage, self).__init__(parent)
        self.product = product

        self.setTitle("Finish")
        self.setSubTitle(f"The {product['name']} was successfully uninstalled from your computer")
        # self.setPixmap(QtWidgets.QWizard.WatermarkPixmap,
        #         QtWidgets.QPixmap(':/images/watermark2.png'))

        # self.label = QtWidgets.QLabel()
        # self.label.setWordWrap(True)
        self.btn = QtWidgets.QPushButton("Finish")

        layout = QtWidgets.QVBoxLayout()
        # layout.addWidget(self.label)
        self.setLayout(layout)
        # self.wizard().setButton(QtWidgets.QWizard.WizardButton.)
    def initializePage(self) -> None:
        self.setFinalPage(True)
        self.wizard().setButton(
            QtWidgets.QWizard.WizardButton.FinishButton,
            self.btn
        )


        # finishText = self.wizard().buttonText(QtWidgets.QWizard.FinishButton)
        # finishText.replace('&', '')
        # self.label.setText(f"The {product['title']} was successfully uninstalled from your computer.")


class FailurePage(QtWidgets.QWizardPage):
    def __init__(self, product, parent=None):
        super(FailurePage, self).__init__(parent)

        self.setTitle("Failure")
        self.setSubTitle(f"An error was occurred during {product['title']} uninstall")
        # self.label = QtWidgets.QLabel()
        # self.label.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout()
        # layout.addWidget(self.label)
        self.setLayout(layout)

    def initializePage(self):
        pass
        # finishText = self.wizard().buttonText(QtWidgets.QWizard.FinishButton)
        # finishText.replace('&', '')
        # self.label.setText("The PikeSquares was successfully uninstalled from your computer.")


class UninstallWizard(QtWidgets.QWizard):
    pages = [
        IntroPage,
        UninstallPage,
        ConclusionPage
    ]
    def __init__(self, config, parent=None):
        super(UninstallWizard, self).__init__(parent)

        self.product = config['product']

        for page in self.pages:
            # pg = page(product=self.product)
            # pg = UninstallPage()
            # pg.setW
            self.addPage(page(product=self.product, parent=self))

        # self.setPixmap(QtWidgets.QWizard.BannerPixmap,
        #         QtWidgets.QPixmap(':/images/banner.png'))
        # self.setPixmap(QtWidgets.QWizard.BackgroundPixmap,
        #         QtWidgets.QPixmap(':/images/background.png'))

        self.setWindowTitle(f"{config['product']['name']} Uninstaller")

    def accept(self):
        if not self.validateCurrentPage():
            self.setPage(FailurePage(product=self.product))
            # self.next()
        super().accept()

def load_config(config_path="mib.toml"):
    config_path = Path(config_path)
    with open(config_path, "rb") as file:
        if config_path.suffix == ".json":
            return json.load(file)
        elif config_path.suffix == ".toml":
            return tomllib.load(file)
        else:
            sys.stderr.write("This config is not supported! (only json, toml files are supported)\n")
            exit(1)

def main():
    app = QtWidgets.QApplication(sys.argv)
    wizard = UninstallWizard(
        config={'product': {'name': "PikeSquares", 'identifier': "com.eloquentbits.pikesquares"}}
    )
    wizard.show()
    # wizard.button(QtWidgets.QWizard.WizardButton.NextButton).setEnabled(False)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
