"""
{'B': 16, 'E': '0.0,0.0', 'N': 'TIME', 'R': 65536, 'S': 'Time LSW'}

$PnN:   Short name for parameter n.
$PnS:   (optional) - Long name for parameter n.
$PnB:   Number of bits reserved for parameter number n.
$PnR:   Range for parameter number n.
$PnE:   Amplification type for parameter n.
    Incoming as str(f1,f2):
    f1 = log maximum decade and f2 = log minimum decade
    Most fcs files improperly use f2=0.0, f2=1.0 is assigned in this case.
"""

from collections import namedtuple
from itertools import compress
import numpy as np
import pandas as pd
# ------------------------------------------------------------------------------
def get_log_decade_min(f1, f2):
    if (f1 > 0) and (f2 == 0):
        return 1
    else:
        return f2


def fix_crossover(vals, max_val):
    """Conforms time, event count values to cumulative if actual value exceeds
    numeric maximum value for the file's word length.

    Args:
        vals: parameter's values as np.array
        max_val: int - maximum possible value based on word length

    Returns:
        vals: np.array - ascending, cumulative values
    """

    crossover_ix = np.where(vals[:-1] > vals[1:])[0]
    for ix in crossover_ix:
        vals = np.append(vals[:ix + 1], vals[ix + 1:] + max_val)
    return vals


# ------------------------------------------------------------------------------
def format_attr(type_i, **ch_spec):
    """Converts attributes for given parameter into useable format for data
    scaling and transforms.

    Args:
        type_i: bool - switch based on $DATATYPE to conform attr values
        ch_spec: all required parameter attr as dict

    Returns:
        tuple of param attr values
    """

    ch_vals = (ch_spec.get(spx_a) for spx_a in ('N', 'S', 'B', 'R', 'E', 'G'))
    name, long_name, word_len, max_range, scale, gain = ch_vals
    gain = 0 if not gain else gain

    if type_i:
        bit_range = (max_range - 1).bit_length()
        bit_mask = 2**bit_range - 1 if word_len != bit_range else 0
        max_range = max_range - 1 if not bit_mask else bit_mask
        f1_dec_max, f2 = map(float, scale.split(','))
        f2_dec_min = get_log_decade_min(f1_dec_max, f2)
    else:
        bit_mask, max_range, f1_dec_max, f2_dec_min = 0, 0, 0, 0

    vals = (name, long_name, word_len, bit_mask, max_range, f1_dec_max, f2_dec_min, gain)
    return vals


# def archyperbolicsine_scale(self, X):
#     return np.log(X + np.sqrt(np.exp2(X) + 1))

# ------------------------------------------------------------------------------
class ParameterData(object):
    """Instantiates a ParameterData object"""

    def __init__(self, spec):
        """Initializes ParameterData"""

        self.spec = spec
        self._config = None
        self.names = None
        self.par_ids = None
        self.ref_ids = []
        self.id_map = {}
        self._comp_matrix = None
        self.channel_ids = None
        self.bit_mask_ids = None
        self.log_ids = None
        self.linear_ids = None
        self.flcomp_ids = None
        self.log_flcomp_ids = None
        self._reference_channels = {}
        self.raw = None
        self.channel = {}
        self.scale = {}
        self.xcxs = {}
        self.compensated = {}
        self.logscale_compensated = {}
        self._load_config()


    def __dir__(self):
        return self.keys()

    # --------------------------------------------------------------------------
    def __get_dataframe(self, src_group, add_ref=True):
        """Converts data values dict to pandas DataFrame.

        Args:
            src_group: dict of data values mapped to parameter id number
            add_ref: bool to enable including time and count values in output

        Returns:
            tuple containing: parameter names list, DataFrame
            or (empty list, None) if values are unavailable
        """

        if not src_group:
            return ([], None)

        tmp_group = {}
        tmp_group.update(src_group)

        if add_ref and self._reference_channels:
            tmp_group.update(self._reference_channels)

        tmp_ids = sorted(tmp_group.keys())
        par_names = [self.id_map[id_] for id_ in tmp_ids]
        tmp_data = {name: tmp_group[id_] for name, id_ in zip(par_names, tmp_ids)}

        xs_df = pd.DataFrame(tmp_data, columns=par_names)
        return (par_names, xs_df)


    def __get_ch_attr(self, attr, dropzero=False):
        """Utility func to retrieve a specific attribute for all ParameterData and
            return either attribute values or the corresponding parameter ids.

        Args:
            attr: the attribute to retrieve
            dropzero: filters list of parameter ids to include if specified
                        attribute exists.

        Return:
            tuple of attribute values or parameter id numbers
        """

        vals = tuple(getattr(self._config.get(num), attr) for num in self.par_ids)
        if dropzero:
            vals = tuple(compress(self.par_ids, vals))
        return vals


    def __update_id_maps(self, name, id_):
        self.id_map.update({name:id_, id_:name})


    # --------------------------------------------------------------------------
    def __load_id_maps(self):
        """Creates symmetrical dict of all param names and their numeric id."""

        self.id_map.update(dict(zip(self.par_ids, self.names)))
        self.id_map.update(dict(zip(self.names, self.par_ids)))

        rdx_names = []
        for keyname in self.names:
            name_ = ''.join(s if s.isalpha() else ' ' for s in keyname).casefold()
            rdx_names.append(name_)

        self.__norm_name_map = dict(zip(rdx_names, self.names))


    def _load_config(self):
        """Formats channel attributes for use in data transforms. Stored in
        self._config dict mapping id to namedtuple.
        Initializes par_ids, names, id_maps.
        """

        channel_spec = self.spec.channels

        _spec_fields = (
            'name', 'long', 'word_len', 'bit_mask', 'max_range', 'log_max',
            'log_min', 'gain')

        ParamSpec = namedtuple('SPn', _spec_fields)

        self._config = {
            num: ParamSpec(*format_attr(self.spec.type_i, **channel_spec[num]))
            for num in channel_spec}

        self.par_ids = tuple(sorted(channel_spec.keys()))
        self.names = self.__get_ch_attr('name')
        self.__load_id_maps()


    # --------------------------------------------------------------------------
    def __locate_count_param(self):
        count_id = 0
        for key in self.__norm_name_map:
            if key == 'event count':
                count_id = self.id_map.get(self.__norm_name_map[key])
                break
        return count_id


    def __normalize_count(self, event_count):
        """Starts event count parameter at 1"""

        start_val = event_count.item(0)
        diff = start_val - 1
        if start_val < 0:
            print('>>> event count warning:', start_val)

        return event_count - diff


    def __scale_count(self, count_id, norm):
        """Applies bit mask and/or normalization to event count parameter.

        Args:
            count_id: numeric parameter id for event count
            norm: bool - user enabled option to enforce count starting at 1

        Returns:
            np.array event count values
        """

        event_count = self.raw[count_id]
        event_spec = self._config.get(count_id)
        if event_spec.bit_mask:
            event_count = self.__bit_mask_data(count_id)

        if norm and event_count.item(0) != 1:
            event_count = self.__normalize_count(event_count)

        return event_count


    def __load_ref_count(self, norm):
        """Locates or creates event count parameter. Checks for values exceeding
        maximum possible based on word length. Count is assigned to id -1 and
        stored in _reference_channels.

        Arg:
            norm: bool - user enabled option to enforce count starting at 1

        Returns:
            numeric parameter id (-1)
        """

        count_id = self.__locate_count_param()
        if count_id:
            event_count = self.__scale_count(count_id, norm)
        else:
            event_count = np.arange(1, len(self.raw[1]) + 1)

        if np.any(event_count[:-1] > event_count[1:]):
            event_count = fix_crossover(event_count, self.spec.max_val)

        self.__update_id_maps('Event Count', -1)
        self._reference_channels[-1] = event_count
        return count_id

    # --------------------------------------------------------------------------
    def __locate_time_params(self):
        """Locates any parameter name ($PnN or $PnS) containing time, msw, lsw.

        Returns:
            for each time param, numeric id or 0 if not located
        """

        time_id, time_lsw, time_msw = 0, 0, 0
        long_names = self.__get_ch_attr('long')
        for name, long_name in zip(self.names, long_names):
            name_id = self.id_map.get(name)
            if long_name:
                keywords = (name.casefold(), long_name.casefold())
            else:
                keywords = (name.casefold(),)

            in_keyword_name = lambda wrd: any(wrd in kw for kw in keywords)
            if in_keyword_name('time'):
                if in_keyword_name('lsw'):
                    time_lsw = name_id
                elif in_keyword_name('msw'):
                    time_msw = name_id
                else:
                    time_id = name_id

        return time_lsw, time_msw, time_id


    def __encode_time(self, time_lsw, time_msw):
        """Converts 2 single word length time parameters into actual, double word
        length time measurement.

        Args:
            time_lsw: lsw time parameter id
            time_msw: msw time parameter id

        Returns:
            np.array - actual time values
        """

        msw_word_len = self._config.get(time_msw).word_len
        msw_data = self.raw.get(time_msw)
        lsw_data = self.raw.get(time_lsw)
        double_word = ((msw_data << msw_word_len) | lsw_data)
        return double_word


    def __load_ref_time(self, norm):
        """Loads time parameter and determines if it exists, or it is split
        between lsw and msw. Applies $TIMESTEP (and gain) factor.
        Stored in _reference_channels as id 0.

        Arg:
            norm: bool - user enabled option to enforce time starting at 0.0

        Returns:
            list of non-zero time ids
        """

        time_lsw, time_msw, time_id = self.__locate_time_params()
        if time_id and (time_lsw or time_msw) and not(time_lsw and time_msw):
            if time_lsw:
                time_msw = time_id
            else:
                time_lsw = time_id
            time_id = 0

        elif all((time_lsw, time_msw, time_id)):
            time_id = 0
        elif not any((time_lsw, time_msw, time_id)):
            return 0, 0, 0

        if time_id or (time_lsw and time_msw):
            gain_factor = 1

            if time_lsw and time_msw:
                time_channel = self.__encode_time(time_lsw, time_msw)
            else:
                time_spec = self._config[time_id]
                time_channel = self.raw.get(time_id)
                if time_spec.gain:
                    gain_factor = time_spec.gain

            # check for time roll over
            if np.any(time_channel[:-1] > time_channel[1:]):
                time_channel = fix_crossover(time_channel, self.spec.max_val)

            time_channel = time_channel * self.spec.timestep / gain_factor
            if norm and time_channel[0] != 0:
                time_channel = time_channel - time_channel[0]

            self.__update_id_maps('TIME', 0)
            self._reference_channels[0] = time_channel

        return [t_id for t_id in (time_lsw, time_msw, time_id) if t_id]


    def load_reference_channels(self, norm_count, norm_time):
        """Initializes time and event count parameters to be stored in
        _reference_channels under ids 0, -1. Filters any time, event count ids
        from par_ids.

        Args:
            norm_count: bool - user enabled option to enforce count starting at 1
            norm_time: bool - user enabled option to enforce time starting at 0.0
        """

        time_ids = self.__load_ref_time(norm_time)
        if time_ids:
            self.ref_ids.extend(time_ids)

        count_id = self.__load_ref_count(norm_count)
        self.ref_ids.append(count_id)
        self.par_ids = tuple(id_ for id_ in self.par_ids if id_ not in self.ref_ids)


    # --------------------------------------------------------------------------
    def get_raw(self):
        return self.__get_dataframe(self.raw, add_ref=False)

    def get_channel(self):
        return self.__get_dataframe(self.channel)

    def get_scale(self):
        if not self.scale:
            self.set_scale_values()
        return self.__get_dataframe(self.scale)

    def get_xcxs(self):
        if not self.xcxs:
            self.set_xcxs_values()
        return self.__get_dataframe(self.xcxs)

    def get_compensated(self):
        if self._has_compensation() and not self.compensated:
            self.set_compensated_values()
        return self.__get_dataframe(self.compensated)

    def get_scale_compensated(self):
        if self._has_compensation(xch='Scaled ') and not self.logscale_compensated:
            self.set_logscale_compensated()
        return self.__get_dataframe(self.logscale_compensated)

    # --------------------------------------------------------------------------
    def set_raw_values(self, raw_channels):
        self.raw = dict(zip(self.par_ids, raw_channels))


    def __bit_mask_data(self, param_n):
        data = self.raw.get(param_n)
        spec_n = self._config.get(param_n)
        mask = spec_n.bit_mask
        return mask & data


    # --------------------------------------------------------------------------
    def _set_group_ids(self):
        """Configs group ids for channel, log scale, gain scale, xcxs data sets.
        Compensation id groups are configured separately alongside comp matrix.
        """

        self.channel_ids = self.par_ids[:]
        self.bit_mask_ids = self.__get_ch_attr('bit_mask', dropzero=True)

        # set scale ids for log and gain
        self.log_ids = self.__get_ch_attr('log_max', dropzero=True)
        gain_mask = [(n != 0 and n != 1) for n in self.__get_ch_attr('gain')]
        self.gain_ids = tuple(compress(self.par_ids, gain_mask))

        # set channel_scale / xcxs ids
        self.linear_ids = tuple(set(self.channel_ids) - set(self.log_ids))


    def set_channel_values(self):
        """All parameters, with bit mask if applicable."""

        self._set_group_ids()

        for param_n in self.bit_mask_ids:
            self.channel[param_n] = self.__bit_mask_data(param_n)

        ch_to_include = set(self.par_ids) - set(self.bit_mask_ids)
        self.channel.update({param_n:self.raw[param_n] for param_n in ch_to_include})


    def set_xcxs_values(self):
        """Channel parameters without log scaling, any log scaled parameters."""

        if not self.scale:
            self.set_scale_values()

        linlog_sets = (self.channel, self.scale)
        linlog_ids = (self.linear_ids, self.log_ids)
        for data_set, data_ids in zip(linlog_sets, linlog_ids):
            self.xcxs.update({p_id:data_set[p_id] for p_id in data_ids})


    # --------------------------------------------------------------------------
    def __log_scale(self, param_n, src_group):
        """Applies log10 scaing based on $PnE value.

        Args:
            param_n: parameter id
            src_group: data set for parameter source values to be scaled

        Returns:
            np.array with log10 scaled values
        """

        spec_ = self._config.get(param_n)
        param_data = src_group.get(param_n)
        return 10**(spec_.log_max * param_data / spec_.max_range) * spec_.log_min


    def __gain_scale(self, param_n, src_group):
        """Applies gain scaling based on $PnG value."""

        spec_ = self._config.get(param_n)
        param_data = src_group.get(param_n)
        return param_data / spec_.gain


    def set_scale_values(self):
        """All parameters that have log10 or gain scaling applied.
        Parameters cannot have both scaling methods.
        """

        for param_n in self.log_ids:
            log_data = self.__log_scale(param_n, self.channel)
            self.scale[param_n] = log_data

        if self.gain_ids:
            for param_n in self.gain_ids:
                gain_data = self.__gain_scale(param_n, self.channel)
                self.scale[param_n] = gain_data


    # --------------------------------------------------------------------------
    def _has_compensation(self, xch=''):
        if not self.spec.spillover:
            print('>>> {}Fluorescence compensation is disabled - $SPILLOVER missing.'.format(xch))
            return False
        else:
            return True

    def set_compensation_matrix(self, comp_matrix_map, fl_comp_ids):
        """Sets values for compensation matrix, id groups.
        _comp_matrix is a dict mapping param id to compensation factor.
        """

        self._comp_matrix = comp_matrix_map
        self.flcomp_ids = fl_comp_ids
        self.log_flcomp_ids = tuple(set(self.log_ids) & set(self.flcomp_ids))


    def set_compensated_values(self):
        """Applies compensation scaling for any parameter located in compensation
        matrix ($SPILLOVER).
        """

        for param_n in self.flcomp_ids:
            param_data = self.channel.get(param_n)
            comp_factor = self._comp_matrix[param_n]
            self.compensated[param_n] = param_data * comp_factor


    def set_logscale_compensated(self):
        """Applies log10 scaling for parameters located in compensation matrix
        that have a log10 scaling value.
        """

        if not self.log_flcomp_ids:
            print('>>> No compensated parameters have log scaling.')
            return

        if not self.compensated:
            self.set_compensated_values()

        for param_n in self.log_flcomp_ids:
            log_ = self.__log_scale(param_n, self.compensated)
            self.logscale_compensated[param_n] = log_


# ------------------------------------------------------------------------------
