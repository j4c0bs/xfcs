"""
    FCS file reader supporting file format spec 3.0, 3.1.
    Data extraction currently supports:
        $MODE: (L) List
        $DATATYPE: I,F,D

    FCS3.0 http://murphylab.web.cmu.edu/FCSAPI/FCS3.html
    FCS3.1 https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2892967/
    A data set is a (HEADER, TEXT, DATA) group.
    Multiple data sets in one file is deprecated.

    A keyword is the label of a data field. A keyword-value pair is the label of the
    data field with its associated value. Keywords are unique in data sets,
    i.e., there are no multiple instances of the same keyword in the data set.

    --> keywords == params and are contained with FCSFile.text

    Required FCS primary TEXT segment keywords:
    $BEGINANALYSIS $BEGINDATA $BEGINSTEXT $BYTEORD $DATATYPE $ENDANALYSIS
    $ENDDATA $ENDSTEXT $MODE $NEXTDATA $PAR $TOT $PnB $PnE $PnN $PnR
"""

from itertools import chain
import os
import re
import struct

from xfcs.FCSFile.DataSection import DataSection
from xfcs.FCSFile.Metadata import Metadata
from xfcs.FCSFile import validate
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


def channel_name_keywords(meta_keys):
    """Finds any channel name keyword in the form: $PxN.

    Yields:
        keyword
    """

    spxn = re.compile(r'^\$P\d+N$', re.IGNORECASE)
    for key in meta_keys:
        if spxn.match(key):
            yield key


# ------------------------------------------------------------------------------
class FCSFile(object):
    """Instantiates an FCSFile object.

    Public Attributes:
        version: version ID for FCS file.
        name: filename of fcs file.
        parentdir: directory containing fcs file.
        text: dict containing all Parameter metadata key : value
        param_keys: iterable of Parameter keys in order of location in fcs text section
        data: Data class instance to access extracted data sets.

    Public Methods:
        load: Load an FCS file for reading and confirm version id is supported.
        load_data: Load Data Section for reading
        load_from_csv: Init FCSFile object from csv containing Parameter key, value pairs.

        check_file_format: Confirms metadata format.
        load_file_spec: Loads all header, text contents into namedtuple.
            Confirms if file is supported for data extraction.

        has_param: Confirm Parameter key in text section.
        param: Retrieve value for given Parameter key.
        numeric_param: Force retrieve numeric value for given Parameter key or 0.
        set_param: Sets value for given Parameter key within fcs.text.
        meta_hash: Generates unique fingerprint based on current Parameter key, value pairs.
            NOTE: this does not provide a hash value for the actual file.

    """

    def __init__(self, quiet=False):
        """Initialize an FCSFile object.

        Attributes:
            version: version ID for FCS file.
            name: filename of fcs file.
            parentdir: directory containing fcs file.
            text: dict of text section metadata Parameter key, value pairs.
            param_keys: iterable of Parameter keys in order of location in fcs
                text section.
            spec: namedtuple instance containing all necessary header, text values
                to extract and scale parameter data.
            data: Data class instance to access extracted data sets.

        """

        self.version = None
        self.name = ''
        self.parentdir = ''
        self.valid = False
        self.supported_format = False
        self._fcs = None
        self.__header = None
        self.text = {}
        self.param_keys = None
        self._param_values = None
        self.__key_set = {}
        self.__n_keys = 0
        self._name_id = None
        self.spec = None
        self.__hashkey = ''
        self.__raw_data = None
        self.data = None
        self.__supp_text = None
        self.__analysis = None
        self.quiet = quiet


    def load(self, fcs_file):
        """Load an FCS file and confirm version id is supported.

            Arg:
                f: A fcs filepath.
            Returns:
                f: A file descriptor
            Raises:
                NotImplementedError: if fcs file format version is not supported
        """

        if self._fcs:
            self.__init__()

        fcs_obj = open(fcs_file, 'rb')

        self.parentdir, self.name = os.path.split(os.path.abspath(fcs_file))

        version_id = fcs_obj.read(6).decode('utf-8')

        if version_id in ('FCS3.0', 'FCS3.1'):
            self.version = version_id
            self.__load_30(fcs_obj)
        else:
            raise NotImplementedError('Not able to parse {vid} files'.format(vid=version_id))

        self._fcs = fcs_obj


    def __load_30(self, fcs_obj):
        """Load an FCS 3.0 file and read text section (metadata).

        Arg:
            fcs_obj: A file descriptor
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
        _read_len = self.__header['text_end'] - self.__header['text_start'] - 1
        tokens = fcs_obj.read(_read_len).decode('utf-8').split(text_delimiter)

        # Collect Parameter keys and values for text map
        all_keys = tuple(key.strip().upper() for key in tokens[::2])
        all_vals = tuple(filter_numeric(val.strip()) for val in tokens[1::2])
        self.text = dict(zip(all_keys, all_vals))
        self.param_keys = all_keys
        self._param_values = all_vals

        self.__update_key_set()
        self.check_file_format()


    def close(self):
        if not self._fcs.closed:
            self._fcs.close()


    def check_file_format(self):
        self.valid = validate.required_keywords(self.text)
        self.supported_format = validate.file_mode_type(self.text)
        if not self.quiet:
            print('--> xfcs.load: {}'.format(self.name))


    def load_file_spec(self):
        _metadata = Metadata(self.version, self.text)
        self.spec = _metadata.spec


    # --------------------------------------------------------------------------
    def load_data(self, norm_count=False, norm_time=False):
        """Public access point to load and read the data section.

        Args:
            norm_count: bool - force event count to start at 1.
            norm_time: bool - force time to start at 0.
        """

        if not self.spec:
            self.load_file_spec()

        if not (self.__header or self._fcs):
            print('>>> No FCS file loaded.')
            return

        validate.file_format(self.text, self.spec)

        if self.spec.datatype == 'I':
            self.__read_int_data()
        else:
            self.__read_float_data()

        self._fcs.close()
        self.data = DataSection(self.__raw_data, self.spec, norm_count, norm_time)


    def __read_float_data(self):
        """Reads fcs $DATATYPE (F|D) - floats (32|64) bit word length"""

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
        """Reads fcs $DATATYPE I - integer data with fixed word length"""

        data_start, _ = self.__get_data_seek()
        self._fcs.seek(data_start)

        nbytes = self.spec.word_len // 8
        tot_reads = self.spec.data_len // nbytes
        byteord = self.spec.byteord

        # transform hex data to separate, numerical entries
        bytes_to_int = int.from_bytes
        __raw_read = (self._fcs.read(nbytes) for _ in range(tot_reads))
        self.__raw_data = tuple(bytes_to_int(n, byteord) for n in __raw_read)


    def __get_data_seek(self):
        """Finds data start and end values within either the header or text section"""
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
        self.name = self.text.get('SRC_FILE', '')


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
            if param in ('SRC_DIR', 'SRC_FILE', 'CSV_CREATED'):
                continue
            txt.extend((param, str(self.text[param])))

        return hash(''.join(txt))


    @property
    def hashkey(self):
        """Creates hash fingerprint using ordered text section keywords and
        values for required channel parameter keywords ($PxBENR).
        """

        if not self.__hashkey:
            ch_key = re.compile(r'^\$P\d+[BENR]$', re.IGNORECASE)
            ch_vals = (str(self.text[kw]) for kw in self.param_keys if ch_key.match(kw))
            self.__hashkey = hash(''.join(chain.from_iterable((self.param_keys, ch_vals))))
        return self.__hashkey


    def get_attr_by_channel_name(self, channel_name, attr):
        """Pre-format channel_name to remove spaces and force upper case.
            e.g. FL 5 Log --> FL5LOG
        """

        if not self._name_id:
            self._name_id = {
                v.replace(' ','').upper():k[:-1]
                for k,v in self.text.items()
                if k.startswith('$P') and k.endswith('N')}

        spx_id = self._name_id.get(channel_name, '') + attr
        return spx_id if self.has_param(spx_id) else ''


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


    def __write(self):
        """Write an FCS file (not implemented)"""
        raise NotImplementedError("Can't write FCS files yet")


# ------------------------------------------------------------------------------
