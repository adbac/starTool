import math

import ezui
from fontTools.misc.transform import DecomposedTransform, Identity
from fontTools.pens.pointPen import ReverseContourPointPen
from mojo.events import BaseEventTool, installTool
from mojo.extensions import ExtensionBundle
from mojo.UI import CurrentGlyphWindow


# collecting image data for building cursors and toolbar icons

shapeBundle = ExtensionBundle("StarTool")
_cursorStar = CreateCursor(shapeBundle.get("cursorStar"), hotSpot=(6, 6))

toolbarIcon = shapeBundle.get("toolbarIcon")


class StarShapeSheet(ezui.WindowController):
    """
    The sheet that allows numbers input to draw star shapes.
    """

    def build(self, parent, glyph, callback, x, y):
        self.glyph = glyph
        self.callback = callback

        content = """
        * HorizontalStack @smallFormsContainer
        > * TwoColumnForm @originForm
        >> : x
        >> [__] @xOrigin
        >> : y
        >> [__] @yOrigin
        > * TwoColumnForm @sizeForm
        >> : w
        >> [__] @width
        >> : h
        >> [__] @height
        * TwoColumnForm @starPropertiesForm
        > : Points
        > [__] @points
        > : Inner radius
        > [__] % @innerRadius
        ====================
        (Cancel) @cancelButton
        (OK) @okButton
        """

        integerInput = dict(
            valueType="integer",
            valueWidth=46,
            valueIncrement=1,
        )
        integerInputPositive = integerInput.copy()
        integerInputPositive.update(dict(
            minValue=0,
        ))

        smallForm = dict(
            titleColumnWidth=10,
            itemColumnWidth=integerInput["valueWidth"],
            width="fit",
        )

        descriptionData = dict(
            originForm = smallForm,
            sizeForm = smallForm,
            starPropertiesForm = dict(
                titleColumnWidth=80,
                itemColumnWidth=integerInput["valueWidth"] + 20,
            ),
            cancelButton = dict(
                keyEquivalent=chr(27),
            ),
            xOrigin = integerInput.copy(),
            yOrigin = integerInput.copy(),
            width = integerInputPositive.copy(),
            height = integerInputPositive.copy(),
            points = integerInputPositive.copy(),
            innerRadius = integerInputPositive.copy(),
        )

        descriptionData["xOrigin"]["value"] = x
        descriptionData["yOrigin"]["value"] = y

        self.w = ezui.EZSheet(
            content=content,
            descriptionData=descriptionData,
            parent=parent,
            controller=self,
            defaultButton="okButton"
        )

    def started(self):
        self.w.open()

    def okButtonCallback(self, sender):
        # draw the shape in the glyph
        # try to get some integers from the input fields
        try:
            x = int(self.w.getItem("xOrigin").get())
            y = int(self.w.getItem("yOrigin").get())
            w = int(self.w.getItem("width").get())
            h = int(self.w.getItem("height").get())
            nbPoints = int(self.w.getItem("points").get())
            innerRadius = int(self.w.getItem("innerRadius").get())
        # if this fails just do nothing and print a tiny traceback
        except Exception:
            print("A number is required!")
            return
        # draw the shape with the callback given on init
        self.callback((x, y, w, h), nbPoints, innerRadius, self.glyph)

    def cancelButtonCallback(self, sender):
        # close the window
        self.w.close()


def _roundPoint(x, y):
    return int(round(x)), int(round(y))


class StarTool(BaseEventTool):

    strokeColor = (1, 0, 0, 1)
    reversedStrokColor = (0, 0, 1, 1)

    def setup(self):
        # setup is called when the tool becomes active
        # use this to initialize some attributes
        self.minPoint = None
        self.maxPoint = None
        self.origin = "corner"
        self.moveShapeShift = None
        self.shouldReverse = False
        self.shouldUseCubic = True
        self.nbPoints = 5
        self.innerRadius = 50

        drawingLayer = self.extensionContainer("com.adbac.starToolBeta")
        self.pathLayer = drawingLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=self.strokeColor,
            strokeWidth=-1
        )
        self.originLayer = drawingLayer.appendSymbolSublayer(
            visible=False,
            imageSettings=dict(
                name="star",
                pointCount=8,
                inner=0.1,
                outer=1,
                size=(15, 15),
                fillColor=self.strokeColor
            )
        )

    def getRect(self):
        # return the rect between mouse down and mouse up
        x = self.minPoint.x
        y = self.minPoint.y
        w = self.maxPoint.x - self.minPoint.x
        h = self.maxPoint.y - self.minPoint.y

        # handle the shift down and equalize width and height
        if self.shiftDown:
            sign = 1
            if abs(w) > abs(h):
                if h < 0:
                    sign = -1
                h = abs(w) * sign
            else:
                if w < 0:
                    sign = -1
                w = abs(h) * sign

        if self.origin == "center":
            # if the origin is centered, subtract the width and height
            x -= w
            y -= h
            w *= 2
            h *= 2

        # optimize the rectangle so that width and height are always positive numbers
        if w < 0:
            w = abs(w)
            x -= w
        if h < 0:
            h = abs(h)
            y -= h

        return x, y, w, h

    def getStarPoints(self, rect, nbPoints, innerRadius):
        points = []

        x, y, w, h = rect

        if w != h:
            minSide = min(w, h)
            outerRadius = minSide / 2
            transformation = DecomposedTransform(scaleX = 1 if minSide == w else w / h if h != 0 else w, scaleY = 1 if minSide == h else h / w if w != 0 else h, tCenterX = x + w/2, tCenterY = y + h/2).toTransform()
        else:
            transformation = Identity
            outerRadius = w / 2

        innerRadius = outerRadius * (innerRadius / 100)

        # Calculate coordinates of the points on the inner and outer circle
        points_x_inner = []
        points_y_inner = []
        points_x_outer = []
        points_y_outer = []

        # draw a star in the glyph using the pen
        for i in range(nbPoints):
            angle = 2 * math.pi * i / nbPoints
            points_x_inner.append(innerRadius * math.cos(angle) + x + w/2)
            points_y_inner.append(innerRadius * math.sin(angle) + y + h/2)
            angle2 = angle + math.pi / nbPoints
            points_x_outer.append(outerRadius * math.cos(angle2) + x + w/2)
            points_y_outer.append(outerRadius * math.sin(angle2) + y + h/2)

        for x_in, y_in, x_out, y_out in zip(points_x_inner, points_y_inner, points_x_outer, points_y_outer):
            points.append(_roundPoint(*transformation.transformPoint((x_in, y_in))))
            points.append(_roundPoint(*transformation.transformPoint((x_out, y_out))))

        return points

    def drawStarWithRectInGlyph(self, rect, nbPoints, innerRadius, glyph):
        # draw the shape into the glyph
        # tell the glyph something is going to happen (undo is going to be prepared)
        glyph.prepareUndo("Drawing Star")

        # get the pen to draw with
        pen = glyph.getPointPen()

        if self.shouldReverse:
            pen = ReverseContourPointPen(pen)

        points = self.getStarPoints(rect, nbPoints, innerRadius)

        pen.beginPath()
        for p in points:
            pen.addPoint(p, "line")
        pen.endPath()

        # tell the glyph you are done with your actions so it can handle the undo properly
        glyph.performUndo()
        glyph.changed()

    def mouseDown(self, point, clickCount):
        # a mouse down, only save the mouse down point
        self.minPoint = point
        # on double click, pop up a dialog with input fields
        if clickCount == 2:
            # create and open dialog
            StarShapeSheet(
                CurrentGlyphWindow(currentFontOnly=True).w,
                self.getGlyph(),
                callback=self.drawStarWithRectInGlyph,
                x=self.minPoint.x,
                y=self.minPoint.y,
            )

    def mouseDragged(self, point, delta):
        # record the dragging point
        self.maxPoint = point
        # if shift the minPoint by the move shift
        if self.moveShapeShift:
            w, h = self.moveShapeShift
            self.minPoint.x = self.maxPoint.x - w
            self.minPoint.y = self.maxPoint.y - h
        # update layer
        self.updateLayer()

    def mouseUp(self, point):
        # mouse up, if you have recorded the rect draw that into the glyph
        if self.minPoint and self.maxPoint:
            self.drawStarWithRectInGlyph(self.getRect(), self.nbPoints, self.innerRadius, self.getGlyph())
        # reset the tool
        self.minPoint = None
        self.maxPoint = None
        # update layer
        self.updateLayer()

    def keyDown(self, event):
        # reverse on tab
        if event.characters() == "\t":
            self.shouldReverse = not self.shouldReverse
            if self.shouldReverse:
                self.pathLayer.setStrokeColor(self.reversedStrokColor)

                settings = self.originLayer.getImageSettings()
                settings["fillColor"] = self.reversedStrokColor
                self.originLayer.setImageSettings(settings)
            else:
                self.pathLayer.setStrokeColor(self.strokeColor)

                settings = self.originLayer.getImageSettings()
                settings["fillColor"] = self.strokeColor
                self.originLayer.setImageSettings(settings)
        # number of points +1 when up is down
        if self.arrowKeysDown["up"]:
            self.nbPoints += 1
        # number of points -1 when down is down
        if self.arrowKeysDown["down"]:
            self.nbPoints = self.nbPoints - 1 if self.nbPoints > 2 else 2
        # inner radius -1 when left is down
        if self.arrowKeysDown["left"]:
            self.innerRadius = self.innerRadius - 1 if self.innerRadius > 2 else 2
        # inner radius +1 when right is down
        if self.arrowKeysDown["right"]:
            self.innerRadius += 1
        # update layer
        if self.arrowKeysDown:
            self.updateLayer()

    def modifiersChanged(self):
        # is being called with modifiers changed (shift, alt, control, command)
        self.origin = "corner"

        # change the origin when command is down
        if self.commandDown:
            self.origin = "center"
        # change cubic <-> quad when caps lock is down
        self.shouldUseCubic = not self.capLockDown
        if self.shouldUseCubic:
            self.pathLayer.setStrokeDash(None)
        else:
            self.pathLayer.setStrokeDash([5, 3])
        # record the current size of the shape and store it
        if self.controlDown and self.moveShapeShift is None and self.minPoint and self.maxPoint:
            w = self.maxPoint.x - self.minPoint.x
            h = self.maxPoint.y - self.minPoint.y
            self.moveShapeShift = w, h
        else:
            self.moveShapeShift = None
        # update layer
        self.updateLayer()

    def updateLayer(self):
        # update the layers with a new path and position for the origing point
        if self.isDragging() and self.minPoint and self.maxPoint:
            x, y, w, h = self.getRect()
            pen = self.pathLayer.getPen()

            points = self.getStarPoints((x, y, w, h), self.nbPoints, self.innerRadius)

            pen.moveTo(points[0])
            for p in points:
                pen.lineTo(p)
            pen.closePath()

            if self.origin == "center":
                self.originLayer.setPosition((x + w / 2, y + h / 2))
                self.originLayer.setVisible(True)
            else:
                self.originLayer.setVisible(False)
        else:
            self.pathLayer.setPath(None)
            self.originLayer.setVisible(False)

    def getDefaultCursor(self):
        # returns the cursor
        return _cursorStar

    def getToolbarIcon(self):
        # return the toolbar icon
        return toolbarIcon

    def getToolbarTip(self):
        # return the toolbar tool tip
        return "Star Tool"


# install the tool!!
installTool(StarTool())
