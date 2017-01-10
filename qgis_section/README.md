# Section viewing and editing


This plugin provides mapcanvases to view and edit layers in the third dimension

Linestrings on the standard xy QGIS canvas are used to define the section. Features within a given distance are projected on the section and can be edited. Edited features are snapped to the section "plane".

## Quick dev install

Clone the repo in a `qgis_section` directory. Add the directory containing `qgis_section` to your PYTHONPATH environment variable.

```sh
export PYTHONPATH=$PWD/..
```

Install plugin:
```sh
python -m qgis_section.package -i
```

Run tests and build the doc (in `docs/build/html/index.html`):
```sh
python -m qgis_section.test
```


