from qtpy import QtCore, QtGui, QtWidgets
import traceback
import sys
from typing import cast, Type, TYPE_CHECKING, Optional, Callable, Any, Union, List

if TYPE_CHECKING:
    from pcbre.model.project import Project

# ipython kernel-based console for tab completion and all the goodies
class JupyterConsoleDockWidget(QtWidgets.QDockWidget):
    def __init__(self, project: 'Project') -> None:
        super(JupyterConsoleDockWidget, self).__init__("Console")
        self.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)

        self.project = project

        # Create an in-process kernel
        kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel(show_banner=False)
        kernel = kernel_manager.kernel

        kernel.shell.push({'project': project})

        kernel_client = kernel_manager.client()
        kernel_client.start_channels()

        ipython_widget = RichJupyterWidget()
        ipython_widget.kernel_manager = kernel_manager
        ipython_widget.kernel_client = kernel_client

        self.setWidget(ipython_widget)


class Output:
    def __init__(self, stream: int, cb : Callable[[int, str], None]) -> None:
        self.stream = stream
        self.cb = cb

    def write(self, d: str) -> None:
        self.cb(self.stream, d)


class CapturedOutput:
    def __init__(self, output_callback: Callable[[int, str], None]) -> None:
        self.output_callback = output_callback
        self.my_stdout = Output(1, output_callback)
        self.my_stderr = Output(2, output_callback)

    def __enter__(self) -> None:
        self.saved = sys.stdout, sys.stdin, sys.stderr

        # safe in this case
        sys.stdout, sys.stdin, sys.stderr = (self.my_stdout, None, self.my_stderr) # type: ignore

    def __exit__(self, excType: Any, excValue: Any, excTB: Any) -> None:
        sys.stdout, sys.stdin, sys.stderr = self.saved

        if excType:
            exc = "\n".join(traceback.format_exception(excType, excValue, excTB))
            self.output_callback(2, exc)


key_map = {}
for name in dir(QtCore.Qt):
    if name.startswith("Key"):
        key_map[getattr(QtCore.Qt, name)] = name


class ConsoleEditWidget(QtWidgets.QLineEdit):
    submit = QtCore.Signal((str,))

    def __init__(self, project: 'Project') -> None:
        super(ConsoleEditWidget, self).__init__()
        self.project = project
        self.history : List[str] = []
        self.history_index = -1
        self.current : Optional[str] = None

    def hist(self, n: int) -> None:
        if self.history_index == -1:
            if n == -1:
                return
            else:
                self.current = self.text()

        self.history_index += n

        if self.history_index < -1:
            self.history_index = -1
        else:
            self.history_index = min(self.history_index, len(self.history) - 1)

        if self.history_index == -1:
            s = self.current
            if s is None:
                s = ""
            self.setText(s)
        elif self.history:
            self.setText(self.history[len(self.history) - self.history_index - 1])

    def do_autocomplete(self) -> None:
        # TODO for future
        pass

    def do_return(self) -> None:
        text = self.text()

        if text:
            self.history.append(text)
        self.history_index = -1

        self.submit.emit(text)

        self.clear()

    def event(self, evt: QtCore.QEvent) -> bool:
        # Capture the Tab keypress
        if evt.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            kevt = cast(QtGui.QKeyEvent, evt)
            if kevt.key() in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                if kevt.type() == QtCore.QEvent.KeyRelease:
                    self.keyReleaseEvent(kevt)
                kevt.accept()
                return True

        return super(ConsoleEditWidget, self).event(evt)

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        if evt.key() == QtCore.Qt.Key_Up:
            self.hist(1)
        elif evt.key() == QtCore.Qt.Key_Down:
            self.hist(-1)
        elif evt.key() == QtCore.Qt.Key_Tab:
            self.do_autocomplete()
        elif evt.key() in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return):
            self.do_return()
        else:
            super(ConsoleEditWidget, self).keyReleaseEvent(evt)


class BasicConsoleWidget(QtWidgets.QWidget):
    def __init__(self, project: 'Project') -> None:
        super(BasicConsoleWidget, self).__init__()
        self.project = project

        import code
        self.console = code.InteractiveConsole(locals={'project': project})

        self.output = QtWidgets.QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.edit = ConsoleEditWidget(project)
        self.edit.submit.connect(self.do_console_input)
        # self.output.setDefaultFont(QtGui.QFont("monospace"))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self.output)
        layout.addWidget(self.edit)

    def do_console_output(self, stream: int, s: str) -> None:
        if s[-1] == "\n":
            s = s[:-1]
        if stream == 1:
            self.output.appendHtml(s.replace("\n", "<br>"))
        else:
            self.output.appendHtml("<span style='color:red'>%s</span>" % s)

    def do_console_input(self, s: str) -> None:
        with CapturedOutput(self.do_console_output):
            self.output.appendPlainText(">>> %s" % s)
            self.console.push(s)


# Basic console if no ipython
class BasicConsoleDockWidget(QtWidgets.QDockWidget):
    def __init__(self, project: 'Project') -> None:
        super(BasicConsoleDockWidget, self).__init__("Console")
        self.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)

        self.w = BasicConsoleWidget(project)
        self.setWidget(self.w)


# TODO: add pref to disable
disable_qtconsole = False

if not disable_qtconsole:
    try:
        from qtconsole.rich_jupyter_widget import RichJupyterWidget  # type: ignore
        from qtconsole.inprocess import QtInProcessKernelManager     # type: ignore
    except ImportError:
        disable_qtconsole = True


ConsoleWidgetT = Union[BasicConsoleDockWidget,JupyterConsoleDockWidget]
ConsoleWidget : Type[ConsoleWidgetT]

if disable_qtconsole:
    ConsoleWidget = BasicConsoleDockWidget
else:
    ConsoleWidget = JupyterConsoleDockWidget
