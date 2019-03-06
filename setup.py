""" Install autochem
"""
from distutils.core import setup


setup(name="autochem",
      version="0.1.2",
      packages=["automol",
                "automol.constructors",
                "automol.readers",
                "automol.writers",
                "automol.inchi",
                "automol.geom",
                "automol.zmatrix",
                "automol.graph",
                "automol.graph._dict",
                "automol.graph._inchi",
                "automol.graph._stereo",
                "automol.tests",
                "autorxn"],
      package_dir={'automol': "automol"},
      package_data={'automol': ["tests/data/*.txt"]},)