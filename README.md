Build 3D geological model from wells information
################################################

This plugin provides tools to create 3D geological models in QGIS.

**Note** 
  - The created layers are memory layers, the data are not saved, you should use the "save as" qgis function if you plan to store the layer as a shapefile or spatialite layer, you can also cpy/paste the layer feature in a postgis layer that has the right structure. This is intended to maximize flexibility of the source data format.

Quick dev install
=================

You have to install the following dependencies:

  - OpenGL for Python (python-opengl)
  - QtOpenGL for Python (python-qt4-gl)
  - shapely
  - pytest, hypothesis and mock (for running tests only)

Clone the repo in a `albion` directory. Add the directory containing `albion` to your PYTHONPATH environment variable.

```sh
export PYTHONPATH=$PWD/..
```

Install plugin:
```sh
python -m albion.package -i
```

Run tests and build the doc (in `docs/build/html/index.html`):
```sh
python -m albion.test
```


