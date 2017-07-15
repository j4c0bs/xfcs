"""Prepares and verifies specific fcs text section parameters to be used in
data extraction.

Required FCS primary TEXT segment keywords:
$BEGINANALYSIS $BEGINDATA $BEGINSTEXT $BYTEORD $DATATYPE $ENDANALYSIS $ENDDATA
$ENDSTEXT $MODE $NEXTDATA $PAR $PnB $PnE $PnN $PnR $TOT
"""

from collections import namedtuple
from operator import itemgetter
# ------------------------------------------------------------------------------
def x_endian(byte_ord):
    """Determines data byte order based on fcs file format specifications.

        Arg:
            byte_ord: fcs text section value for $BYTEORD

        Returns:
            str: little | big - for use in DataSection.

        Raises:
            ValueError - file spec provides only 2 options for this parameter.
    """

    if byte_ord == '1,2,3,4':
        return 'little'
    elif byte_ord == '4,3,2,1':
        return 'big'
    else:
        raise ValueError


# ------------------------------------------------------------------------------
def verify_format(datatype, mode):

    status = True

    if mode != 'L':
        print('FCS MODE NOT SUPPORTED - LIST MODE ONLY:', mode)
        status = False

    if datatype != 'I':
        print('FCS DATA TYPE NOT SUPPORTED:', datatype)
        status = False

    return status


def verify_bytes(word_len_set, par, tot):
    """Verify metadata values for byte word length and total length of data section.
        In a list mode fcs file with datatype I, all parameters have the same
        word length.

        Total bit len of data = number params * number events * word length

    Args:
        word_len_set: set of all parameters word length ($PnB) value.
        par: int - number of parameters.
        tot: int - total number of events recorded.

    Returns:
        status: bool - False if any check failed.
        word_len: int - number of bits reserved per parameter event.
        data_len: int - total number of bytes to read for data section.
    """

    status = True
    word_len = 0
    data_len = 0

    if not word_len_set:
        print('DATA BYTE READ LENGTH MISSING:')
        status = False
    elif len(word_len_set) > 1:
        print('DATA BYTE READ LENGTH NOT STANDARD FOR ALL CHANNELS:')
        print(word_len_set)
        status = False
    else:
        word_len = word_len_set.pop()
        # TODO: confirm word lens are multiples of 8 <---
        if not word_len or word_len % 8 != 0:
            print('DATA BYTE READ LENGTH NOT RECOGNIZED: {}'.format(word_len))
            status = False

    if status:
        data_len = par * tot * word_len // 8

    return status, word_len, data_len


# ------------------------------------------------------------------------------
class Metadata(object):
    def __init__(self, text):
        """Initialize metadata section for FCS File"""

        self.__text = text
        self.__data_spec = {}
        self.__spec = None
        self.__format_status = False
        self.__bytes_status = False
        self.has_valid_format = False
        self.__load_keywords()


    # def __getattr__(self, item):
    #     if item in self.__data_spec:
    #         return self.__data_spec.get(item)
    #     else:
    #         raise AttributeError

    @property
    def spec(self):
        return self.__spec


    def __add_to_spec(self, keyword, def_val=None, val_format=None):
        spec_key = keyword.strip('$').lower()
        if val_format:
            val = val_format(self.__text.get(keyword, def_val))
        else:
            val = self.__text.get(keyword, def_val)
        self.__data_spec[spec_key] = val


    def __make_spec_pkg(self):
        spec_keys = sorted(self.__data_spec.keys())
        spec_vals = [self.__data_spec.get(k) for k in spec_keys]
        DataSpec = namedtuple('spec', spec_keys)
        self.__spec = DataSpec(*spec_vals)


    def __load_keywords(self):
        self.__required_keywords()
        self.__load_optional_keywords()
        all_word_lens, channels = self.__load_channel_spec()

        par, tot = self.__text['$PAR'], self.__text['$TOT']
        self.__bytes_status, word_len, data_len = verify_bytes(all_word_lens, par, tot)

        self.has_valid_format = (self.__format_status and self.__bytes_status)

        self.__add_to_spec('word_len', def_val=word_len)
        self.__add_to_spec('data_len', def_val=data_len)
        self.__add_to_spec('channels', def_val=channels)
        self.__make_spec_pkg()


    def __required_keywords(self):
        type_keys = ('$DATATYPE', '$MODE')
        self.__format_status = verify_format(*(self.__text.get(kw) for kw in type_keys))

        self.__add_to_spec('$BYTEORD', val_format=x_endian)
        _read_keys = ('$BEGINDATA', '$ENDDATA', '$PAR', '$TOT')
        for keyword in _read_keys:
            self.__add_to_spec(keyword)


    def __load_optional_keywords(self):
        self.__add_to_spec('$TIMESTEP', 0)
        self.__add_to_spec('$SPILLOVER')


    def __load_channel_spec(self):
        """self.channel['$P9'] = {'N':'long', 'S':'name', 'B':word_len, ...}
        """

        n_parameters = self.__data_spec['par']
        param_attr = ('N', 'S', 'B', 'E', 'R')
        __get_byte = itemgetter(2)
        all_word_lens = set()
        channels = {}

        for param_n in range(1, n_parameters + 1):
            par_keywords = ['$P{}{}'.format(param_n, attr) for attr in param_attr]
            vals = [self.__text.get(keyword) for keyword in par_keywords]

            # par_name = '$P{}'.format(param_n)
            channels[param_n] = dict(zip(param_attr, vals))
            all_word_lens.add(__get_byte(vals))

        return all_word_lens, channels



# ------------------------------------------------------------------------------
