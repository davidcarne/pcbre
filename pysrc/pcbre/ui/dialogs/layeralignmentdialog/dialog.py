import OpenGL.GL as GL

from pcbre.matrix import scale, Point2
from pcbre.model.imagelayer import KeyPoint, KeyPointPosition, KeyPointAlignment, RectAlignment
from pcbre.ui.boardviewwidget import BaseViewWidget
from pcbre.ui.dialogs.layeralignmentdialog.keypointalign import KeypointAlignmentModel, KeypointAlignmentControllerView, \
    KeypointAlignmentWidget
from pcbre.ui.dialogs.layeralignmentdialog.rectalign import RectAlignSettingsWidget
from pcbre.ui.dialogs.layeralignmentdialog.visibilitywidget import VisibilityModel, VisibilityModelGroup, \
    VisibilityModelLeaf, VisibilityTree
from pcbre.ui.gl.textrender import TextBatcher
from pcbre.ui.undo import UndoStack, undofunc, sig
from pcbre.view.imageview import ImageView
from pcbre.view.originview import OriginView
from .rectalign import RectAlignmentControllerView, RectAlignmentModel

from qtpy import QtGui, QtCore, QtWidgets
import numpy
from pcbre.ui.uimodel import mdlacc, GenModel

__author__ = 'davidc'

ALIGN_BY_DIMENSIONS = 0
ALIGN_BY_KEYPOINTS = 1

VIEW_MODE_UNALIGNED = 0
VIEW_MODE_ALIGNED = 1

VIEW_MODE_EXISTING_KEYPOINTS = 2


class AlignmentViewModel(GenModel):
    def __init__(self, image):
        GenModel.__init__(self)

        self.ra = RectAlignmentModel(image)
        self.kp = KeypointAlignmentModel(image)

    align_by = mdlacc(ALIGN_BY_DIMENSIONS)

    view_mode = mdlacc(VIEW_MODE_UNALIGNED)

@undofunc
def cmd_set_align_by(target, align_mode):
    old_state = target.model.align_by
    target.set_align_by(align_mode)
    return sig(old_state)


class AlignmentViewWidget(BaseViewWidget):
    def __init__(self, vis_model, il, model):
        BaseViewWidget.__init__(self)

        self.il = il
        self.iv = ImageView(il)
        self.model = model
        self.vis_model = vis_model

        self.overlays = set()
        self.active_overlays = set()

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.viewState.transform = scale(0.80)

        self.originView = OriginView()

        self.text_batch = TextBatcher(self.gls.text)

    def reinit(self):
        self.iv.initGL(self.gls)
        self.iv_cache = {}

        for ov in self.overlays:
            ov.initializeGL(self.gls)

        self.originView.initializeGL(self.gls)

        self.text_batch.initializeGL()

    def get_iv(self, il):
        if il is self.iv.il:
            return self.iv

        if il not in self.iv_cache:
            iv = ImageView(il)

            iv.initGL(self.gls)

            self.iv_cache[il]  = iv


        return self.iv_cache[il]

    def get_flattened(self, n=None, l=None):
        if l is None:
            l = []

        if n is None:
            n = self.vis_model

        for i in n.children:
            if hasattr(i, "_il_obj") and i.visible:
                l.append(i._il_obj)
            else:
                self.get_flattened(i, l)

        return l

    def render(self):
        self.text_batch.restart()
        GL.glEnable(GL.GL_BLEND)
        if self.model.align_by == ALIGN_BY_DIMENSIONS:
            if self.model.view_mode == VIEW_MODE_UNALIGNED:
                self.iv.mat = numpy.identity(3)
            else:
                self.iv.mat = self.model.ra.image_matrix
        else:
            if self.model.view_mode == VIEW_MODE_UNALIGNED:
                self.iv.mat = numpy.identity(3)
            else:
                self.iv.mat = self.model.kp.image_matrix

        # Render the base image
        if self.model.view_mode == VIEW_MODE_UNALIGNED:
            self.iv.render(self.viewState.glMatrix)
        else:
            # Draw all visible layers bottom to top
            all_ils = list(reversed(self.get_flattened()))

            for il in all_ils:
                iv = self.get_iv(il)
                iv.render(self.viewState.glMatrix)

        for ovl in self.active_overlays:
            ovl.render(self.viewState)


        self.text_batch.render()


    def keyPressEvent(self, evt):
        if self.interactionDelegate:
            self.interactionDelegate.keyPressEvent(evt)

    def focusNextPrevChild(self, next):
        found = False

        if self.interactionDelegate:
            found = self.interactionDelegate.next_prev_child(next)

        if not found:
            return super(AlignmentViewWidget, self).focusNextPrevChild(next)
        return True

    def focusOutEvent(self, evt):
        if self.interactionDelegate:
            self.interactionDelegate.focusOutEvent(evt)


class LayerAlignmentDialog(QtWidgets.QDialog):
    def __init__(self, parent, project, il):
        QtWidgets.QDialog.__init__(self, parent)
        self.resize(800,600)
        self.setSizeGripEnabled(True)

        self.project = project
        self.il = il

        self.model = AlignmentViewModel(self.il)

        # Build the treeView model for layer visibility
        self.buildVisibilityModel()

        # Always align keypoint-based load. Works with unaligned images
        self.model.kp.load(self.project)

        # Keypoint-align, initialize from existing align project and align data
        if isinstance(il.alignment, KeyPointAlignment):
            self.model.align_by = ALIGN_BY_KEYPOINTS
        elif isinstance(il.alignment, RectAlignment):
            self.model.ra.load(self.project)
            self.model.align_by = ALIGN_BY_DIMENSIONS

        # Dialog is two areas, the view, and the controls for the view
        hlayout = QtWidgets.QHBoxLayout()
        self.setLayout(hlayout)

        view_layout = QtWidgets.QVBoxLayout()

        self.view_tabs = QtWidgets.QTabBar()
        self.view_tabs.currentChanged.connect(self.set_view_type)

        self.update_tabs()

        view_layout.addWidget(self.view_tabs)

        self.view = AlignmentViewWidget(self.vis_model, self.il, self.model)


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
        self.stacked_layout = QtWidgets.QStackedLayout()
        self.stacked_layout.addWidget(rect_align_controls)
        self.stacked_layout.addWidget(keypoint_align_controls)



        # right pane layout
        control_buttons_layout = QtWidgets.QVBoxLayout()
        control_buttons_layout.addLayout(control_layout)
        control_buttons_layout.addLayout(self.stacked_layout)

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
        self.model.ra.changed.disconnect(self.model.change)

        self.model.changed.connect(self.view.update)
        self.vis_model.changed.connect(self.view.update)
        self.model.changed.connect(self.update_controls)


        self._selected_view = None

        self._saved_transforms = [
            scale(0.8), scale(0.8)
        ]


        # Undo stack
        self.undoStack = UndoStack()
        self.undoStack.setup_actions(self)

        self.update_controls()

    def visMakeLeaf(self, il):
        l = VisibilityModelLeaf(il.name)
        l._il_obj = il
        return l

    def buildVisibilityModel(self):
        self.vis_model = VisibilityModel()

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

        self.vis_model.propagate_model()

    def update_tabs(self):
        self.view_tabs.blockSignals(True)
        for i in range(self.view_tabs.count() - 1, -1, -1):
            self.view_tabs.removeTab(i)

        self.view_tabs.addTab("Unaligned (image)")
        self.view_tabs.addTab("Aligned (world)")
        self.view_tabs.blockSignals(False)

    def accept(self):
        if self.model.align_by == ALIGN_BY_DIMENSIONS:
            self.model.ra.save(self.project)
        else:
            self.model.kp.save(self.project)

        super(LayerAlignmentDialog, self).accept()

    def align_selection_cb_changed(self, idx):
        cmd = cmd_set_align_by(self, idx)
        self.undoStack.push(cmd)

    def set_align_by(self, idx):
        self.model.align_by = idx
        self.model.view_mode = 0
        self.update_tabs()

        if self.model.align_by == ALIGN_BY_DIMENSIONS:
            self.directions_label.setText("Ctrl-click to add anchor point, Shift-click to delete anchor point.\n" +
                                          "Anchor points constrain handle movement.")
        else:
            self.directions_label.setText("Ctrl-click to add keypoint. Shift-click to delete keypoint.")

    def set_view_type(self, idx):
        self.model.view_mode = idx

    def save_restore_transform(self):
        if self._selected_view is not None:
            self._saved_transforms[self._selected_view] = self.view.viewState.transform

        self._selected_view = self.model.view_mode

        self.view.viewState.transform = self._saved_transforms[self._selected_view]

    def update_controls(self):

        self.save_restore_transform()

        self.align_selection.setCurrentIndex(self.model.align_by)
        self.stacked_layout.setCurrentIndex(self.model.align_by)

        if self.model.align_by == ALIGN_BY_DIMENSIONS:
            self.view.setInteractionDelegate(self.ra_id)
            self.view.active_overlays = set([self.ra_id])
        else:
            self.view.setInteractionDelegate(self.kp_id)
            self.view.active_overlays = set([self.kp_id])

        self.view_tabs.setCurrentIndex(self.model.view_mode)







