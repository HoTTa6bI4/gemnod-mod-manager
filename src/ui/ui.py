# -*- coding: utf-8 -*-
from PyQt6 import QtGui
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import src.generated.fonts_rcc
import src.generated.textures_rcc
from math import pi as PI, sin, cos
from enum import Enum
from typing import Dict, Optional


def qssFromFile(path):
    qss_file = QFile(path)
    if qss_file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        return bytes(qss_file.readAll()).decode("utf-8")
    else:
        raise FileNotFoundError("Error opening style sheet file")


""" Class specified for qss design """


class AzureGroupBox(QGroupBox):
    pass


class PathBrowser(AzureGroupBox):
    pathChanged = pyqtSignal(str, name="")

    def __init__(self, parent, filters=""):
        # parent_layout = parent.layout()
        super().__init__(parent)
        self.path = ""
        self.pathEdit = QLineEdit(self)
        self.pathBrowseButton = QPushButton(self)
        self.contentsLayout = QHBoxLayout(self)
        self.browseDialog = QFileDialog(self, filter=filters)

    def setupUI(self, browseFileMode, options=None):
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


class HexagonJogDial(QWidget):
    class HexagonVertex(Enum):
        right = 0
        topRight = PI / 3
        topLeft = 2 * PI / 3
        left = PI
        bottomLeft = 4 * PI / 3
        bottomRight = 5 * PI / 3

    def __init__(self, parent, smallestRadius, biggestRadius, innerDistance, borderThickness):
        super().__init__(parent)
        self.r = smallestRadius  # the smallest button radius (side buttons)
        self.alpha = borderThickness / self.r  # border width / r
        self.beta = innerDistance / self.r  # distance between side buttons and center / r
        self.gamma = biggestRadius / self.r  # central button radius / r

        # Side buttons...
        self.sideButtons: Dict[HexagonJogDial.HexagonVertex, Optional[QAbstractButton]] = {
            HexagonJogDial.HexagonVertex.right: None,
            HexagonJogDial.HexagonVertex.topRight: None,
            HexagonJogDial.HexagonVertex.topLeft: None,
            HexagonJogDial.HexagonVertex.left: None,
            HexagonJogDial.HexagonVertex.bottomLeft: None,
            HexagonJogDial.HexagonVertex.bottomRight: None
        }
        # ...surrounding central button
        self.centralButton = None

    def setCentralButton(self, button: QAbstractButton):
        self.centralButton = button
        self.centralButton.setParent(self)

    def getCentralButton(self):
        return self.centralButton

    def setSideButton(self, pos: HexagonVertex, button: QAbstractButton):
        self.sideButtons[pos] = button
        self.sideButtons[pos].setParent(self)

    def getSideButton(self, pos: HexagonVertex):
        return self.sideButtons[pos]

    def placeButtons(self):

        b = self.r * self.alpha
        d = self.r * self.beta
        R = self.r * self.gamma

        # print(f'> Placing buttons (r={self.r}, R={R}, d={d}) inside rect {self.width()} x {self.height()}')

        # Hexagon center computation (center of central button)
        C_x = self.width()//2  # - d + self.r + b
        C_y = self.height()//2  # - d * sin(PI / 3) + self.r + b
        # left corner of central button
        x = C_x - R
        y = C_y - R
        # print(f"> Central button center: ({C_x}, {C_y}), top left: ({x}, {y})")
        if self.centralButton:
            self.centralButton.setGeometry(round(x), round(y), round(2 * R), round(2 * R))

        for pos_angle, button in self.sideButtons.items():
            # Center of button coordinates
            c_x = C_x + d * cos(-pos_angle.value)
            c_y = C_y + d * sin(-pos_angle.value)
            # Top left corner of button
            x = c_x - self.r
            y = c_y - self.r
            # print(f">> {pos_angle} button center: ({c_x}, {c_y}), top left: ({x}, {y})")
            if button:
                button.setGeometry(int(x), int(y), int(2 * self.r), int(2 * self.r))
                # print(f'>> Button {pos_angle} placed in {button.geometry().x()},{button.geometry().y()}')

    def setupUI(self):
        # print(f'Setting up JogDialSize: {self.sizeHint().width()} x {self.sizeHint().height()}')
        self.setAutoFillBackground(True)
        self.placeButtons()

    def sizeHint(self) -> QSize:
        w = 2 * self.r * (self.alpha + self.beta + 1)
        h = 2 * self.r * (self.alpha + self.beta*sin(PI/3) + 1)
        # print(f"> Recommended size: {int(round(w))} x {int(round(h))}")
        return QSize(int(round(w)), int(round(h)))

    def resizeEvent(self, event: Optional[QtGui.QResizeEvent]):
        super().resizeEvent(event)
        if not event:
            return
        wh = (self.beta+self.alpha+1)/(self.beta*sin(PI/3)+self.alpha+1)
        width = event.size().width()
        height = event.size().height()
        # print(f'Resizing JogDialSize to: {width} x {height}')
        # print(f"width/height coeff: {float(width)/float(height)} (ideal: {wh})")
        if width > round(wh * height):
            self.r = height/((self.alpha+self.beta*sin(PI/3)+1)*2)
        elif width <= round(wh * height):
            self.r = width/((self.alpha+self.beta+1)*2)
        self.placeButtons()

    def showEvent(self, event: Optional[QtGui.QShowEvent]):
        super().showEvent(event)
        self.setupUI()

    def paintEvent(self, event: Optional[QtGui.QPaintEvent]) -> None:
        opt = QStyleOption()
        opt.initFrom(self)
        p = QStylePainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        # super().paintEvent(event)


class GemnodWidget(AzureGroupBox):
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
        self.mapBrowser = PathBrowser(self, filters="H5 maps (*.h5m)")
        self.log = QTextEdit(self)
        self.patchMap = QPushButton("Patch", self)
        self.logNbrowseSectionWidget = QWidget(self.contentsSplitter)
        self.logNbrowseLayout = QGridLayout(self.logNbrowseSectionWidget)

        # Customize gemnod object filters
        self.filtersBox = QGroupBox(self)
        self.filtersLayout = QVBoxLayout(self.filtersBox)
        self.filtersCheckBoxes = []
        for filter in self.filters_list:
            checkBox = QCheckBox(filter['type'], self)
            checkBox.setChecked(filter['enabled'])
            checkBox.setEnabled(filter['enabled'])
            self.filtersCheckBoxes.append(checkBox)

        # Setup map browser
        self.mapBrowser.setupUI(QFileDialog.FileMode.ExistingFile)

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

        # All contents may be scrolled
        self.scrollArea = QScrollArea(self.parent)

        # Splitter for all widgets that will be added to mainScrollAreaWidget
        self.sectionsSplitter = QSplitter(self.scrollArea)

        # Text edit with file mode to choose Heroes V root (installation) folder
        self.gameRootBrowser = PathBrowser(self.sectionsSplitter)

        self.modsContainer = QWidget(self.sectionsSplitter)
        self.modsContainerLayout = QVBoxLayout(self.modsContainer)
        self.modsAndJogDialSplitter = QSplitter(self.modsContainer)

        # Main table of managed mods and components
        self.modsTable = QTableWidget(self.modsAndJogDialSplitter)

        # Jog dial for operations on mods from table
        self.jogDialContainer = QWidget(self.modsAndJogDialSplitter)
        self.jogDialLayout = QVBoxLayout(self.jogDialContainer)
        self.modsJogDial = HexagonJogDial(self.jogDialContainer,
                                          smallestRadius=28.,
                                          biggestRadius=40.,
                                          innerDistance=77.,
                                          borderThickness=5.)
        self.modsJogDial.setObjectName('jogDial')
        self.downloadInstallButton = QPushButton(self.modsJogDial)
        self.uninstallButton = QPushButton(self.modsJogDial)
        self.updateModButton = QPushButton(self.modsJogDial)
        self.enableModButton = QPushButton(self.modsJogDial)
        self.disableModButton = QPushButton(self.modsJogDial)
        self.modInfoButton = QPushButton(self.modsJogDial)

        self.managementProgress = QProgressDialog(self.parent)

        self.gemnodSection = GemnodWidget(self.sectionsSplitter)

        self.menubar = QMenuBar(MainWindow)
        self.statusbar = QStatusBar(MainWindow)

    def setupGameRootBrowser(self):
        # Setup area of browsing game folder
        self.gameRootBrowser.setupUI(QFileDialog.FileMode.Directory,
                                     QFileDialog.Option.ShowDirsOnly)
        self.gameRootBrowser.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))
        self.gameRootBrowser.setTitle("Heroes V game folder")
        self.gameRootBrowser.pathChanged.connect(self.gemnodSection.mapBrowser.browseDialog.setDirectory)

    def setupModsTable(self):
        # Setup installed mods table
        # self.componentsTable.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.modsTable.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.modsTable.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.modsTable.setShowGrid(False)
        self.modsTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.modsTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.modsTable.setColumnCount(3)
        self.modsTable.setRowCount(4)
        for i in range(4):
            self.modsTable.setVerticalHeaderItem(i, QTableWidgetItem())
            for j in range(3):
                self.modsTable.setHorizontalHeaderItem(j, QTableWidgetItem())
                self.modsTable.setItem(i, j, QTableWidgetItem())

        self.modsTable.verticalHeader().setVisible(False)
        self.modsTable.verticalHeader().setStretchLastSection(False)
        self.modsTable.horizontalHeader().setVisible(True)
        self.modsTable.horizontalHeader().setStretchLastSection(True)
        self.modsTable.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setupModsJogDial(self):

        self.jogDialLayout.setContentsMargins(0, 0, 0, 0)
        self.jogDialLayout.setSpacing(0)
        self.jogDialLayout.addWidget(self.modsJogDial)
        self.jogDialLayout.addStretch(1)

        self.downloadInstallButton.setObjectName('downloadInstall_button')

        self.uninstallButton.setObjectName('uninstall_button')
        self.uninstallButton.hide()

        self.updateModButton.setObjectName('update_button')

        self.enableModButton.setObjectName('enable_button')

        self.disableModButton.setObjectName('disable_button')
        self.disableModButton.hide()

        self.modInfoButton.setObjectName('info_button')

        self.modsJogDial.setCentralButton(self.downloadInstallButton)
        self.modsJogDial.setSideButton(HexagonJogDial.HexagonVertex.topLeft,
                                       self.updateModButton)
        self.modsJogDial.setSideButton(HexagonJogDial.HexagonVertex.topRight,
                                       self.enableModButton)
        self.modsJogDial.setSideButton(HexagonJogDial.HexagonVertex.right,
                                       self.modInfoButton)

    def setupModsSection(self):
        # Setup mods + buttons container
        self.modsContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.modsContainerLayout.addWidget(self.modsAndJogDialSplitter)

        self.setupModsTable()
        self.setupModsJogDial()

        # Setup splitter between buttons group and mods table
        self.modsAndJogDialSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.modsAndJogDialSplitter.setChildrenCollapsible(True)
        self.modsAndJogDialSplitter.addWidget(self.modsTable)
        self.modsAndJogDialSplitter.addWidget(self.jogDialContainer)
        # self.modsAndJogDialSplitter.setSizes([self.parent.width(), 220])

        self.jogDialContainer.setFixedWidth(220)  # self.modsJogDial.sizeHint().width())

    def setupUi(self):
        # Setup Main Window
        #
        self.parent.resize(1200, 600)

        # Setup contents scroll area
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setWidgetResizable(True)

        # Setup area of gemnod map patcher
        self.gemnodSection.setTitle("GEMNOD effects creator")
        self.gemnodSection.hide()

        # Setup contents splitter in scroll area
        self.sectionsSplitter.setOrientation(Qt.Orientation.Vertical)
        self.sectionsSplitter.setChildrenCollapsible(True)
        self.sectionsSplitter.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))

        self.setupGameRootBrowser()
        self.setupModsSection()
        # print(self.modsContainer.width())
        # total_width = self.modsContainer.minimumSizeHint().width()
        # jogDial_width = self.modsButtonsGroup.sizeHint().width()
        # self.modsAndButtonsSplitter.setSizes([total_width-jogDial_width, jogDial_width])

        # Add scroll area parts and relate scroll area with its central widget
        # note: QSplitter self.ComponentsSplitter automatically lays its children inside
        self.scrollArea.setWidget(self.sectionsSplitter)

        # Setup parent widget
        self.parent.setCentralWidget(self.scrollArea)
        self.parent.setMenuBar(self.menubar)
        self.parent.setStatusBar(self.statusbar)
        self.parent.setWindowIcon(QtGui.QIcon("../../textures/Icon.ico"))

        self.parent.setStyleSheet(qssFromFile("../../heroes-main.qss"))
        self.retranslateUi()
        # QMetaObject.connectSlotsByName(self.parent)



    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.parent.setWindowTitle("GEMNOD mod manager")
        self.modsTable.setSortingEnabled(True)
        item = self.modsTable.verticalHeaderItem(0)
        item.setText("1")
        item = self.modsTable.verticalHeaderItem(1)
        item.setText("2")
        item = self.modsTable.verticalHeaderItem(2)
        item.setText("3")
        item = self.modsTable.verticalHeaderItem(3)
        item.setText("4")
        item = self.modsTable.horizontalHeaderItem(0)
        item.setText("Modpack")
        item = self.modsTable.horizontalHeaderItem(1)
        item.setText("Installed version")
        item = self.modsTable.horizontalHeaderItem(2)
        item.setText("Latest Version")
        __sortingEnabled = self.modsTable.isSortingEnabled()
        self.modsTable.setSortingEnabled(False)
        item = self.modsTable.item(0, 0)
        item.setText("GemOrange")
        item = self.modsTable.item(0, 1)
        item.setText("1.0.0")
        item = self.modsTable.item(0, 2)
        item.setText("1.0.0")
        item = self.modsTable.item(1, 0)
        item.setText("GemBlue")
        item = self.modsTable.item(1, 1)
        item.setText("-")
        item = self.modsTable.item(1, 2)
        item.setText("0.1.6")
        item = self.modsTable.item(2, 0)
        item.setText("ENOD")
        item = self.modsTable.item(2, 1)
        item.setText("0.1.0")
        item = self.modsTable.item(2, 2)
        item.setText("1.0.0")
        item = self.modsTable.item(3, 0)
        item.setText("Scratch")
        item = self.modsTable.item(3, 1)
        item.setText("-")
        item = self.modsTable.item(3, 2)
        item.setText("-")
        self.modsTable.setSortingEnabled(__sortingEnabled)


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
