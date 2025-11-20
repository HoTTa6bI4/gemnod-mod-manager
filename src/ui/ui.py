# -*- coding: utf-8 -*-
from PyQt6 import QtGui
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import src.generated.fonts_rcc
import src.generated.textures_rcc


def qssFromFile(path):
    qss_file = QFile(path)
    if qss_file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        return bytes(qss_file.readAll()).decode("utf-8")
    else:
        raise FileNotFoundError("Error opening style sheet file")


""" Class specified for qss design """


class AzureFrame(QGroupBox):
    pass


class PathBrowser(AzureFrame):
    pathChanged = pyqtSignal(str, name="")

    def __init__(self, parent, browseFileMode, options=None, filters=""):
        # parent_layout = parent.layout()
        super().__init__(parent)
        self.path = ""
        self.pathEdit = QLineEdit(self)
        self.pathBrowseButton = QPushButton(self)
        self.contentsLayout = QHBoxLayout(self)
        self.browseDialog = QFileDialog(self, filter=filters)

        # Path line edit is supposed to take as much width, as possible
        # and no more height
        self.pathEdit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        self.browseDialog.setFileMode(browseFileMode)
        if options is not None:
            self.browseDialog.setOptions(options)
        self.browseDialog.setModal(False)
        self.browseDialog.setLabelText(QFileDialog.DialogLabel.Accept, "Browse")
        self.browseDialog.setWindowTitle("Browse Heroes V game folder")

        self.pathBrowseButton.setText("Browse")

        self.contentsLayout.addWidget(self.pathEdit)
        self.contentsLayout.addWidget(self.pathBrowseButton)
        self.setLayout(self.contentsLayout)

        # Synchronize elements
        self.pathEdit.textChanged.connect(self.setPath)
        self.pathBrowseButton.clicked.connect(self.browseDialog.show)
        self.browseDialog.fileSelected.connect(self.pathEdit.setText)

    def setPath(self, path):
        self.path = path
        self.pathChanged.emit(path)

    def getPath(self):
        return self.path


class GemnodWidget(AzureFrame):
    filters_list = [
        {'type': "AdvMapStaticShared", 'enabled': True},
        {'type': "AdvMapBuildingShared", 'enabled': True},
        {'type': "AdvMapDwellingShared", 'enabled': False},
        {'type': "AdvMapHeroShared", 'enabled': False},
        {'type': "AdvMapStandShared", 'enabled': True},
    ]

    def __init__(self, parent):
        super().__init__(parent)
        # Create widgets and inheritors
        self.contentsLayout = QVBoxLayout(self)
        self.contentsSplitter = QSplitter(self)
        self.mapBrowser = PathBrowser(self,
                                      QFileDialog.FileMode.ExistingFile,
                                      filters="H5 maps (*.h5m)")
        self.log = QTextEdit(self)
        self.patchMap = QPushButton(parent=self, text="Patch")
        self.logNbrowseSectionWidget = QWidget(self.contentsSplitter)
        self.logNbrowseLayout = QGridLayout(self.logNbrowseSectionWidget)

        # Customize gemnod object filters
        self.filtersBox = QGroupBox(self)
        self.filtersLayout = QVBoxLayout(self.filtersBox)
        self.filtersCheckBoxes = []
        for filter in self.filters_list:
            checkBox = QCheckBox(text=filter['type'], parent=self)
            checkBox.setChecked(filter['enabled'])
            checkBox.setEnabled(filter['enabled'])
            self.filtersCheckBoxes.append(checkBox)

        # Customize contained widgets
        self.contentsLayout.setContentsMargins(8, 8, 8, 8)
        self.contentsSplitter.setOrientation(Qt.Orientation.Horizontal)
        # self.contentsSplitter.setChildrenCollapsible(False)
        # self.contentsSplitter.setStretchFactor(0, 10)
        # self.contentsSplitter.setStretchFactor(1, 1)
        self.contentsSplitter.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # self.log.setReadOnly(True)
        self.log.setFrameStyle(QFrame.Shape.NoFrame)
        self.logNbrowseLayout.setContentsMargins(0, 0, 0, 0)
        self.logNbrowseLayout.setSpacing(0)
        # self.logNbrowseSectionWidget.setSizePolicy(
        #     QSizePolicy.Policy.Minimum,
        #     QSizePolicy.Policy.Expanding
        # )

        self.filtersBox.setTitle("AdvMap objects filters")
        self.filtersBox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.filtersBox.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(qssFromFile("../../heroes-gemnod-section.qss"))

        self.mapBrowser.pathChanged.connect(lambda s: self.messageToLog("Map chosen: " + s))

        # Place widgets on layouts
        self.logNbrowseLayout.addWidget(self.mapBrowser, 0, 0)
        self.logNbrowseLayout.addWidget(self.patchMap, 0, 1)
        self.logNbrowseLayout.addWidget(self.log, 1, 0, -1, 2)
        for checkBox in self.filtersCheckBoxes:
            self.filtersLayout.addWidget(checkBox)
        self.filtersLayout.addStretch(0)
        self.contentsLayout.addWidget(self.contentsSplitter)
        self.contentsSplitter.addWidget(self.logNbrowseSectionWidget)
        self.contentsSplitter.addWidget(self.filtersBox)

    def messageToLog(self, message):
        self.log.append(f"> {message}")


class GemnodModManager(object):

    def __init__(self, window):
        # Window central maintaining widget - scroll area (so the contents would be accessible at any
        # window size
        #
        self.parent = window

        self.mainScrollArea = QScrollArea(self.parent)
        self.mainScrollAreaWidget = QWidget()
        self.mainScrollAreaWidgetContentsLayout = QVBoxLayout(self.mainScrollAreaWidget)

        self.gameRootBrowser = PathBrowser(self.mainScrollAreaWidget,
                                           QFileDialog.FileMode.Directory,
                                           QFileDialog.Option.ShowDirsOnly)

        self.ComponentsSplitter = QSplitter(self.mainScrollAreaWidget)
        self.ComponentsTable = QTableWidget(self.ComponentsSplitter)

        self.gemnodSection = GemnodWidget(self.ComponentsSplitter)
        self.gameRootBrowser.pathChanged.connect(self.gemnodSection.mapBrowser.browseDialog.setDirectory)

        self.menubar = QMenuBar(MainWindow)
        self.statusbar = QStatusBar(MainWindow)

    def setupUi(self):
        # Setup Main Window
        #
        self.parent.resize(1200, 800)
        self.parent.setStyleSheet(qssFromFile("../../heroes-main.qss"))

        # Setup contents scroll area
        self.mainScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.mainScrollArea.setWidgetResizable(True)

        # Setup area of browsing game folder
        self.gameRootBrowser.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))
        self.gameRootBrowser.setTitle("Heroes V game folder")

        # Setup area of gemnod map patcher
        self.gemnodSection.setTitle("GEMNOD effects creator")

        # Setup contents splitter in scroll area
        self.ComponentsSplitter.setOrientation(Qt.Orientation.Vertical)
        self.ComponentsSplitter.setChildrenCollapsible(True)

        # Setup installed mods table
        self.ComponentsTable.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.ComponentsTable.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.ComponentsTable.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.ComponentsTable.setShowGrid(False)
        self.ComponentsTable.setColumnCount(3)
        self.ComponentsTable.setRowCount(4)
        item = QTableWidgetItem()
        self.ComponentsTable.setVerticalHeaderItem(0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setVerticalHeaderItem(1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setVerticalHeaderItem(2, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setVerticalHeaderItem(3, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setHorizontalHeaderItem(0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setHorizontalHeaderItem(1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setHorizontalHeaderItem(2, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(0, 0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(0, 1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(0, 2, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(1, 0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(1, 1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(1, 2, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(2, 0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(2, 1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(2, 2, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(3, 0, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(3, 1, item)
        item = QTableWidgetItem()
        self.ComponentsTable.setItem(3, 2, item)
        self.ComponentsTable.horizontalHeader().setHighlightSections(False)
        self.ComponentsTable.horizontalHeader().setStretchLastSection(True)
        self.ComponentsTable.verticalHeader().setVisible(False)
        self.ComponentsTable.verticalHeader().setStretchLastSection(False)

        # Add scroll area parts and relate scroll area with its central widget
        # note: QSplitter self.ComponentsSplitter automatically lays its children inside
        self.mainScrollAreaWidgetContentsLayout.addWidget(self.gameRootBrowser)
        self.mainScrollAreaWidgetContentsLayout.addWidget(self.ComponentsSplitter)
        self.mainScrollArea.setWidget(self.mainScrollAreaWidget)

        # Setup parent widget
        self.parent.setCentralWidget(self.mainScrollArea)
        self.parent.setMenuBar(self.menubar)
        self.parent.setStatusBar(self.statusbar)
        self.parent.setWindowIcon(QtGui.QIcon("../../textures/Icon.ico"))

        self.retranslateUi()
        QMetaObject.connectSlotsByName(self.parent)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.parent.setWindowTitle("MainWindow")
        self.ComponentsTable.setSortingEnabled(True)
        item = self.ComponentsTable.verticalHeaderItem(0)
        item.setText("1")
        item = self.ComponentsTable.verticalHeaderItem(1)
        item.setText("2")
        item = self.ComponentsTable.verticalHeaderItem(2)
        item.setText("3")
        item = self.ComponentsTable.verticalHeaderItem(3)
        item.setText("4")
        item = self.ComponentsTable.horizontalHeaderItem(0)
        item.setText("Modpack")
        item = self.ComponentsTable.horizontalHeaderItem(1)
        item.setText("Installed version")
        item = self.ComponentsTable.horizontalHeaderItem(2)
        item.setText("Latest Version")
        __sortingEnabled = self.ComponentsTable.isSortingEnabled()
        self.ComponentsTable.setSortingEnabled(False)
        item = self.ComponentsTable.item(0, 0)
        item.setText("GemOrange")
        item = self.ComponentsTable.item(0, 1)
        item.setText("1.0.0")
        item = self.ComponentsTable.item(0, 2)
        item.setText("1.0.0")
        item = self.ComponentsTable.item(1, 0)
        item.setText("GemBlue")
        item = self.ComponentsTable.item(1, 1)
        item.setText("-")
        item = self.ComponentsTable.item(1, 2)
        item.setText("0.1.6")
        item = self.ComponentsTable.item(2, 0)
        item.setText("ENOD")
        item = self.ComponentsTable.item(2, 1)
        item.setText("0.1.0")
        item = self.ComponentsTable.item(2, 2)
        item.setText("1.0.0")
        item = self.ComponentsTable.item(3, 0)
        item.setText("Scratch")
        item = self.ComponentsTable.item(3, 1)
        item.setText("-")
        item = self.ComponentsTable.item(3, 2)
        item.setText("-")
        self.ComponentsTable.setSortingEnabled(__sortingEnabled)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    MainWindow.setObjectName("MainWindow")
    QtGui.QFontDatabase.addApplicationFont(":/common/fonts/fonts/Monotype-Corsiva-Bold.ttf")
    ui = GemnodModManager(MainWindow)
    ui.setupUi()
    MainWindow.show()
    sys.exit(app.exec())
