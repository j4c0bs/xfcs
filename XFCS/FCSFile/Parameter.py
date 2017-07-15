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
import numpy as np
import pandas as pd
# ------------------------------------------------------------------------------
ParamSpec = namedtuple('Spec', ('name', 'long', 'word_len', 'bit_mask', 'max_range', 'log_max', 'log_min'))


# ------------------------------------------------------------------------------
def get_log_decade_min(f1, f2):
    if (f1 > 0) and (f2 == 0):
        return 1
    else:
        return f2


# ------------------------------------------------------------------------------
def load_param_spec(N='', S='', B=0, R=0, E=''):
    name = N
    long_name = S
    word_len = B
    max_range = R
    scale = E

    # bit_redux = word_len - bit_range
    bit_range = (max_range - 1).bit_length()
    bit_mask = 2**bit_range - 1 if word_len != bit_range else 0
    max_range = max_range - 1 if not bit_mask else bit_mask
    f1_dec_max, f2 = map(float, scale.split(','))
    f2_dec_min = get_log_decade_min(f1_dec_max, f2)
    data_vals = (name, long_name, word_len, bit_mask, max_range, f1_dec_max, f2_dec_min)
    return ParamSpec(*data_vals)


# def archyperbolicsine_scale(self, X):
#     return np.log(X + np.sqrt(np.exp2(X) + 1))

# ------------------------------------------------------------------------------
class Parameters(object):
    def __init__(self, channel_spec):
        self._config = None
        self.par_id = None
        self.names = None
        self.has_bit_mask = None
        self.has_log_scale = None

        self.raw = None
        self.channel = {}
        self.scale = {}
        self.compensated = {}
        self.scale_compensated = {}

        self.__num_to_name = None
        self.__name_to_num = None

        self.__load_config_spec(channel_spec)


    # --------------------------------------------------------------------------
    # def get_by_id(self, *p_nums):
    # def by_name(self, *short_names):
    #     for name in short_names:
    #         par_n = self.__name_to_num.get(name)


    def __get_ch_attr(self, attr, dropzero=False):
        vals = tuple(getattr(self._config.get(num), attr) for num in self.par_id)
        if dropzero:
            vals = tuple(compress(self.par_id, vals))
        return vals

    def __load_id_maps(self):
        self.__num_to_name = dict(zip(self.par_id, self.names))
        self.__name_to_num = dict(zip(self.names, self.par_id))

    def __update_id_maps(self, name, id_):
        self.__name_to_num.update({name:id_})
        self.__num_to_name.update({id_:name})

    def __load_config_spec(self, channel_spec):
        self._config = {num: load_param_spec(**spec) for num, spec in channel_spec.items()}
        self.par_id = tuple(sorted(channel_spec.keys()))
        self.names = self.__get_ch_attr('name')
        self.__load_id_maps()
        self.has_bit_mask = self.__get_ch_attr('bit_mask', dropzero=True)
        self.has_log_scale = self.__get_ch_attr('log_max', dropzero=True)


    def __get_dataframe(self, src_group):

        # TODO: set df.dtype with word_len
        p_ids = sorted(src_group.keys())
        p_names = [self.__num_to_name[id_] for id_ in p_ids]
        tmp_data = {p_name: src_group[id_] for p_name, id_ in zip(p_names, p_ids)}
        xs_df = pd.DataFrame(tmp_data, columns=p_names)
        xs_df.index = xs_df.index + 1
        return xs_df


    # --------------------------------------------------------------------------
    def set_raw_values(self, raw_channels):
        if self.raw:
            print('>>> Raw channel data is being overwritten')
        self.raw = dict(zip(self.par_id, raw_channels))


    def __locate_time_params(self):
        time_id = 0
        time_lsw = 0
        time_msw = 0
        long_names = self.__get_ch_attr('long')

        for name, long_name in zip(self.names, long_names):
            name_id = self.__name_to_num.get(name)
            keywords = (name.casefold(), long_name.casefold())
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

    def __load_time_params(self, timestep):

        time_ids = []
        time_lsw, time_msw, time_id = self.__locate_time_params()
        if (time_lsw and time_msw) and not time_id:
            enc_time = self.__encode_time(time_lsw, time_msw, timestep)
            self.channel[0] = enc_time
            self.__update_id_maps('TIME', 0)
            time_ids.extend((time_lsw, time_msw))

        elif time_id and not (time_lsw and time_msw):
            self.channel[time_id] = self.raw.get(time_id) * timestep
            time_ids.append(time_id)
        else:
            print('>>> Time Parameter Error')
        return time_ids


    def __bit_mask_data(self, param_n):
        data = self.raw.get(param_n)
        spec_n = self._config.get(param_n)
        mask = spec_n.bit_mask
        return mask & data


    def set_channel_values(self, timestep):

        ch_to_transform = []
        if timestep:
            time_ids = self.__load_time_params(timestep)
            ch_to_transform.extend(time_ids)

        ch_to_transform.extend(self.has_bit_mask)
        ch_to_include = [num for num in self.par_id if num not in ch_to_transform]

        for param_n in self.has_bit_mask:
            self.channel[param_n] = self.__bit_mask_data(param_n)

        self.channel.update({param_n:self.raw[param_n] for param_n in ch_to_include})
        print('---> channel values set')


    # --------------------------------------------------------------------------
    def get_channel_df(self):
        return self.__get_dataframe(self.channel)


    def get_channel_scaled_df(self):
        """channel values and any log scaled params
        """

        channel_lin = [p_id for p_id in self.channel if p_id not in self.scale]
        cs_data = {self.__num_to_name[p_id]:self.channel[p_id] for p_id in channel_lin}
        cs_data.update({self.__num_to_name[p_id]:self.scale[p_id] for p_id in self.scale})

        all_ids = []
        all_ids.extend(channel_lin)
        all_ids.extend(self.scale.keys())
        all_ids.sort()

        columns = [self.__num_to_name[p_id] for p_id in all_ids]

        xcs_df = pd.DataFrame(cs_data, columns=columns)
        xcs_df.index = xcs_df.index + 1
        return xcs_df


    # --------------------------------------------------------------------------
    def __log_scale(self, param_n, src_group):
        spec_ = self._config.get(param_n)
        param_data = src_group.get(param_n)
        return 10**(spec_.log_max * param_data / spec_.max_range) * spec_.log_min

    def set_logscale_values(self):
        for param_n in self.has_log_scale:
            log_ = self.__log_scale(param_n, self.channel)
            self.scale[param_n] = log_
        print('---> (log)scale values set')

    def get_logscale_df(self):
        return self.__get_dataframe(self.scale)

    def compensate_channel(self, param_ids, compensation_matrix):
        for ix, param_n in enumerate(param_ids):
            param_data = self.channel.get(param_n)
            comp_factor = compensation_matrix[:,ix].sum()
            self.compensated[param_n] = param_data * comp_factor

    def logscale_comp_channel(self, param_ids, compensation_matrix):
        for param_n in param_ids:
            log_ = self.__log_scale(param_n, self.compensated)
            self.scale_compensated[param_n] = log_



# ------------------------------------------------------------------------------
