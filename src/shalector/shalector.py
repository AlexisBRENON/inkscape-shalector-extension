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


def get_bbox_polygon(ebb: inkex.transforms.BoundingBox) -> shapely.Polygon:
    return shapely.Polygon.from_bounds(ebb.left, ebb.top, ebb.right, ebb.bottom)


class Shalector(inkex.EffectExtension):
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

    def _should_select(
        self, selector_polygon: "shapely.Polygon", element: elements.ShapeElement
    ) -> bool:
        if self.options.selectable_mode == "shape" and element.tag_name == "path":
            # TODO: maybe try the BBox based predicate before doing complicated computation to get the actual path
            # This would:
            #   1. Avoid too much warnings for all non-path objects with bounding box not validating predicate
            #   2. Speed up process (warning: not covering bbox does not mean we not cover the shape)
            element_transform = element.composed_transform()
            element_polygon = shapely.Polygon(
                [
                    element_transform.apply_to_point(p)
                    for p in element.path.control_points
                ]
            )
        else:
            if self.options.selectable_mode != "bbox":
                self.debug(
                    f"Warning: the element {element.get_id()} is not a path. Falling back on BBox selection"
                )
            ebb = element.bounding_box()
            if ebb is None:
                return False
            element_polygon = get_bbox_polygon(ebb)

        predicate = selector_polygon.covers
        if self.options.selector_mode == "intersecting":
            predicate = selector_polygon.intersects

        return predicate(element_polygon)

    def effect(self):
        if len(self.svg.selection) != 1:
            inkex.errormsg("Select a single shape to use as selector")
            raise inkex.AbortExtension

        selector_element: elements.BaseElement = self.svg.selection.first()
        # self.debug(f"Using element '{selector_element.get_id()}({selector_element})'")

        if not isinstance(selector_element, elements.ShapeElement):
            inkex.errormsg("Selected element must be a path")
            raise inkex.AbortExtension()

        selector_bb = selector_element.bounding_box()
        if selector_bb is None:
            inkex.errormsg("Unable to get selector bounding box")
            raise inkex.AbortExtension()

        selector_transform = selector_element.composed_transform()
        selector_polygon = shapely.Polygon(
            [
                selector_transform.apply_to_point(p)
                for p in selector_element.path.control_points
            ]
        )

        # Get all sibling objects matching criterion
        selection_list = [
            e
            for e in iter(
                typing.cast(
                    typing.Iterable[elements.BaseElement],
                    selector_element.ancestors().first(),
                )
            )
            if (
                e.get_id()
                != selector_element.get_id()  # Should not be the selector object
                and isinstance(e, elements.ShapeElement)  # Should be visible
                and self._should_select(
                    selector_polygon, e
                )  # Is the element valid for the selection
            )
        ]
        self.debug(f"Polygon selection: {[e.get_id() for e in selection_list]}")

        # Build a group to store all the selected elements
        selection_group = inkex.elements.Group(
            *selection_list, attrib=dict(id=f"{selector_element.get_id()}_selection")
        )
        selector_ancestor = selector_element.ancestors().first()
        if selector_ancestor is None:
            inkex.errormsg("Unable to get selector ancestor")
            raise inkex.AbortExtension()
        selector_ancestor.add(selection_group)
        selector_element.delete()
        return True


if __name__ == "__main__":
    Shalector().run()
