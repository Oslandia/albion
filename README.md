# Build 3D geological model from wells information

## What is Albion ?

This [QGIS](http://qgis.org) plugin provides tools to create 3D geological models.

[![Albion : cross-section edition](https://i.vimeocdn.com/video/692568277_600x340.jpg
)](https://vimeo.com/263119265)

Features :
- Edition of Cross-sections (see video above)
- 3D Volume reconstruction from cross-sections
- 3D Volume edition
- 2D Visualization
  - All geological 2D layers
  - Additional GIS data ( orthophotos/satellite, maps, geological maps..)
  - Boreholes
  - Cross sections
- 3D visualization
  - Boreholes
  - Volume

**Note** 
  - The created layers are memory layers, the data are not saved, you should use the "save as" qgis function if you plan to store the layer as a shapefile or spatialite layer, you can also cpy/paste the layer feature in a postgis layer that has the right structure. This is intended to maximize flexibility of the source data format.

## Quick dev install


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

Run tests:
```sh
pytest
```


## Process

- Create project (no caps, no space, no accents in project name)
- Import data directory
- Create the grid (e.g. open an existing shapefile, select all features with Ctrl+a then cpy/paste in the grid layer that has been switched to edition mode)
- Create a graph
- Set graph nodes (e.g. open formation attribute table, select feature by code, cpy/paste into node layer and set the graph_id field of pasted features, use field calculator for that)
- Launch Auto Graph from the Albion menu
- Check graph, you can extend sections to interpolated either section by section of globaly with the Albion menu entry


## Interface

- Albion Menu: 
    - new project (create db and load layers)
    - --
    - import data
    - compute mineralization (adds table and layer)
    - --
    - new graph (create table and views and new layers)
    - clean graph
    - --
    - export project (`pg_dump`)
    - import project (`pg_restore`)

- Albion Toolbar:
    - toggle section/top
    - current graph
    - grid line from points
    - select current section (either on top view, or orthogonal in section view)
    - previous section
    - next section
    - end distance
    - auto-connect
    - auto-wall and ceil 

notes on 3D:
- togle visibility
- dynamic update on changes
