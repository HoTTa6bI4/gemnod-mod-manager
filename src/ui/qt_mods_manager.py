import src.scripts.mods_manager
from PyQt6 import QtGui
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from src.scripts.mods_manager import ModManager, Progress
from functools import wraps


class ComboBoxDelegate(QStyledItemDelegate):

    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.comboBox = None

    def createEditor(self, parent, option: QStyleOptionViewItem, index: QModelIndex):
        comboBox = QComboBox(parent)
        comboBox.setEditable(False)
        comboBox.addItems(self.items())

        comboBox.activated.connect(self.finishEditing)

        self.comboBox = comboBox

        return comboBox

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        editor.setCurrentText(index.data())

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        model.setData(index, editor.currentText())

    def updateEditorGeometry(self, editor: QComboBox, option: QStyleOptionViewItem, index: QModelIndex):
        editor.setGeometry(option.rect)

    def items(self):
        return self.factory()

    def finishEditing(self):
        self.commitData.emit(self.comboBox)
        self.closeEditor.emit(self.comboBox)


class VersionsDelegate(ComboBoxDelegate):

    def __init__(self, mod: ModManager.SupportedMod, parent=None):
        super().__init__(mod.getAllVersions, parent)

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        version = index.data()
        offset = self.factory().index(version)
        editor.setCurrentIndex(offset)

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        version = self.factory()[editor.currentIndex()]
        model.setData(index, version)

    def items(self):
        result = []
        for item in self.factory():
            result.append(item.name)
        return result


# Qt-compatiable ModManager
class QModManager(QObject, ModManager):

    currentOperationProgressChanged = pyqtSignal(Progress, name='')
    currentOperationFinished = pyqtSignal(name='')
    currentOperationCanceled = pyqtSignal(name='')
    currentOperationFailed = pyqtSignal(Exception, name='')

    def __init__(self, mod_db_url, parent=None):
        QObject.__init__(self, parent)
        ModManager.__init__(self, mod_db_url)
        self.cancel_current = False

    def cancelCurrentOperation(self):
        self.cancel_current = True

    def progressSignalsDecorator(self, progress_generator):

        @wraps(gen)
        def wrap(*args, **kwargs):
            try:
                for progress in gen(*args, **kwargs):
                    if self.cancel_current:
                        self.cancel_current = False
                        self.currentOperationCanceled.emit()
                        break
                    self.currentOperationProgressChanged.emit(progress)
                    yield progress
            except Exception as exc:
                self.currentOperationFailed.emit(exc)
            else:
                self.currentOperationFinished.emit()

        return wrap


