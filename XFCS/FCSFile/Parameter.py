# {'B': 16, 'E': '0.0,0.0', 'N': 'TIME', 'R': 65536, 'S': 'Time LSW'}
"""
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
import sys
import numpy as np
import pandas as pd
# ------------------------------------------------------------------------------
def get_log_decade_min(f1, f2):
    if (f1 > 0) and (f2 == 0):
        return 1
    else:
        return f2


# ------------------------------------------------------------------------------
_spec_fields = (
    'name', 'long', 'word_len', 'bit_mask', 'max_range', 'log_max', 'log_min', 'gain')

ParamSpec = namedtuple('Spec', _spec_fields)


def load_param_spec(type_i=True, **ch_spec):
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
    return ParamSpec(*vals)


# def archyperbolicsine_scale(self, X):
#     return np.log(X + np.sqrt(np.exp2(X) + 1))

# ------------------------------------------------------------------------------
class Parameters(object):
    def __init__(self, datatype_i):
        self._type_i = datatype_i
        self._norm_count = True
        self._config = None
        self.names = None
        self.par_ids = None
        self.ref_ids = []
        self._reference_channels = {}
        self.channel_ids = None
        self.bit_mask_ids = []
        self.log_ids = []
        self.linear_ids = []
        self.fl_comp_ids = []
        self.log_fl_comp_ids = []
        self._comp_matrix = None

        self.raw = None
        self.channel = {}
        self.scale = {}
        self.xcxs = {}
        self.compensated = {}
        self.logscale_compensated = {}
        self.id_map = {}

        self._timestep = 0

        self._ref_channels = {}
        self._time = None
        self._event_count = None

    # --------------------------------------------------------------------------
    def __get_dataframe(self, src_group, add_ref=True):
        if not src_group:
            return None

        tmp_group = {}
        tmp_group.update(src_group)

        if add_ref and self._reference_channels:
            tmp_group.update(self._reference_channels)

        tmp_ids = sorted(tmp_group.keys())
        tmp_names = [self.id_map[id_] for id_ in tmp_ids]
        tmp_data = {name: tmp_group[id_] for name, id_ in zip(tmp_names, tmp_ids)}

        xs_df = pd.DataFrame(tmp_data, columns=tmp_names)
        return xs_df


    def __get_ch_attr(self, attr, dropzero=False):
        vals = tuple(getattr(self._config.get(num), attr) for num in self.par_ids)
        if dropzero:
            vals = tuple(compress(self.par_ids, vals))
        return vals

    def __update_id_maps(self, name, id_):
        self.id_map.update({name:id_, id_:name})


    # --------------------------------------------------------------------------
    def __locate_count_param(self):
        count_id = 0
        for key in self.__norm_name_map:
            if key == 'event count':
                count_id = self.id_map.get(self.__norm_name_map[key])
                break
        return count_id

    def __normalize_count(self, count_id):
        event_count = self.raw[count_id]
        event_spec = self._config.get(count_id)
        if event_spec.bit_mask:
            event_count = self.__bit_mask_data(count_id)

        start_val = event_count.item(0)
        if start_val < 0:
            print('>>> event count warning:', start_val)
            return event_count

        if start_val != 1:
            if start_val > 0:
                diff = start_val - 1
            elif start_val == 0:
                diff = -1
            event_count = event_count - diff

        # check for count roll over
        if np.any(event_count==0):
            zero = np.where(event_count == 0)[0].item()
            max_count = event_count[zero-1] + 1
            event_count = np.append(event_count[:zero], event_count[zero:] + max_count)

        return event_count

    def __load_event_count(self):
        count_id = self.__locate_count_param()
        if count_id:
            event_count = self.__normalize_count(count_id)
        else:
            event_count = np.arange(1, len(self.raw[1]) + 1)

        self.__update_id_maps('Event Count', -1)
        self._reference_channels[-1] = event_count
        return count_id

    # --------------------------------------------------------------------------
    def __locate_time_params(self):
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


    def __encode_time(self, time_lsw, time_msw, timestep):
        msw_word_len = self._config.get(time_msw).word_len
        msw_data = self.raw.get(time_msw)
        lsw_data = self.raw.get(time_lsw)
        double_word = ((msw_data << msw_word_len) | lsw_data)
        delta = double_word - double_word[0]
        enc_time = delta * timestep
        return enc_time


    def __load_channel_time(self, timestep):
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
            if time_lsw and time_msw:
                time_channel = self.__encode_time(time_lsw, time_msw, timestep)
            else:
                time_channel = self.raw.get(time_id) * timestep
                time_spec = self._config[time_id]
                if time_spec.gain:
                    time_channel = time_channel / time_spec.gain

            self.__update_id_maps('TIME', 0)
            self._reference_channels[0] = time_channel

        return time_lsw, time_msw, time_id


    def __set_time_reference(self, timestep):
        time_ids = self.__load_channel_time(timestep)
        return [t for t in time_ids if t]

    def load_reference_channels(self, timestep, norm_count):

        if timestep:
            time_ids = self.__set_time_reference(timestep)
            self.ref_ids.extend(time_ids)

        # if norm_count:
        count_id = self.__load_event_count()
        self.ref_ids.append(count_id)

        self.par_ids = tuple(id_ for id_ in self.par_ids if id_ not in self.ref_ids)
        self.channel_ids = self.par_ids[:]

    # --------------------------------------------------------------------------
    def __load_id_maps(self):

        self.id_map.update(dict(zip(self.par_ids, self.names)))
        self.id_map.update(dict(zip(self.names, self.par_ids)))

        rdx_names = []
        for keyname in self.names:
            name_ = ''.join(s if s.isalpha() else ' ' for s in keyname).casefold()
            rdx_names.append(name_)

        self.__norm_name_map = dict(zip(rdx_names, self.names))


    def load_config(self, channel_spec):
        self._config = {
            num: load_param_spec(type_i=self._type_i, **channel_spec[num])
            for num in channel_spec}

        self.par_ids = tuple(sorted(channel_spec.keys()))
        self.names = self.__get_ch_attr('name')
        self.__load_id_maps()


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
        if not self.compensated:
            self.set_compensated_values()
        return self.__get_dataframe(self.compensated)

    def get_scale_compensated(self):
        if not self.logscale_compensated:
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
    def set_channel_values(self):

        bit_mask_ids = self.__get_ch_attr('bit_mask', dropzero=True)
        for param_n in bit_mask_ids:
            self.channel[param_n] = self.__bit_mask_data(param_n)

        ch_to_include = [num for num in self.par_ids if num not in bit_mask_ids]
        self.channel.update({param_n:self.raw[param_n] for param_n in ch_to_include})


    def set_xcxs_values(self):
        """channel values and any log scaled params
        """

        if not self.scale:
            self.set_scale_values()

        self.linear_ids = tuple(id_ for id_ in self.channel.keys() if id_ not in self.log_ids)

        linlog_sets = (self.channel, self.scale)
        linlog_ids = (self.linear_ids, self.log_ids)
        for data_set, data_ids in zip(linlog_sets, linlog_ids):
            self.xcxs.update({p_id:data_set[p_id] for p_id in data_ids})


    # --------------------------------------------------------------------------
    def __log_scale(self, param_n, src_group):
        spec_ = self._config.get(param_n)
        param_data = src_group.get(param_n)
        return 10**(spec_.log_max * param_data / spec_.max_range) * spec_.log_min

    def __gain_scale(self, param_n, src_group):
        spec_ = self._config.get(param_n)
        print('--> __gain_scale({}), gain={}'.format(param_n, spec_.gain))
        param_data = src_group.get(param_n)
        return param_data / spec_.gain

    def set_scale_values(self):

        self.log_ids = self.__get_ch_attr('log_max', dropzero=True)
        gain_mask = [(n != 0 and n != 1) for n in self.__get_ch_attr('gain')]
        self.gain_ids = tuple(compress(self.par_ids, gain_mask))

        for param_n in self.log_ids:
            log_data = self.__log_scale(param_n, self.channel)
            self.scale[param_n] = log_data

        # ---> $Param can have gain or log but not both
        if self.gain_ids:
            for param_n in self.gain_ids:
                gain_data = self.__gain_scale(param_n, self.channel)
                self.scale[param_n] = gain_data


    # --------------------------------------------------------------------------
    def load_spillover(self, fl_comp_matrix, fl_comp_ids):
        self._comp_matrix, self.fl_comp_ids = fl_comp_matrix, fl_comp_ids


    def set_compensated_values(self):
        for ix, param_n in enumerate(self.fl_comp_ids):
            param_data = self.channel.get(param_n)
            comp_factor = self._comp_matrix[:,ix].sum()
            self.compensated[param_n] = param_data * comp_factor

    def set_logscale_compensated(self):
        log_fl_comp_ids = tuple(set(self.log_ids) & set(self.fl_comp_ids))
        if not log_fl_comp_ids:
            print('>>> No compensated params have log scaling.')
            return

        if not self.compensated:
            self.set_compensated_values()

        for param_n in log_fl_comp_ids:
            log_ = self.__log_scale(param_n, self.compensated)
            self.logscale_compensated[param_n] = log_


# ------------------------------------------------------------------------------
