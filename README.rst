xfcs
=======
Extract metadata and data from FCS 3.0/3.1 files.
Data extraction supports file formats:
    - Mode: List (L)
    - Datatypes: I, F, D

Implemented parameter data set options:
    - raw
    - channel values
    - scale values (log10, gain)
    - channel and scale combined into one data set
    - fluorescence compensation
    - log10 scaled fluorescence compensation


Installation
------------

::

    python setup.py install

Command Line Usage
------------------

See
`USAGE <https://github.com/j4c0bs/xfcs/blob/master/docs/usage.md>`_
for expanded details.

To see a list of available commands and arguments, run ''xfcsdata --help'' or ''xfcsmeta --help''

::

    extract data: xfcsdata [options]
    extract metadata: xfcsmeta [options]

Requirements
------------

- Python 3.5 or greater
- numpy
- pandas

License
-------

xfcs is released under the BSD 2-clause license. See
`LICENSE <https://raw.githubusercontent.com/j4c0bs/xfcs/master/LICENSE.txt>`_
for details.