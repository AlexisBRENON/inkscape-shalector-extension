import io
import unittest
import sys
import xml.etree.ElementTree as ET

sys.path.append("./src")
from shalector.shalector import Shalector


class ShalectorTest(unittest.TestCase):
    namespaces = {
        "inkscape": "http://www.inkscape.org/namespaces/inkscape",
        "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
        "": "http://www.w3.org/2000/svg",
        "svg": "http://www.w3.org/2000/svg",
    }

    def test_group(self):
        output = io.BytesIO()

        Shalector().run(["./test1.svg", "--id=selector"], output)

        root = ET.fromstring(output.getvalue().decode())
        selection = root.findall(".//g[@id='selector_selection']", self.namespaces)[0]
        self.assertGreater(len(selection), 0)

    def test_class(self):
        output = io.BytesIO()

        Shalector().run(
            ["./test1.svg", "--id=selector", "--selection-method=class"], output
        )

        root = ET.fromstring(output.getvalue().decode())
        selection = root.findall(".//*[@class='selector_selection']", self.namespaces)
        self.assertGreater(len(selection), 0)

    def test_2(self):
        output = io.BytesIO()
        Shalector().run(["./test2.svg", "--id=selector"], output)

        root = ET.fromstring(output.getvalue().decode())
        selection = root.findall(".//g[@id='selector_selection']", self.namespaces)[0]
        self.assertGreater(len(selection), 0)
