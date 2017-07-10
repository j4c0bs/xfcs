#!/usr/bin/env python3

"""
FCS3.0 http://murphylab.web.cmu.edu/FCSAPI/FCS3.html
FCS3.1
A data set is a (HEADER, TEXT, DATA) group. Multiple data sets in one file is deprecated.
"""

import sys
from .DataSection import DataSection
from .Metadata import Metadata
# ------------------------------------------------------------------------------
def filter_numeric(s):
    """If the given string is numeric, return a numeric value for it"""

    if s.isnumeric():
        return int(s)
    else:
        try:
            fval = float(s)
            return fval
        except ValueError:
            return s


def filter_ascii32(s):
    """If string is repetition of '20', return 0 else convert to int"""

    x = set(s[i*2:i*2+2] for i in range(len(s)//2))
    tset = set(['20'])
    if x == tset:
        return 0
    else:
        return int(s,16)


def text_dict(tokens):
    """Makes a dict of fcs text section parameter keys, values"""

    keys_vals = zip(tokens[::2], tokens[1::2])
    return {key.strip():filter_numeric(val.strip()) for key, val in keys_vals}


# ------------------------------------------------------------------------------
class FCSFile(object):
    def __init__(self):
        """Initialize an FCSFile object"""
        self.version = None
        self.header = None
        self.text = {}
        self.all_keys = None
        self.__key_set = {}
        self.supp_text = None
        self.data_hex_bytes = None
        self.analysis = None
        self.metadata = None
        self.data = None
        self.datasection = None

    def load(self, f):
        """Load an FCS file

        Arg:
            f: A file descriptor or filepath to fcs file
        Returns:
            f: A file descriptor
        Raises:
            NotImplementedError: if fcs file format version is not supported
        """

        if isinstance(f, str):
            f = open(f, 'rb')

        self.name = f.name
        version_id = f.read(6).decode("utf-8")

        if version_id in ('FCS3.0', 'FCS3.1'):
            self.version = version_id
            self.__load_30(f)
        else:
            raise NotImplementedError("Not able to parse {vid} files".format(vid=version_id))

        return f

    def __load_30(self, f):
        """Load an FCS 3.0 file

        Arg:
            f: A file descriptor
        """

        f.seek(10)
        self.header = {"text_start": int(f.read(8).decode("utf-8")),
                       "text_end": int(f.read(8).decode("utf-8")),
                       "data_start": int(f.read(8).decode("utf-8")),
                       "data_end": int(f.read(8).decode("utf-8")),
                       "analysis_start": filter_ascii32(f.read(8).hex()),
                       "analysis_end": filter_ascii32(f.read(8).hex())}

        # Read the TEXT section
        f.seek(self.header['text_start'])
        text_delimiter = f.read(1).decode("utf-8")
        tokens = f.read(self.header['text_end'] - self.header['text_start']).decode("utf-8").split(text_delimiter)

        self.text = text_dict(tokens)
        # >> change to meta_keys
        self.all_keys = tokens[::2]

        if len(self.all_keys) > len(self.text):
            n = -1 * (len(self.all_keys) - len(self.text))
            self.all_keys = self.all_keys[:n]

        self.__key_set = set(self.all_keys)


    def load_data(self, f):
        if not self.text:
            fcs_obj = self.load(f)

        self.metadata = Metadata(self.text)
        self.__read_data(fcs_obj)
        self.datasection = DataSection(self.data_hex_bytes, self.metadata)
        # >>> change to self.data -> self.datasection.get_data()
        self.df = self.datasection.df
        self.param_attr_log = self.datasection.param_attr_log


    def __read_data(self, f):
        """Read Data Section"""

        if not self.text:
            self.load(f)
        self.metadata = Metadata(self.text)

        data_start, data_end = self.__get_data_seek()
        f.seek(data_start)
        data_nbytes = data_end - data_start
        self.data_hex_bytes = f.read(data_nbytes + 1)
        self.check_file_standards_conformity()
        f.close()


    def __get_data_seek(self):
        header_check_1 = (self.header['data_start'] == int(self.text['$BEGINDATA']))
        header_check_2 = (self.header['data_end'] == int(self.text['$ENDDATA']))

        if header_check_1 and header_check_2:
            data_start = self.header['data_start']
            data_end = self.header['data_end']
        else:
            data_start = int(self.text['$BEGINDATA'])
            data_end = int(self.text['$ENDDATA'])

        return data_start, data_end


    def check_file_standards_conformity(self):
        if not self.metadata.verify_format(len(self.data_hex_bytes)):
            print('ABORTING DATA EXTRACTION')
            sys.exit(0)


    def write_data(self, filetype='csv'):

        if filetype == 'csv':
            fn = self.datasection.store_csv_data(self.name)
        elif filetype == 'hdf5':
            fn = self.datasection.store_hdf5_data(self.name)
        else:
            fn = 'nothing extracted'

        print('Data extracted to: {}'.format(fn))


    def load_from_csv(self, keys_in, param_vals):
        # >>> param_keys, values ? -> self.all_keys = param_keys[:] ?

        for param, value in param_vals.items():
            self.set_param(param, value)
            # self.all_keys.append(param)

        self.all_keys = keys_in[:]
        self.__key_set = set(self.all_keys)


    def has_param(self, key):
        """Return True given parameter is in text section"""
        return (key in self.__key_set)

    def param(self, param):
        """Return the value for the given parameter"""
        return self.text.get(param, 'N/A')

    def numeric_param(self, param):
        """Return the numeric value for the given parameter"""
        return self.text.get(param, 0)

    def set_param(self, param, value):
        """Set the value of the given parameter"""
        if isinstance(value, str) and not value.isalpha():
            value = filter_numeric(value)
        self.text[param] = value

    def write(self, f):
        """Write an FCS file (not implemented)"""
        raise NotImplementedError("Can't write FCS files yet")


# ------------------------------------------------------------------------------
if __name__ == "__main__":

    x = FCSFile()
    x.load(open(sys.argv[1], 'rb'))
    print(x.text)
