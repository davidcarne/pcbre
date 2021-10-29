from typing import TYPE_CHECKING

import OpenGL.GL as GL  # type: ignore

from pcbre.matrix import scale
from pcbre.model.imagelayer import KeyPoint, KeyPointAlignment, RectAlignment, ImageLayer
from pcbre.ui.boardviewwidget import BaseViewWidget
from pcbre.ui.dialogs.layeralignmentdialog.keypointalign import KeypointAlignmentModel, KeypointAlignmentControllerView, \
    KeypointAlignmentWidget
from pcbre.ui.dialogs.layeralignmentdialog.rectalign import RectAlignSettingsWidget
from pcbre.ui.dialogs.layeralignmentdialog.visibilitywidget import VisibilityModelRoot, VisibilityModelGroup, \
    VisibilityModelLeaf, VisibilityTree, Visible


from pcbre.ui.gl.textrender import TextBatcher
from pcbre.ui.undo import UndoStack, UndoFunc, sig
from pcbre.view.imageview import ImageView
from pcbre.view.originview import OriginView
from .rectalign import RectAlignmentControllerView, RectAlignmentModel

from qtpy import QtCore, QtWidgets
import numpy
import enum
import pcbre.model.project
import pcbre.model.imagelayer

from typing import Optional, List, Any, Set, Callable
if TYPE_CHECKING:
    from pcbre.ui.dialogs.layeralignmentdialog.visibilitywidget import VisibilityNode
    from typing_extensions import Protocol
    from pcbre.ui.gl.glshared import GLShared

    class OverlayProtocol(Protocol):
        def initializeGL(self, gls: GLShared) -> None:
            ...

        def render(self, viewstate: Any) -> None:
            ...

__author__ = 'davidc'



class AlignBy(enum.Enum):
    Dimensions = 0
    KeyPoints = 1


class ViewMode(enum.Enum):
    UnAligned = 0
    Aligned = 1

    def is_aligned(self) -> bool:
        return self == ViewMode.Aligned


class AlignmentViewModel:
    def __init__(self, image) -> None:
        self.ra = RectAlignmentModel(image)
        self.kp = KeypointAlignmentModel(image)

        self.__align_by : AlignBy = AlignBy.Dimensions
        self.__view_mode : ViewMode = ViewMode.UnAligned

        self.__cb_list: List[Callable[[], None]] = []

    @property
    def align_by(self) -> AlignBy:
        return self.__align_by

    @align_by.setter
    def align_by(self, new_value: AlignBy) -> None:
        changed = new_value != self.__align_by
        self.__align_by = new_value

        if changed:
            self.__notify()

    @property
    def view_mode(self) -> ViewMode:
        return self.__view_mode

    @view_mode.setter
    def view_mode(self, new_value: ViewMode):
        changed = new_value != self.__view_mode
        self.__view_mode = new_value

        if changed:
            self.__notify()

    def __notify(self) -> None:
        for i in self.__cb_list:
            i()

    def register_notify(self, target: Callable):
        self.__cb_list.append(target)


@UndoFunc
def cmd_set_align_by(target: 'LayerAlignmentDialog', align_mode: AlignBy):
    old_state = target.model.align_by
    target.set_align_by(align_mode)
    return sig(old_state)


class AlignmentViewWidget(BaseViewWidget):
    def __init__(self, vis_model: VisibilityModelRoot, il: ImageLayer, model) -> None:
        BaseViewWidget.__init__(self)

        self.il = il
        self.iv = ImageView(il)
        self.model = model
        self.vis_model = vis_model

        self.overlays: Set[OverlayProtocol] = set()
        self.active_overlays: Set[OverlayProtocol] = set()

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.viewState.transform = scale(0.80)

        self.originView = OriginView()

        self.text_batch = TextBatcher(self.gls.text)

    def reinit(self) -> None:
        self.iv.initGL(self.gls)
        self.iv_cache = {}

        for ov in self.overlays:
            ov.initializeGL(self.gls)

        self.originView.initializeGL(self.gls)
        self.text_batch.initializeGL()

    def get_imageview(self, il: ImageLayer) -> None:
        if il is self.iv.il:
            return self.iv

        if il not in self.iv_cache:
            iv = ImageView(il)

            iv.initGL(self.gls)

            self.iv_cache[il] = iv

        return self.iv_cache[il]

    def get_flattened(self, n: 'VisibilityNode' = None, l: List = None) -> List[Any]:
        if l is None:
            l = []

        if n is None:
            n = self.vis_model

        for i in n.children:
            if i.visible == Visible.YES and i.obj is not None:
                l.append(i.obj)
            else:
                self.get_flattened(i, l)

        return l

    def render(self):
        self.text_batch.restart()
        GL.glEnable(GL.GL_BLEND)
        if self.model.align_by == AlignBy.Dimensions:
            if self.model.view_mode == ViewMode.UnAligned:
                self.iv.mat = numpy.identity(3)
            else:
                self.iv.mat = self.model.ra.image_matrix
        else:
            if self.model.view_mode == ViewMode.UnAligned:
                self.iv.mat = numpy.identity(3)
            else:
                self.iv.mat = self.model.kp.image_matrix

        # Render the base image
        if self.model.view_mode == ViewMode.UnAligned:
            self.iv.render(self.viewState.glMatrix)
        else:
            # Draw all visible layers bottom to top
            all_ils = list(reversed(self.get_flattened()))

            for il in all_ils:
                iv = self.get_imageview(il)
                iv.render(self.viewState.glMatrix)

        for ovl in self.active_overlays:
            ovl.render(self.viewState)

        self.text_batch.render()

    def focusNextPrevChild(self, next) -> bool:
        found = False

        if self.interactionDelegate:
            found = self.interactionDelegate.next_prev_child(next)

        if not found:
            return super(AlignmentViewWidget, self).focusNextPrevChild(next)
        return True

    def focusOutEvent(self, evt) -> None:
        if self.interactionDelegate:
            self.interactionDelegate.focusOutEvent(evt)


class LayerAlignmentDialog(QtWidgets.QDialog):
    def __init__(self, parent,
                 project: 'pcbre.model.project.Project',
                 il: 'pcbre.model.imagelayer.ImageLayer'):

        QtWidgets.QDialog.__init__(self, parent)
        self.resize(800, 600)
        self.setSizeGripEnabled(True)

        self.project: pcbre.model.project.Project = project
        self.il: pcbre.model.imagelayer.ImageLayer = il

        self.model: AlignmentViewModel = AlignmentViewModel(self.il)

        # Build the treeView model for layer visibility
        self.buildVisibilityModel()

        # Always align keypoint-based load. Works with unaligned images
        self.model.kp.load(self.project)

        # Keypoint-align, initialize from existing align project and align data
        if isinstance(il.alignment, KeyPointAlignment):
            self.model.align_by = AlignBy.KeyPoints
        elif isinstance(il.alignment, RectAlignment):
            self.model.ra.load(self.project)
            self.model.align_by = AlignBy.Dimensions

        # Dialog is two areas, the view, and the controls for the view
        hlayout = QtWidgets.QHBoxLayout()
        self.setLayout(hlayout)

        view_layout = QtWidgets.QVBoxLayout()

        self.view_tabs = QtWidgets.QTabBar()
        self.view_tabs.currentChanged.connect(self.set_view_type)

        self.update_tabs()

        view_layout.addWidget(self.view_tabs)

        self.view: AlignmentViewWidget = AlignmentViewWidget(self.vis_model, self.il, self.model)

        self.ra_id = RectAlignmentControllerView(self, self.model)
        self.kp_id = KeypointAlignmentControllerView(self, self.model)

        self.view.overlays.add(self.ra_id)
        self.view.overlays.add(self.kp_id)

        view_layout.addWidget(self.view, 1)
        self.directions_label = QtWidgets.QLabel("")
        view_layout.addWidget(self.directions_label, 0)
        hlayout.addLayout(view_layout, 1)

        # Align Controls
        control_layout = QtWidgets.QFormLayout()

        rect_align_controls = RectAlignSettingsWidget(self, self.model.ra)
        keypoint_align_controls = KeypointAlignmentWidget(self, self.model.kp)

        # Alignment selection
        self.align_selection = QtWidgets.QComboBox()
        self.align_selection.addItem("Perimeter + Dimensions")
        self.align_selection.addItem("Keypoints")
        self.align_selection.activated.connect(self.align_selection_cb_changed)
        control_layout.addRow("Align By:", self.align_selection)

        # And the widget stack to drive that
        stack_widget = QtWidgets.QWidget()
        self.stacked_layout = QtWidgets.QStackedLayout(stack_widget)
        self.stacked_layout.addWidget(rect_align_controls)
        self.stacked_layout.addWidget(keypoint_align_controls)

        # right pane layout
        control_buttons_layout = QtWidgets.QVBoxLayout()
        control_buttons_layout.addLayout(control_layout)
        control_buttons_layout.addWidget(stack_widget)

        # Visbox
        vis_gb = QtWidgets.QGroupBox("Visible Layers")

        self.vis_widget = VisibilityTree(self.vis_model)
        vis_gb_layout = QtWidgets.QVBoxLayout()
        vis_gb.setLayout(vis_gb_layout)
        vis_gb_layout.addWidget(self.vis_widget)
        control_buttons_layout.addWidget(vis_gb)

        bbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        control_buttons_layout.addWidget(bbox)
        hlayout.addLayout(control_buttons_layout, 0)

        # Explicitly disconnect child-events for the rect-align model
        # We (mostly) don't care about changes to the perimeter
        self.model.register_notify(self.view.update)
        self.model.register_notify(self.update_controls)

        self.vis_model.changed.connect(self.view.update)

        self._selected_view: Optional[int] = None

        self._saved_transforms = [
            scale(0.8), scale(0.8)
        ]

        # Undo stack
        self.undoStack : UndoStack = UndoStack()
        self.undoStack.setup_actions(self)

        self.update_controls()

    def visMakeLeaf(self, il: ImageLayer) -> VisibilityModelLeaf:
        l = VisibilityModelLeaf(il.name, obj=il)
        return l

    def buildVisibilityModel(self) -> None:
        self.vis_model = VisibilityModelRoot()

        # Add all layers in the project to the visModel. If this layer is visible, put it at the top
        g = VisibilityModelGroup("Current")
        self.vis_model.addChild(g)
        l = self.visMakeLeaf(self.il)
        g.addChild(l)

        unassigned_ils = set(self.project.imagery.imagelayers)
        # Add stackup groups
        for sl in self.project.stackup.layers:
            g = VisibilityModelGroup(sl.name)

            for il in sl.imagelayers:
                unassigned_ils.discard(il)

                if il is not self.il:
                    l = self.visMakeLeaf(il)
                    g.addChild(l)

            self.vis_model.addChild(g)

        g = VisibilityModelGroup("Unassigned")
        for il in unassigned_ils:
            if il is not self.il:
                l = self.visMakeLeaf(il)
                g.addChild(l)

        self.vis_model.addChild(g)

        self.vis_model.propagate_root()

    def update_tabs(self) -> None:
        self.view_tabs.blockSignals(True)
        for i in range(self.view_tabs.count() - 1, -1, -1):
            self.view_tabs.removeTab(i)

        self.view_tabs.addTab("Unaligned (image)")
        self.view_tabs.addTab("Aligned (world)")
        self.view_tabs.blockSignals(False)

    def accept(self) -> None:
        if self.model.align_by == AlignBy.Dimensions:
            self.model.ra.save(self.project)
        else:
            self.model.kp.save(self.project)

        super(LayerAlignmentDialog, self).accept()

    def align_selection_cb_changed(self, idx: int) -> None:
        cmd = cmd_set_align_by(self, AlignBy(idx))
        self.undoStack.push(cmd)

    def set_align_by(self, idx: int) -> None:
        self.model.align_by = AlignBy(idx)
        self.model.view_mode = ViewMode(0)
        self.update_tabs()

        if self.model.align_by == AlignBy.Dimensions:
            self.directions_label.setText("Ctrl-click to add anchor point, Shift-click to delete anchor point.\n" +
                                          "Anchor points constrain handle movement.")
        else:
            self.directions_label.setText("Ctrl-click to add keypoint. Shift-click to delete keypoint.")

    def set_view_type(self, idx: int) -> None:
        self.model.view_mode = ViewMode(idx)

    def save_restore_transform(self) -> None:
        if self._selected_view is not None:
            self._saved_transforms[self._selected_view] = self.view.viewState.transform

        self._selected_view = idx = self.model.view_mode.value
        self.view.viewState.transform = self._saved_transforms[idx]

    def update_controls(self) -> None:

        self.save_restore_transform()

        self.align_selection.setCurrentIndex(self.model.align_by.value)
        self.stacked_layout.setCurrentIndex(self.model.align_by.value)

        if self.model.align_by == AlignBy.Dimensions:
            self.view.setInteractionDelegate(self.ra_id)
            self.view.active_overlays = set([self.ra_id])
        else:
            self.view.setInteractionDelegate(self.kp_id)
            self.view.active_overlays = set([self.kp_id])

        self.view_tabs.setCurrentIndex(self.model.view_mode.value)
