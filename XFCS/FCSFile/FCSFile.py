#!/usr/bin/env python3

"""
    FCS file reader supporting file format spec 3.0, 3.1.
    Data extraction currently supports:
        $MODE: (L) List
        $DATATYPE: I,F,D

    FCS3.0 http://murphylab.web.cmu.edu/FCSAPI/FCS3.html
    FCS3.1 https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2892967/
    A data set is a (HEADER, TEXT, DATA) group.
    Multiple data sets in one file is deprecated.

    2.2.5
    A keyword is the label of a data field. A keyword-value pair is the label of the
    data field with its associated value. Keywords are unique in data sets,
    i.e., there are no multiple instances of the same keyword in the data set.

    Required FCS primary TEXT segment keywords:
    $BEGINANALYSIS $BEGINDATA $BEGINSTEXT $BYTEORD $DATATYPE $ENDANALYSIS
    $ENDDATA $ENDSTEXT $MODE $NEXTDATA $PAR $TOT $PnB $PnE $PnN $PnR
"""

from itertools import chain, compress
import struct

from XFCS.FCSFile.DataSection import DataSection
from XFCS.FCSFile.Metadata import Metadata
from XFCS.FCSFile import validate
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


def filter_ascii32(hex_str):
    """If hex string is repetition of '20', return 0 else convert to int"""

    hex_char_set = set(hex_str[i*2:i*2+2] for i in range(len(hex_str)//2))
    twozero = set(['20'])
    if hex_char_set == twozero:
        return 0
    else:
        return int(hex_str, 16)


# ------------------------------------------------------------------------------
class FCSFile(object):
    """Instantiates an FCSFile object.

    Public Attributes:
        version
        text: dict containing all Parameter metadata key : value
        param_keys: iterable of Parameter keys in order of location in fcs text section

        data_hex_bytes: Complete Data Section read as hex
        metadata
        data ->
        datasection

    Public Methods:
        load: Load an FCS file for reading and confirm version id is supported.
        load_from_csv: Init FCSFile object from csv containing Parameter key, value pairs.
        load_data: Load Data Section for reading
        write_data: Writes data section to csv or hdf5 file.

        check_file_standards_conformity: Confirms metadata format.
        meta_hash: Generates unique fingerprint based on Parameter key, value pairs.

        has_param: Confirm Parameter key in text section.
        param: Retrieve value for given Parameter key.
        numeric_param: Force retrieve numeric value for given Parameter key or 0.
        set_param: Sets value for given Parameter key within self.text.

    """

    def __init__(self):
        """Initialize an FCSFile object.

        Attributes:
            version: version ID for FCS file.
            text: dict of text section metadata Parameter key, value pairs
            param_keys: iterable of Parameter keys in order of location in fcs text section

            data_hex_bytes: Complete Data Section read as hex
            metadata
            data
            datasection

        """

        self.version = None
        self.name = ''
        self.filepath = ''
        self.valid = False
        self.supported_format = False
        self.datatype = ''
        self._fcs = None
        self.__header = None
        self.text = {}
        self.param_keys = None
        self.__key_set = {}
        self.__n_keys = 0
        self.spec = None
        self.__raw_data = None
        self.data = None
        self.__supp_text = None
        self.__analysis = None


    def load(self, fcs_file):
        """Load an FCS file and confirm version id is supported.

            Arg:
                f: A fcs filepath.
            Returns:
                f: A file descriptor
            Raises:
                NotImplementedError: if fcs file format version is not supported
        """

        fcs_obj = open(fcs_file, 'rb')
        self.name = fcs_obj.name
        self.filepath = fcs_file

        version_id = fcs_obj.read(6).decode('utf-8')

        if version_id in ('FCS3.0', 'FCS3.1'):
            self.version = version_id
            self.__load_30(fcs_obj)
        else:
            raise NotImplementedError('Not able to parse {vid} files'.format(vid=version_id))

        self._fcs = fcs_obj
        vtxt = 'valid' if self.valid else 'invalid'
        print('---> fcs.load({}) - ver: {} - {}'.format(self.name, version_id[3:], vtxt))


    def __load_30(self, fcs_obj):
        """Load an FCS 3.0 file and read text section (metadata).

            Arg:
                f: A file descriptor
        """

        fcs_obj.seek(10)
        self.__header = {
            'text_start': int(fcs_obj.read(8).decode('utf-8')),
            'text_end': int(fcs_obj.read(8).decode('utf-8')),
            'data_start': int(fcs_obj.read(8).decode('utf-8')),
            'data_end': int(fcs_obj.read(8).decode('utf-8')),
            'analysis_start': filter_ascii32(fcs_obj.read(8).hex()),
            'analysis_end': filter_ascii32(fcs_obj.read(8).hex())}

        # Read the TEXT section
        fcs_obj.seek(self.__header['text_start'])
        text_delimiter = fcs_obj.read(1).decode('utf-8')
        _read_len = self.__header['text_end'] - self.__header['text_start']
        tokens = fcs_obj.read(_read_len).decode('utf-8').split(text_delimiter)

        # Collect Parameter keys and values for text map
        all_keys = [key.strip().upper() for key in tokens[::2] if key]
        all_vals = [filter_numeric(val.strip()) for val in tokens[1::2]]
        self.text = {key:val for key, val in zip(all_keys, all_vals)}

        if len(all_keys) > len(self.text):
            n = -1 * (len(all_keys) - len(self.text))
            self.param_keys = tuple(all_keys[:n])
        else:
            self.param_keys = tuple(all_keys)

        self.__update_key_set()

        self.load_spec()


    def load_spec(self):
        self.valid = validate.required_keywords(self.text)

        _metadata = Metadata(self.version, self.text)
        self.spec = _metadata.spec

        self.supported_format = validate.file_format(self.text, self.spec)



    # --------------------------------------------------------------------------
    def load_data(self, norm_count=False, norm_time=False):
        if not (self.__header or self._fcs):
            print('>>> No FCS file loaded.')
            return
        elif not self.supported_format:
            print('>>> XFCS cannot access the data section in this file.')
            return

        if self.spec.datatype == 'I':
            self.__read_int_data()
        else:
            self.__read_float_data()

        self._fcs.close()
        self.data = DataSection(self.__raw_data, self.spec, norm_count, norm_time)


    def __read_float_data(self):
        data_start, data_end = self.__get_data_seek()
        read_len = data_end - data_start
        if read_len + 1 == self.spec.data_len:
            read_len += 1

        self._fcs.seek(data_start)
        data_bytes = self._fcs.read(read_len)

        float_format = '{}{}'.format(self.spec.byteord, self.spec.datatype.lower())
        bytes_to_float = struct.Struct(float_format)
        self.__raw_data = tuple(chain.from_iterable(bytes_to_float.iter_unpack(data_bytes)))


    def __read_int_data(self):

        data_start, data_end = self.__get_data_seek()
        self._fcs.seek(data_start)

        nbytes = self.spec.word_len // 8
        tot_reads = self.spec.data_len // nbytes
        byteord = self.spec.byteord

        # transform hex data to separate, numerical entries
        bytes_to_int = int.from_bytes
        __raw_read = (self._fcs.read(nbytes) for _ in range(tot_reads))
        self.__raw_data = tuple(bytes_to_int(n, byteord) for n in __raw_read)


    def __get_data_seek(self):
        data_start = self.__header['data_start']
        data_end = self.__header['data_end']

        if not (data_start and data_end):
            data_start = self.spec.begindata
            data_end = self.spec.enddata

        return data_start, data_end


    # --------------------------------------------------------------------------
    def load_from_csv(self, keys_in, param_vals):
        """Initialize an FCSFile text attribute instance using keys, values from
            a previously generated csv file. Loads data for:
                self.text, self.param_keys, self.__key_set

        Args:
            keys_in: Parameter keys located in csv file
            param_vals: the keys respective values
        """

        for param, value in param_vals.items():
            self.set_param(param, value)

        self.param_keys = tuple(keys_in)
        self.__update_key_set()


    def __update_key_set(self):
        self.__key_set = set(self.text.keys())
        self.__n_keys = len(self.__key_set)


    def meta_hash(self, meta_keys=None):
        """Generates a hash fingerprint for the fcs file based on Parameter keys
            and their respective values. Key order is maintained. Accepts an
            optional subset of Parameter keys for use in comparing fcs files to
            partial data located in an appended csv file.

        Arg:
            meta_keys: iterable of Parameter keys to use in place of param_keys

        Returns:
            Calculated hash as str
        """

        txt = []
        if not meta_keys:
            meta_keys = self.param_keys

        for param in meta_keys:
            if param in ('SRC_DIR', 'CSV_CREATED'):
                continue
            txt.extend((param, str(self.text[param])))

        mrg_txt = ''.join(txt)
        return hash(mrg_txt)


    def has_param(self, key):
        """Return True if given parameter key is in text section"""

        if self.__n_keys != len(self.text):
            self.__update_key_set()

        return key in self.__key_set


    def param_is_numeric(self, param):
        """Return True if param value is numeric"""
        return isinstance(self.param(param), (float, int))


    def param(self, param):
        """Return the value for the given parameter"""
        return self.text.get(param, 'N/A')


    def numeric_param(self, param):
        """Return numeric value for the given parameter or zero"""
        return self.text.get(param, 0)


    def set_param(self, param, value):
        """Set the value of the given parameter"""
        if isinstance(value, str) and not value.isalpha():
            value = filter_numeric(value)
        self.text[param] = value


    def __write(self, f):
        """Write an FCS file (not implemented)"""
        raise NotImplementedError("Can't write FCS files yet")


# ------------------------------------------------------------------------------
