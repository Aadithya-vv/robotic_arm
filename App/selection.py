"""Interactive movable crop selection for the perception preview."""


class CropSelection:
    def __init__(self, canvas, scale_provider):
        self.canvas = canvas
        self.scale_provider = scale_provider
        self.start = None
        self.rectangle = None
        self.coords = None
        canvas.bind("<Button-1>", self._start)
        canvas.bind("<B1-Motion>", self._drag)
        canvas.bind("<ButtonRelease-1>", self._finish)
        canvas.bind("<Key>", self._key)

    def _start(self, event):
        self.canvas.focus_set(); self.start = (event.x, event.y)
        if self.rectangle: self.canvas.delete(self.rectangle)
        self.rectangle = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#fdb022", width=2, dash=(4, 2))

    def _drag(self, event):
        if self.start and self.rectangle: self.canvas.coords(self.rectangle, self.start[0], self.start[1], event.x, event.y)

    def _finish(self, event):
        if not self.start: return
        self.coords = (min(self.start[0], event.x), min(self.start[1], event.y), max(self.start[0], event.x), max(self.start[1], event.y))

    def _key(self, event):
        if not self.coords or event.keysym not in ("Left", "Right", "Up", "Down"): return
        dx = -2 if event.keysym == "Left" else 2 if event.keysym == "Right" else 0
        dy = -2 if event.keysym == "Up" else 2 if event.keysym == "Down" else 0
        self.coords = tuple(value + (dx if index % 2 == 0 else dy) for index, value in enumerate(self.coords))
        self.canvas.coords(self.rectangle, *self.coords)

    def image_region(self):
        if not self.coords: return None
        scale, offset_x, offset_y, width, height = self.scale_provider()
        x1, y1, x2, y2 = self.coords
        x = max(0, min(width - 1, int((x1 - offset_x) / scale)))
        y = max(0, min(height - 1, int((y1 - offset_y) / scale)))
        right = max(x + 1, min(width, int((x2 - offset_x) / scale)))
        bottom = max(y + 1, min(height, int((y2 - offset_y) / scale)))
        return {"x": x, "y": y, "width": right - x, "height": bottom - y}

    def clear(self):
        if self.rectangle: self.canvas.delete(self.rectangle)
        self.start = self.rectangle = self.coords = None
