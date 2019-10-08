
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from petri.petri import *
from ui.common import *


class NodeType:
	PLACE = 0
	TRANSITION = 1
	
NodeTypeMap = {
	"place": NodeType.PLACE,
	"transition": NodeType.TRANSITION
}

			
class TransitionFilter(HoverFilter):
	def applyToBrush(self, brush):
		super().applyToBrush(brush)
		if self.item.obj.enabled:
			color = mergeColors(brush.color(), QColor(Qt.green))
			brush.setColor(color)
			

class ArrowFilter(HoverFilter):
	def applyToPen(self, pen):
		super().applyToPen(pen)
		if self.item.isSelected():
			pen.setColor(Qt.blue)


class LabelItem(EditorItem):
	def __init__(self, scene, obj):
		super().__init__(scene)

		self.dragMode = DragMode.SPECIAL

		self.obj = obj
		self.obj.positionChanged.connect(self.updateLabel)
		self.obj.labelChanged.connect(self.updateLabel)
		self.obj.deleted.connect(self.removeFromScene)

		self.font = QFont()
		self.font.setPixelSize(16)
		self.fontMetrics = QFontMetrics(self.font)

		self.updateLabel()
		
	def disconnect(self):
		self.obj.positionChanged.disconnect(self.updateLabel)
		self.obj.labelChanged.disconnect(self.updateLabel)
		self.obj.deleted.disconnect(self.removeFromScene)
		
	def delete(self):
		self.obj.setLabel("")
		self.obj.setLabelAngle(math.pi / 2)
		self.obj.setLabelDistance(35)

	def drag(self, pos):
		dx = pos.x() - self.obj.x
		dy = pos.y() - self.obj.y

		dist = math.sqrt(dx * dx + dy * dy)
		dist = min(max(dist, 20), 60)

		self.obj.setLabelAngle(math.atan2(dy, dx))
		self.obj.setLabelDistance(dist)

	def updateLabel(self):
		xoffs = math.cos(self.obj.labelAngle) * self.obj.labelDistance
		yoffs = math.sin(self.obj.labelAngle) * self.obj.labelDistance
		self.setPos(self.obj.x + xoffs, self.obj.y + yoffs)

		self.prepareGeometryChange()
		self.update()

	def boundingRect(self):
		rect = self.fontMetrics.boundingRect(self.obj.label)
		rect.moveCenter(QPoint(0, 0))
		return QRectF(rect.adjusted(-1, -1, 1, 1))

	def paint(self, painter, option, widget):
		if self.isSelected():
			pen = QPen(Qt.blue)
			painter.setPen(pen)

		painter.setFont(self.font)
		painter.drawText(self.boundingRect(), Qt.AlignCenter, self.obj.label)
			
			
class PlaceNode(ActiveNode):
	def __init__(self, scene, style, obj):
		super().__init__(scene, style.shapes["place"], obj, NodeType.PLACE)
		self.obj.tokensChanged.connect(self.update)
		
		self.font = QFont()
		self.font.setPixelSize(16)
		
	def disconnect(self):
		self.obj.tokensChanged.disconnect(self.update)
	
	def paint(self, painter, option, widget):
		super().paint(painter, option, widget)
		
		if self.obj.tokens != 0:
			text = str(self.obj.tokens)
			painter.setFont(self.font)
			painter.drawText(self.shp.rect, Qt.AlignCenter, text)

			
class TransitionNode(ActiveNode):
	def __init__(self, scene, style, obj):
		super().__init__(scene, style.shapes["transition"], obj, NodeType.TRANSITION)
		self.obj.enabledChanged.connect(self.update)
		self.filter = TransitionFilter(self)
		
	def disconnect(self):
		self.obj.enabledChanged.disconnect(self.update)
		
		
class ArrowType:
	INPUT = 0
	OUTPUT = 1


class ArrowItem(EditorShape):
	def __init__(self, scene):
		super().__init__(scene)
		self.setZValue(-1)

		self.arrow = ShapeElement(
			"arrow", x1=0, y1=0, x2=0, y2=0, stretch=10
		)

		pen = QPen()
		pen.setCapStyle(Qt.RoundCap)
		pen.setWidth(2)

		part = ShapePart()
		part.setPen(pen)
		part.addElement(self.arrow)

		shape = Shape()
		shape.addPart(part)

		self.setShape(shape)

	def setPoints(self, x1, y1, x2, y2):
		self.arrow.x1 = x1
		self.arrow.y1 = y1
		self.arrow.x2 = x2
		self.arrow.y2 = y2
		self.updateShape()


class TemporaryArrow(ArrowItem):
	def __init__(self, scene, source):
		super().__init__(scene)

		self.source = source
		self.setPoints(source.x(), source.y(), source.x(), source.y())

	def drag(self, pos):
		self.setPoints(self.source.x(), self.source.y(), pos.x(), pos.y())


class ActiveArrow(ArrowItem):
	def __init__(self, scene, obj, type):
		super().__init__(scene)

		self.filter = ArrowFilter(self)

		self.type = type

		self.obj = obj
		self.obj.deleted.connect(self.removeFromScene)

		if type == ArrowType.INPUT:
			self.source = self.obj.place
			self.target = self.obj.transition
		else:
			self.source = self.obj.transition
			self.target = self.obj.place

		self.source.positionChanged.connect(self.updateArrow)
		self.target.positionChanged.connect(self.updateArrow)

		self.updateArrow()
		
	def disconnect(self):
		self.obj.deleted.disconnect(self.removeFromScene)
		self.source.positionChanged.disconnect(self.updateArrow)
		self.target.positionChanged.disconnect(self.updateArrow)

	def delete(self):
		self.obj.delete()

	def updateArrow(self):
		dx = self.target.x - self.source.x
		dy = self.target.y - self.source.y
		angle = math.atan2(dy, dx)

		self.setPoints(
			self.source.x + math.cos(angle) * 30,
			self.source.y + math.sin(angle) * 30,
			self.target.x - math.cos(angle) * 30,
			self.target.y - math.sin(angle) * 30
		)
		
		
class EnterpriseController:
	def __init__(self, style, window):
		self.style = style
		
		self.toolbar = window.toolbar
		self.scene = window.scene
		
		self.net = None
		
	def load(self, net):
		self.net = net

	def startPlacement(self, pos):
		type = self.toolbar.currentTool("enterprise")
		if type in NodeTypeMap:
			self.scene.setHoverEnabled(False)
			shape = self.style.shapes[type]
			item = EditorNode(self.scene, shape)
			item.type = NodeTypeMap[type]
			item.drag(pos)
			return item
		elif type == "arrow":
			source = self.scene.findItem(pos, ActiveNode)
			if source:
				return TemporaryArrow(self.scene, source)

	def finishPlacement(self, pos, item):
		if isinstance(item, EditorNode):
			pos = alignToGrid(pos)
			x, y = pos.x(), pos.y()
			
			if not item.invalid:
				if item.type == NodeType.PLACE:
					place = Place(x, y)
					self.net.places.add(place)
				elif item.type == NodeType.TRANSITION:
					trans = Transition(x, y)
					self.net.transitions.add(trans)

		elif isinstance(item, TemporaryArrow):
			source = item.source
			target = self.scene.findItem(pos, ActiveNode)
			if target and target.type != source.type:
				if target.type == NodeType.TRANSITION:
					arrow = Arrow(ArrowType.INPUT, source.obj, target.obj)
					self.net.inputs.add(arrow)
				else:
					arrow = Arrow(ArrowType.OUTPUT, target.obj, source.obj)
					self.net.outputs.add(arrow)

		self.scene.setHoverEnabled(True)
		
		
class GeneralSettings(QWidget):
	def __init__(self, net):
		super().__init__()
		self.setStyleSheet("font-size: 16px")
		
		self.net = net
		self.net.deadlockChanged.connect(self.updateDeadlock)
		
		self.label = QLabel("No item selected")
		self.label.setAlignment(Qt.AlignCenter)
		self.triggerRandom = QPushButton("Trigger random")
		self.triggerRandom.setEnabled(not self.net.deadlock)
		self.triggerRandom.clicked.connect(self.net.triggerRandom)

		self.layout = QVBoxLayout(self)
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.triggerRandom)
		self.layout.setAlignment(Qt.AlignTop)
		
	def cleanup(self):
		self.net.deadlockChanged.disconnect(self.updateDeadlock)

	def setSelection(self, items):
		if len(items) == 0:
			self.label.setText("No item selected")
		elif len(items) == 1:
			self.label.setText("1 item selected")
		else:
			self.label.setText("%i items selected" %len(items))
			
	def updateDeadlock(self):
		self.triggerRandom.setEnabled(not self.net.deadlock)

			
class PlaceSettings(QWidget):
	def __init__(self, obj):
		super().__init__()
		self.obj = obj
		self.obj.positionChanged.connect(self.updatePos)
		self.obj.labelChanged.connect(self.updateLabel)
		self.obj.tokensChanged.connect(self.updateTokens)

		self.setStyleSheet("font-size: 16px")

		self.x = QLabel("%i" %(obj.x / GRID_SIZE))
		self.x.setAlignment(Qt.AlignRight)
		self.y = QLabel("%i" %(obj.y / GRID_SIZE))
		self.y.setAlignment(Qt.AlignRight)
		self.label = QLineEdit(obj.label)
		self.label.setMaxLength(20)
		self.label.textEdited.connect(self.obj.setLabel)
		self.tokens = QSpinBox()
		self.tokens.setRange(0, 999)
		self.tokens.setValue(obj.tokens)
		self.tokens.valueChanged.connect(self.obj.setTokens)

		self.layout = QFormLayout(self)
		self.layout.addRow("X:", self.x)
		self.layout.addRow("Y:", self.y)
		self.layout.addRow("Label:", self.label)
		self.layout.addRow("Tokens:", self.tokens)
		
	def cleanup(self):
		self.obj.positionChanged.disconnect(self.updatePos)
		self.obj.labelChanged.disconnect(self.updateLabel)
		self.obj.tokensChanged.disconnect(self.updateTokens)

	def updatePos(self):
		self.x.setText("%i" %(self.obj.x / GRID_SIZE))
		self.y.setText("%i" %(self.obj.y / GRID_SIZE))

	def updateLabel(self):
		self.label.setText(self.obj.label)
		
	def updateTokens(self):
		self.tokens.setValue(self.obj.tokens)

		
class TransitionSettings(QWidget):
	def __init__(self, obj):
		super().__init__()
		self.obj = obj
		self.obj.positionChanged.connect(self.updatePos)
		self.obj.labelChanged.connect(self.updateLabel)
		self.obj.enabledChanged.connect(self.updateEnabled)

		self.setStyleSheet("font-size: 16px")

		self.x = QLabel("%i" %(obj.x / GRID_SIZE))
		self.x.setAlignment(Qt.AlignRight)
		self.y = QLabel("%i" %(obj.y / GRID_SIZE))
		self.y.setAlignment(Qt.AlignRight)
		self.label = QLineEdit(obj.label)
		self.label.setMaxLength(20)
		self.label.textEdited.connect(self.obj.setLabel)
		self.trigger = QPushButton("Trigger")
		self.trigger.setEnabled(self.obj.enabled)
		self.trigger.clicked.connect(self.obj.trigger)

		self.layout = QFormLayout(self)
		self.layout.addRow("X:", self.x)
		self.layout.addRow("Y:", self.y)
		self.layout.addRow("Label:", self.label)
		self.layout.addRow(self.trigger)
		
	def cleanup(self):
		self.obj.positionChanged.disconnect(self.updatePos)
		self.obj.labelChanged.disconnect(self.updateLabel)
		self.obj.enabledChanged.disconnect(self.updateEnabled)

	def updatePos(self):
		self.x.setText("%i" %(self.obj.x / GRID_SIZE))
		self.y.setText("%i" %(self.obj.y / GRID_SIZE))

	def updateLabel(self):
		self.label.setText(self.obj.label)
		
	def updateEnabled(self):
		self.trigger.setEnabled(self.obj.enabled)
		
		
class EnterpriseScene:
	def __init__(self, style, application):
		self.style = style
		self.application = application
		self.window = window = application.window
		
		self.controller = EnterpriseController(style, window)
		
		self.toolbar = window.toolbar
		self.scene = window.scene
		self.view = window.view
		self.settings = window.settings
		
	def load(self, net):
		self.scene.clear()
		
		self.net = net
		self.net.places.added.connect(self.addPlace)
		self.net.transitions.added.connect(self.addTransition)
		self.net.inputs.added.connect(self.addInput)
		self.net.outputs.added.connect(self.addOutput)
		
		for place in self.net.places:
			self.addPlace(place)
		for transition in self.net.transitions:
			self.addTransition(transition)
		for input in self.net.inputs:
			self.addInput(input)
		for output in self.net.outputs:
			self.addOutput(output)

		self.controller.load(net)
		
		self.scene.setController(self.controller)
		self.scene.selectionChanged.connect(self.updateSelection)
		
		self.view.setHandDrag(False)
		
		self.toolbar.reset()
		self.toolbar.addGroup("common")
		self.toolbar.addGroup("enterprise")
		self.toolbar.selectTool("selection")
		self.toolbar.selectionChanged.connect(self.updateTool)
		
		self.generalSettings = GeneralSettings(self.net)
		self.settings.setWidget(self.generalSettings)
		
	def cleanup(self):
		self.scene.selectionChanged.disconnect(self.updateSelection)
		self.toolbar.selectionChanged.disconnect(self.updateTool)
		
		self.net.places.added.disconnect(self.addPlace)
		self.net.transitions.added.disconnect(self.addTransition)
		self.net.inputs.added.disconnect(self.addInput)
		self.net.outputs.added.disconnect(self.addOutput)
		
		self.generalSettings.cleanup()
		if self.settings.widget() != self.generalSettings:
			self.settings.widget().cleanup()
		self.scene.cleanup()
			
	def addPlace(self, obj):
		item = PlaceNode(self.scene, self.style, obj)
		label = LabelItem(self.scene, obj)
		self.scene.addItem(item)
		self.scene.addItem(label)

	def addTransition(self, obj):
		item = TransitionNode(self.scene, self.style, obj)
		label = LabelItem(self.scene, obj)
		self.scene.addItem(item)
		self.scene.addItem(label)

	def addInput(self, obj):
		item = ActiveArrow(self.scene, obj, ArrowType.INPUT)
		self.scene.addItem(item)

	def addOutput(self, obj):
		item = ActiveArrow(self.scene, obj, ArrowType.OUTPUT)
		self.scene.addItem(item)
		
	def updateSelection(self):
		if self.settings.widget() != self.generalSettings:
			self.settings.widget().cleanup()
		
		items = self.scene.selectedItems()
		widget = self.createSettingsWidget(items)
		self.settings.setWidget(widget)
		
	def createSettingsWidget(self, items):
		filtered = [i for i in items if isinstance(i, ActiveNode)]
		if len(filtered) == 1:
			item = filtered[0]
			if item.type == NodeType.PLACE:
				return PlaceSettings(item.obj)
			return TransitionSettings(item.obj)
		
		self.generalSettings.setSelection(items)
		return self.generalSettings
		
	def updateTool(self, tool):
		if tool == "selection":
			self.view.setHandDrag(False)
		elif tool == "hand":
			self.view.setHandDrag(True)
