"""Prepares and verifies specific fcs text section parameters to be used in
data extraction.

Required FCS primary TEXT segment keywords:
$BEGINANALYSIS $BEGINDATA $BEGINSTEXT $BYTEORD $DATATYPE $ENDANALYSIS $ENDDATA
$ENDSTEXT $MODE $NEXTDATA $PAR $TOT $PnB $PnE $PnN $PnR
"""

from collections import namedtuple

import numpy as np
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


def test_spill_format(spill):
    """Confirms $SPILLOVER value has correct format.
    [# channels], [ch 1,...,ch n], [val 1, ..., val n**2]
    """

    if ',' not in spill and not spill[0].isdigit():
        return False

    spill_sep = spill.split(',')
    n_par = int(spill_sep[0])
    if len(spill_sep) != (1 + n_par + n_par**2):
        return False

    for val in spill_sep[n_par + 1:]:
        try:
            float(val)
        except ValueError:
            return False

    return True


def get_dtype_maxval(datatype, word_len):
    dmap = {'I':'uint{}'.format(word_len), 'F':'float32', 'D':'float64'}
    txt_dtype = dmap.get(datatype)
    mode_dtype = np.dtype(txt_dtype)
    n_info = np.iinfo if datatype == 'I' else np.finfo
    max_value = n_info(mode_dtype).max + 1
    return txt_dtype, max_value


# ------------------------------------------------------------------------------
class Metadata(object):
    """Instantiates an FCS Metadata object"""

    def __init__(self, version, text):
        """Initialize metadata section for FCS File"""

        self.version = version
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

        txt_dtype, max_val = get_dtype_maxval(self._text['$DATATYPE'], word_len)

        attr_names = ('channels', 'word_len', 'data_len', 'txt_dtype', 'max_val')
        vals = (channels, word_len, data_len, txt_dtype, max_val)

        for attr_name, val in zip(attr_names, vals):
            self._add_to_spec(attr_name, set_val=val)


    def _required_keywords(self):
        _read_keys = ('$BEGINDATA', '$ENDDATA', '$PAR', '$TOT', '$DATATYPE')
        for keyword in _read_keys:
            self._add_to_spec(keyword)

    def _set_optional_keywords(self):
        self._add_to_spec('$TIMESTEP', def_val=1)
        if self.version != 'FCS3.0' or '$SPILLOVER' in self._text:
            self._add_to_spec('$SPILLOVER')
        else:
            v3_spill = None
            sp_kws = ('$COMP', 'SPILL', 'SPILLOVER')
            for kw in sp_kws:
                spill = self._text.get(kw, None)
                if spill and test_spill_format(spill):
                    v3_spill = spill
                    break

            self._add_to_spec('$SPILLOVER', set_val=v3_spill)


    def _set_byteorder(self):
        type_i = self._text['$DATATYPE'] == 'I'
        byteord = x_endian(self._text['$BYTEORD'], type_i)
        self._add_to_spec('$BYTEORD', set_val=byteord)
        self._add_to_spec('type_i', set_val=type_i)


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
