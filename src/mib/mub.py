#!/usr/bin/env python3
import json, tomllib    
import sys

from contextlib import contextmanager
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QPushButton,
    QWizard, QWizardPage, QProgressBar, QVBoxLayout, QListWidget
)
from PySide6.QtCore import QObject, Signal, QRunnable

from mib.utils import cmd_exec, dscl, launchctl, pkgutil, superuser_cmd_context


class StepFailedError(Exception):
    pass


class UninstallerWorker(QObject, QRunnable):
    finished = Signal()
    failed = Signal(str)
    progress = Signal(int, str)

    @contextmanager
    def step(self, description):
        try:
            yield
        except StepFailedError as e:
            self.step_failed(f"[step: {description}]:\n{e}")
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

        with superuser_cmd_context(gui_prompt="PikeSquares uninstaller options"):
            with self.step("Stopping and unloading daemon from launchd"):
                # Stopping and unloading daemon from launchd
                daemon_path = Path(f"/Library/LaunchDaemons/{daemon_id}.plist")
                user_daemon_path = Path(f"/Library/LaunchAgents/{daemon_id}.plist")
                if not daemon_path.exists():
                    daemon_path = Path.home() / user_daemon_path
                if not daemon_path.exists():
                    daemon_path = Path("/Users/pikesquares") / user_daemon_path
                    unload_result = launchctl(
                        "unload",
                        str(daemon_path.resolve()), 
                        as_superuser_gui=True,
                        gui_prompt=gui_prompt
                    )
                    if unload_result.error:
                        raise StepFailedError(unload_result.stderr)
                else:
                    raise StepFailedError(f"Daemon {daemon_id} not found in system!")
                
            with self.step("Removing daemon plist file"):
                # Removing daemon plist file
                res = cmd_exec(
                    "rm",
                    "-f",
                    str(daemon_path.resolve()),
                    as_superuser=True,
                    # gui_prompt=gui_prompt
                )
                if res.error:
                    raise StepFailedError(res.stderr)

            # Forget package from package db
            with self.step("Forget package from package db"):
                packages = pkgutil(
                    pkgs=True,
                    as_superuser=True,
                    # gui_prompt=gui_prompt
                )
                if packages.success:
                    for pkg in packages.stdout.splitlines():
                        if daemon_id not in pkg:
                            continue
                        res = pkgutil(forget=pkg, as_superuser=True)
                        if res.error:
                            raise StepFailedError(res.stderr)
            
            # Remove pikesquares user
            with self.step("Remove pikesquares internal user"):
                # sudo /usr/bin/dscl . -delete /Users/dylan
                # list all users
                users = dscl(list="/Users")
                for user in users.stdout.splitlines():
                    if "pikesquares" in user:
                        res = dscl(
                            delete=f"/Users/{user}",
                            as_superuser=True,
                            # gui_prompt=gui_prompt
                        )
                        if res.error:
                            raise StepFailedError(res.stderr)
            
            with self.step("Removing Pikesquares runtime from PATH and restoring PATH to initial state"):
                import os
                path_vars_file = Path(f"/etc/path.d/50-pikesquares")
                if path_vars_file.exists() and path_vars_file.is_file():
                    res = cmd_exec(
                        "rm",
                        "-f",
                        "/etc/paths.d/50-pikesquares",
                        as_superuser=True,
                        # gui_prompt=gui_prompt
                    )
                    if res.error:
                        raise StepFailedError(res.stderr)
                    os.system("eval $(/usr/libexec/path_helper -s)")

            # Remove app data dir
            with self.step("Remove application data (certificates, configs and so on)"):
                for dir_ in user_app_data_dirs:
                    if dir_.exists() and dir_.is_dir():
                        res = cmd_exec(
                            "rm",
                            "-r",
                            "-f",
                            str(dir_.resolve()),
                            as_superuser=True,
                            # gui_prompt=gui_prompt
                        )
                        if res.error:
                            raise StepFailedError(res.stderr)

        self.finished.emit()


class IntroPage(QWizardPage):
    def __init__(self, product, parent=None):
        super(IntroPage, self).__init__(parent)

        self.setTitle("Introduction")
        self.setSubTitle(f"This wizard will remove {product['name']} from your computer. ")
        layout = QVBoxLayout()
        self.setLayout(layout)
    
    def initializePage(self) -> None:
        self.wizard().setButtonLayout([
            QWizard.WizardButton.Stretch,
            # QWizard.WizardButton.BackButton,
            QWizard.WizardButton.CancelButton,
            QWizard.WizardButton.NextButton,
            # QWizard.WizardButton.FinishButton
        ])


class UninstallPage(QWizardPage):
    def setup_ui(self, product):
        self.setTitle(f"Uninstalling {product['name']}...")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(5)

        self.list_widget = QListWidget()

        self.page_layout = QVBoxLayout()
        self.page_layout.addWidget(self.progress_bar)
        self.page_layout.addWidget(self.list_widget)
        
        self.setLayout(self.page_layout)

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

    def step_completed(self, value, msg):
        self.progress_bar.setValue(value)
        self.list_widget.addItem(f"✅ {msg}")

    def step_failed(self, m):
        self.list_widget.addItem(f"❌ {m}")
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
            QWizard.WizardButton.Stretch,
        ])
        self.worker.run()


class ConclusionPage(QWizardPage):
    def __init__(self, product, parent=None):
        super(ConclusionPage, self).__init__(parent)
        self.product = product

        self.setTitle("Finish")
        self.setSubTitle(f"The {product['name']} was successfully uninstalled from your computer")
        
        self.btn = QPushButton("Finish")
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # self.wizard().setButton(QtWidgets.QWizard.WizardButton.)
    def initializePage(self) -> None:
        self.wizard().setButtonLayout([
            QWizard.WizardButton.Stretch,
            # QWizard.WizardButton.BackButton,
            QWizard.WizardButton.CancelButton,
            # QWizard.WizardButton.NextButton,
            # QWizard.WizardButton.FinishButton
        ])
        self.wizard().setButtonText(QWizard.WizardButton.CancelButton, "Finish")

    def isFinalPage(self) -> bool:
        return True


class FailurePage(QWizardPage):
    def __init__(self, product, parent=None):
        super(FailurePage, self).__init__(parent)

        self.setTitle("Failure")
        self.setSubTitle(f"An error was occurred during {product['name']} uninstall")

        layout = QVBoxLayout()
        self.setLayout(layout)

    def isFinalPage(self) -> bool:
        return True


class PagesSequence:
    PAGE_INTRO = 0
    PAGE_UNINSTALL = 1
    PAGE_FAILURE = 2
    PAGE_CONCLUSION = 3


class UninstallWizard(QWizard):
    pages = [
        (PagesSequence.PAGE_INTRO, IntroPage),
        (PagesSequence.PAGE_UNINSTALL, UninstallPage),
        (PagesSequence.PAGE_CONCLUSION, ConclusionPage),
        (PagesSequence.PAGE_FAILURE, FailurePage)
    ]

    def __init__(self, config, parent=None):
        super(UninstallWizard, self).__init__(parent)

        self.product = config['product']

        for identifier, page_cls in self.pages:
            self.setPage(identifier, page_cls(product=self.product))

        self.setWindowTitle(f"{config['product']['name']} Uninstaller")

    def nextId(self) -> int:
        if self.currentId() == PagesSequence.PAGE_UNINSTALL and self.validateCurrentPage():
            return PagesSequence.PAGE_CONCLUSION
        return super().nextId()

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
    app = QApplication(sys.argv)
    wizard = UninstallWizard(
        config={'product': {'name': "PikeSquares", 'identifier': "com.eloquentbits.pikesquares"}}
    )
    wizard.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
