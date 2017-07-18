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
    def __init__(self):
        self._type_i = None
        self._config = None
        self.par_ids = None
        self.names = None

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

        self._ref_channels = {}
        self._time = None
        self._event_count = None

    # --------------------------------------------------------------------------
    def set_datatype(self, type_i):
        self._type_i = type_i


    def __get_dataframe(self, src_group, add_ref=False):

        if not src_group:
            return None

        p_ids = sorted(src_group.keys())
        p_names = [self.id_map[id_] for id_ in p_ids]
        tmp_data = {p_name: src_group[id_] for p_name, id_ in zip(p_names, p_ids)}
        if add_ref:
            tmp_data.update(self._ref_channels)
            p_names.extend(key for key in self._ref_channels if key not in p_names)

        xs_df = pd.DataFrame(tmp_data, columns=p_names)
        return xs_df


    # --------------------------------------------------------------------------
    def __get_ch_attr(self, attr, dropzero=False):
        vals = tuple(getattr(self._config.get(num), attr) for num in self.par_ids)
        if dropzero:
            vals = tuple(compress(self.par_ids, vals))
        return vals

    def __update_id_maps(self, name, id_):
        self.id_map.update({name:id_, id_:name})


    def __load_id_maps(self):

        self.id_map.update(dict(zip(self.par_ids, self.names)))
        self.id_map.update(dict(zip(self.names, self.par_ids)))

        rdx_names = []
        for keyname in self.names:
            name_ = ''.join(s if s.isalpha() else ' ' for s in keyname).casefold()
            rdx_names.append(name_)

        self.__norm_name_map = dict(zip(rdx_names, self.names))


    def __load_id_groups(self):
        # >>> deal w time ids missing after channel
        self.bit_mask_ids = self.__get_ch_attr('bit_mask', dropzero=True)

        gain_mask = [(n != 0 and n != 1) for n in self.__get_ch_attr('gain')]
        self.gain_ids = tuple(compress(self.par_ids, gain_mask))

        self.log_ids = self.__get_ch_attr('log_max', dropzero=True)
        self.log_fl_comp_ids = tuple(set(self.log_ids) & set(self.fl_comp_ids))


    def load_config(self, channel_spec, fl_comp_matrix, fl_comp_ids):
        self._config = {
            num: load_param_spec(type_i=self._type_i, **channel_spec[num])
            for num in channel_spec}

        self.par_ids = tuple(sorted(channel_spec.keys()))
        self.names = self.__get_ch_attr('name')
        self.__load_id_maps()
        self._comp_matrix, self.fl_comp_ids = fl_comp_matrix, fl_comp_ids

        self.__load_id_groups()


    # --------------------------------------------------------------------------
    def get_raw(self):
        return self.__get_dataframe(self.raw)

    def get_channel(self):
        return self.__get_dataframe(self.channel)

    def get_scale(self):
        if not self.scale:
            self.set_scale_values()
        return self.__get_dataframe(self.scale, add_ref=True)

    def get_xcxs(self):
        if not self.xcxs:
            self.set_xcxs_values()
        return self.__get_dataframe(self.xcxs, add_ref=True)

    def get_compensated(self):
        return self.__get_dataframe(self.compensated)

    def get_scale_compensated(self):
        return self.__get_dataframe(self.logscale_compensated, add_ref=True)

    # --------------------------------------------------------------------------
    def set_raw_values(self, raw_channels):
        self.raw = dict(zip(self.par_ids, raw_channels))
        print('---> raw values set')


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

        time_ids = []
        time_lsw, time_msw, time_id = self.__locate_time_params()
        if not any((time_lsw, time_msw, time_id)):
            print('>>> Time Parameter Error: no $PnN TIME param located, $TIMESTEP in text section.')
            sys.exit(0)
        elif not time_id and not (time_lsw and time_msw):
            print('>>> Time error 2.')
            sys.exit(0)


        if (time_lsw and time_msw) and not time_id:
            _scaled_time = self.__encode_time(time_lsw, time_msw, timestep)
            time_ids.extend((time_lsw, time_msw))

        elif time_id and not (time_lsw and time_msw):
            _scaled_time = self.raw.get(time_id) * timestep
            time_ids.append(time_id)

        self.channel[time_id] = _scaled_time
        self._ref_channels['TIME'] = _scaled_time
        self.__update_id_maps('TIME', 0)
        return time_ids


    def __locate_count_param(self):
        count_id = 0
        for key in self.__norm_name_map:
            if key == 'event count':
                count_id = self.id_map.get(self.__norm_name_map[key])
                break
        return count_id


    def __normalize_count(self, count_id):
        # TODO: check for count roll over
        ev_count = self.raw[count_id]
        start_val = ev_count.item(0)
        if start_val < 0:
            print('>>> Event Count has negative values.')
            print('>>> Aborting data extraction.')
            sys.exit(0)

        if start_val != 1:
            if start_val > 0:
                diff = start_val - 1
            elif start_val == 0:
                diff = -1

            ev_count = ev_count - diff

        self.channel[count_id] = ev_count
        key = self.id_map[count_id]
        self._ref_channels[key] = ev_count
        return count_id


    def __load_event_count(self):
        count_id = self.__locate_count_param()
        if count_id:
            self.__normalize_count(count_id)
        else:
            count_id = -1
            ev_count = np.arange(1, len(self.raw[1]) + 1)
            self.channel[count_id] = ev_count
            self._ref_channels['Event Count'] = ev_count

        return count_id


    def __bit_mask_data(self, param_n):
        data = self.raw.get(param_n)
        spec_n = self._config.get(param_n)
        mask = spec_n.bit_mask
        return mask & data


    # --------------------------------------------------------------------------
    def set_channel_values(self, timestep, norm_count=False):

        ch_to_transform = []

        if timestep:
            time_ids = self.__load_channel_time(timestep)
            ch_to_transform.extend(time_ids)

        if norm_count:
            count_id = self.__load_event_count()
            ch_to_transform.append(count_id)

        ch_to_transform.extend(self.bit_mask_ids)
        for param_n in self.bit_mask_ids:
            self.channel[param_n] = self.__bit_mask_data(param_n)

        ch_to_include = [num for num in self.par_ids if num not in ch_to_transform]
        self.channel.update({param_n:self.raw[param_n] for param_n in ch_to_include})

        print('---> channel values set')


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
        print('--> gain == 1:', spec_.gain == 1)

        param_data = src_group.get(param_n)
        return param_data / spec_.gain

    def set_scale_values(self):

        print('\n>>> self.log_ids:', self.log_ids)

        for param_n in self.log_ids:
            log_data = self.__log_scale(param_n, self.channel)
            self.scale[param_n] = log_data

        # ---> $Param can have gain or log but not both
        if self.gain_ids:
            for param_n in self.gain_ids:
                gain_data = self.__gain_scale(param_n, self.channel)
                self.scale[param_n] = gain_data

        print('---> fcs.data.parameters.set_scale_values: log set')


    # --------------------------------------------------------------------------
    def compensate_channel_values(self, param_ids, compensation_matrix):
        for ix, param_n in enumerate(param_ids):
            param_data = self.channel.get(param_n)
            comp_factor = compensation_matrix[:,ix].sum()
            self.compensated[param_n] = param_data * comp_factor

    def set_logscale_compensated(self, param_ids, compensation_matrix):
        for param_n in param_ids:
            log_ = self.__log_scale(param_n, self.compensated)
            self.logscale_compensated[param_n] = log_


# ------------------------------------------------------------------------------
