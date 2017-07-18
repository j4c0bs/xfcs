"""Prepares and verifies specific fcs text section parameters to be used in
data extraction.

Required FCS primary TEXT segment keywords:
$BEGINANALYSIS $BEGINDATA $BEGINSTEXT $BYTEORD $DATATYPE $ENDANALYSIS $ENDDATA
$ENDSTEXT $MODE $NEXTDATA $PAR $TOT $PnB $PnE $PnN $PnR
"""

from collections import namedtuple
# from operator import itemgetter
# ------------------------------------------------------------------------------
def x_endian(byte_ord, type_i=True):
    """Determines data byte order based on fcs file format specifications.

        Args:
            byte_ord: fcs text section value for $BYTEORD
            type_i: bool - selects proper return value for $DATATYPE I or F/D

        Returns:
            str: little|big or <|> for use in converting bytes to numeric.

        Raises:
            ValueError - fcs documentation specifies only 2 options for this parameter.
    """

    if byte_ord == '1,2,3,4':
        return 'little' if type_i else '<'
    elif byte_ord == '4,3,2,1':
        return 'big' if type_i else '>'
    else:
        raise ValueError


# ------------------------------------------------------------------------------

# def verify_format(datatype, mode):
#
#     status = True
#
#     if mode != 'L':
#         print('FCS MODE NOT SUPPORTED - LIST MODE ONLY:', mode)
#         status = False
#
#     if datatype != 'I':
#         print('FCS DATA TYPE NOT SUPPORTED:', datatype)
#         status = False
#
#     return status

# def verify_bytes(word_len_set, par, tot):
#     """Verify metadata values for byte word length and total length of data section.
#         In a list mode fcs file with datatype I, all parameters have the same
#         word length.
#
#         Total bit len of data = number params * number events * word length
#
#     Args:
#         word_len_set: set of all parameters word length ($PnB) value.
#         par: int - number of parameters.
#         tot: int - total number of events recorded.
#
#     Returns:
#         status: bool - False if any check failed.
#         word_len: int - number of bits reserved per parameter event.
#         data_len: int - total number of bytes to read for data section.
#     """
#
#     status = True
#     word_len = 0
#     data_len = 0
#
#     if not word_len_set:
#         print('DATA BYTE READ LENGTH MISSING:')
#         status = False
#     elif len(word_len_set) > 1:
#         print('DATA BYTE READ LENGTH NOT STANDARD FOR ALL CHANNELS:')
#         print(word_len_set)
#         status = False
#     else:
#         word_len = word_len_set.pop()
#         # TODO: confirm word lens are multiples of 8
#         if not word_len or word_len % 8 != 0:
#             print('DATA BYTE READ LENGTH NOT RECOGNIZED: {}'.format(word_len))
#             status = False
#
#     if status:
#         data_len = par * tot * word_len // 8
#
#     return status, word_len, data_len

# ------------------------------------------------------------------------------
class Metadata(object):
    def __init__(self, text):
        """Initialize metadata section for FCS File"""

        self._text = text
        self._data_spec = {}
        self.__spec = None
        self._load_keywords()
        self._make_spec_pkg()


    @property
    def spec(self):
        return self.__spec

    def _add_to_spec(self, keyword, set_val=None, def_val=None, val_format=None):
        spec_key = keyword.strip('$').lower()
        if val_format:
            val = val_format(self._text.get(keyword, def_val))
        elif set_val:
            val = set_val
        else:
            val = self._text.get(keyword, def_val)
        self._data_spec[spec_key] = val

    def _make_spec_pkg(self):
        spec_keys = sorted(self._data_spec.keys())
        spec_vals = [self._data_spec.get(k) for k in spec_keys]
        DataSpec = namedtuple('spec', spec_keys)
        self.__spec = DataSpec(*spec_vals)

    # --------------------------------------------------------------------------
    def _load_keywords(self):
        self._required_keywords()
        self._set_optional_keywords()
        self._set_byteorder()
        channels = self._load_channel_spec()
        word_len = self._get_word_len(channels)
        data_len = self._get_data_len(word_len)
        self._add_to_spec('channels', set_val=channels)
        self._add_to_spec('word_len', set_val=word_len)
        self._add_to_spec('data_len', set_val=data_len)

    def _required_keywords(self):
        _read_keys = ('$BEGINDATA', '$ENDDATA', '$PAR', '$TOT', '$DATATYPE')
        for keyword in _read_keys:
            self._add_to_spec(keyword)

    def _set_optional_keywords(self):
        self._add_to_spec('$TIMESTEP', def_val=0)
        self._add_to_spec('$SPILLOVER')

    def _set_byteorder(self):
        type_i = self._text['$DATATYPE'] == 'I'
        byteord = x_endian(self._text['$BYTEORD'], type_i)
        self._add_to_spec('$BYTEORD', set_val=byteord)

    def _get_word_len(self, channels):
        all_word_len = set(ch_val['B'] for ch_val in channels.values())
        if len(all_word_len) != 1:
            return 0
        else:
            return all_word_len.pop()

    def _get_data_len(self, word_len):
        par, tot = self._text['$PAR'], self._text['$TOT']
        return par * tot * word_len // 8

    def _load_channel_spec(self):
        """self.channel['$P9'] = {'N':'long', 'S':'name', 'B':word_len, ...}
        """

        n_parameters = self._data_spec['par']
        param_attr = ('N', 'S', 'B', 'E', 'R', 'G')
        channels = {}

        for param_n in range(1, n_parameters + 1):
            base = '$P{}'.format(param_n)
            par_keywords = (base + attr for attr in param_attr)
            vals = [self._text.get(keyword) for keyword in par_keywords]
            channels[param_n] = dict(zip(param_attr, vals))

        return channels


# ------------------------------------------------------------------------------
