import io
import pathlib
import unittest
import sys

sys.path.append(
    "./src"
)
from shalector.shalector import Shalector



class ShalectorTest(unittest.TestCase):

    def test_group(self):
        output = io.BytesIO()

        Shalector().run([
            "./test1.svg",
            "--id=selector"
        ], output)

        print(output.getvalue().decode())
        # TODO: test that a group is present with the right ID, and the elements in the group

    def test_class(self):
        output = io.BytesIO()

        Shalector().run([
            "./test1.svg",
            "--id=selector",
            "--selection-method=class"
        ], output)

        print(output.getvalue().decode())
        # TODO: test that elements has the right class, and the class is added in the stylesheet
