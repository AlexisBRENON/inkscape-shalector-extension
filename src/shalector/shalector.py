import argparse
import pathlib
import typing
import sys

import inkex
from inkex import elements

from typing import TYPE_CHECKING

try:
    import shapely
except ImportError:
    extension_prefix = pathlib.Path(__file__).parent / "3rdparty"
    sys.path.append(
        str(
            extension_prefix
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
    )
    try:
        import shapely
    except ImportError:
        inkex.debug(
            f"Shapely not available. Trying to install it to {extension_prefix}"
        )
        import subprocess

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "--no-cache-dir",
                "install",
                "--prefer-binary",
                "--prefix",
                extension_prefix,
                "shapely",
            ]
        )
        import shapely

        inkex.debug("Shapely successfully installed")


def get_bbox_polygon(element: elements.ShapeElement) -> shapely.Polygon:
    ebb = element.bounding_box()
    if ebb is None:
        raise ValueError(element, element.get_id())
    return shapely.Polygon.from_bounds(ebb.left, ebb.top, ebb.right, ebb.bottom)


def get_shape_polygon(element: elements.ShapeElement) -> shapely.Polygon:
    if element.tag_name == "path":
        element_transform = element.composed_transform()
        return shapely.Polygon(
            [element_transform.apply_to_point(p) for p in element.path.control_points]
        )
    # TODO: Add logic for rect, use, etc.
    inkex.utils.debug(
        f"Warning: the element {element.get_id()} is not a path. Falling back on BBox polygon"
    )
    return get_bbox_polygon(element)


class Shalector(inkex.EffectExtension):
    def __init__(self):
        super().__init__()
        self._selector_element = None
        self._selector_bbox = None
        self._selector_polygon = None

    def add_arguments(self, pars: argparse.ArgumentParser):
        pars.add_argument(
            "--shalector_notebook",
        )
        pars.add_argument(
            "--selector-mode", default="covering", choices=("covering", "intersecting")
        )
        pars.add_argument(
            "--selectable-mode", default="bbox", choices=("bbox", "shape")
        )
        pars.add_argument(
            "--selection-method", default="group", choices=("group", "class")
        )

    def _should_select(self, element: elements.ShapeElement) -> bool:
        shapely.prepare(self.selector_polygon)

        if self.options.selectable_mode == "bbox":
            ebb = get_bbox_polygon(element)
            predicate = (
                self.selector_polygon.covers if self.options.selector_mode == "covering"
                else self.selector_polygon.intersects
            )
            return predicate(ebb)

        elif self.options.selector_mode == "interecting" and self.options.selectable_mode == "shape":
            return (
                self.selector_polygon.intersects(get_bbox_polygon(element)) and
                self.selector_polygon.intersects(get_shape_polygon(element))
            )
        elif self.options.selector_mode == "covering" and self.options.selectable_mode == "shape":
            return (
                self.selector_polygon.covers(get_bbox_polygon(element)) or (
                    self.selector_polygon.intersects(get_bbox_polygon(element)) and
                    self.selector_polygon.covers(get_shape_polygon(element))
                )
            )
        raise inkex.AbortExtension("Unknown selector mode")

    def _group_selection(self, selection: typing.Sequence[elements.BaseElement]):
        # Build a group to store all the selected elements
        selection_group = inkex.elements.Group(
            *selection, attrib=dict(id=f"{self.selector_element.get_id()}_selection")
        )
        selector_ancestor = self.selector_element.ancestors().first()
        if selector_ancestor is None:
            inkex.errormsg("Unable to get selector ancestor")
            raise inkex.AbortExtension()
        selector_ancestor.add(selection_group)

    def _class_selection(self, selection: typing.Sequence[elements.BaseElement]):
        class_name = f"{self.selector_element.get_id()}_selection"

        self.svg.stylesheet.add(f".{class_name}", {})

        for elem in selection:
            elem_classes = inkex.styles.Classes(elem.attrib.get("class"))
            elem_classes.append(class_name)
            elem.attrib["class"] = " ".join(elem_classes)

    @property
    def selector_element(self) -> elements.ShapeElement:
        if self._selector_element is None:
            if len(self.svg.selection) != 1:
                inkex.errormsg("Select a single shape to use as selector")
                raise inkex.AbortExtension
            selector_element: elements.BaseElement = self.svg.selection.first()
            if not isinstance(selector_element, elements.ShapeElement):
                inkex.errormsg("Selected element must be a path")
                raise inkex.AbortExtension()
            self._selector_element = selector_element
        return self._selector_element

    @property
    def selector_bbox(self) -> inkex.transforms.BoundingBox:
        if self._selector_bbox is None:
            selector_bb = self.selector_element.bounding_box()
            if selector_bb is None:
                inkex.errormsg("Unable to get selector bounding box")
                raise inkex.AbortExtension()
            self._selector_bbox = selector_bb
        return self._selector_bbox

    @property
    def selector_polygon(self) -> shapely.Polygon:
        if self._selector_polygon is None:
            selector_transform = self.selector_element.composed_transform()
            self._selector_polygon = shapely.Polygon(
                [
                    selector_transform.apply_to_point(p)
                    for p in self.selector_element.path.control_points
                ]
            )
        return self._selector_polygon

    def effect(self):
        # Get all sibling objects matching criterion
        selection_list = [
            e
            for e in iter(
                typing.cast(
                    typing.Iterable[elements.BaseElement],
                    self.selector_element.ancestors().first(),
                )
            )
            if (
                e != self.selector_element  # Should not be the selector object
                and isinstance(e, elements.ShapeElement)  # Should be visible
                and self._should_select(e)  # Is the element valid for the selection
            )
        ]
        self.debug(f"Polygon selection: {[e.get_id() for e in selection_list]}")

        if self.options.selection_method == "class":
            self._class_selection(selection_list)
        else:
            self._group_selection(selection_list)

        self.selector_element.delete()
        return True


if __name__ == "__main__":
    Shalector().run()
