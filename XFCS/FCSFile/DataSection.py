
from itertools import islice
import os

import numpy as np
import pandas as pd

from XFCS.FCSFile.Parameter import Parameters
# ------------------------------------------------------------------------------

# ('begindata', 'byteord', 'channels', 'data_len', 'enddata',
# 'par', 'spillover', 'timestep', 'tot', 'word_len')

class DataSection(object):
    def __init__(self, raw_data, spec, datatype_i, norm_count=False):
        self.spec = spec
        self._comp_ids = []
        self._comp_matrix = None
        self.__raw = None
        self.__channel = None
        self.__channel_scale = None
        self.__scale = None
        self.__compensated = None
        self.__scale_compensated = None
        self.parameters = Parameters()
        self.parameters.set_datatype(datatype_i)
        self._load_channels(raw_data, norm_count)


    def _get_dtype(self, word_len):

        dmap = {'I':'uint{}'.format(word_len), 'F':'float32', 'D':'float64'}
        mode_dtype = dmap.get(self.spec.datatype)
        return np.dtype(mode_dtype)


    def _load_channels(self, raw_data, norm_count):
        par = self.spec.par
        word_len = self.spec.word_len
        dt = self._get_dtype(word_len)

        # slice all event data into separate channels
        raw_values = []
        for param_n in range(par):
            raw_channel = np.array(tuple(islice(raw_data, param_n, None, par)), dtype=dt)
            raw_values.append(raw_channel)

        self._load_param_config()
        self.parameters.set_raw_values(raw_values)
        self.parameters.set_channel_values(self.spec.timestep, norm_count)

        print('---> fcs.data.__load_channels: all raw and channel value loaded')


    def _load_param_config(self):
        if self.spec.spillover:
            self.__load_spillover_matrix()

        ch_spec = self.spec.channels
        self.parameters.load_config(ch_spec, self._comp_matrix, self._comp_ids)

    # --------------------------------------------------------------------------

    # def any_log_scaled(self):
    #     return self.parameters.has_logscale
    # def any_compensated(self):
    #     return self.parameters.has_logscale

    # --------------------------------------------------------------------------

    @property
    def raw(self):
        return self.parameters.get_raw()

    @property
    def channel(self):
        return self.parameters.get_channel()

    @property
    def scale(self):
        return self.parameters.get_scale()

    @property
    def channel_scale(self):
        return self.parameters.get_xcxs()

    @property
    def compensated(self):
        self.__load_compensated_channels()
        return self.parameters.get_compensated()

    @property
    def scale_compensated(self):
        self.__load_logscaled_compensated()
        return self.parameters.get_scale_compensated()

    # --------------------------------------------------------------------------

    def __load_spillover_matrix(self):
        # >>> check for neg vals

        spillover = self.spec.spillover.split(',')
        n_channels = int(spillover[0])
        self._comp_ids = [int(n) for n in spillover[1:n_channels + 1]]
        comp_vals = [float(n) for n in spillover[n_channels + 1:]]
        spill_matrix = np.array(comp_vals).reshape(n_channels, n_channels)
        diagonals = np.unique(spill_matrix[np.diag_indices(n_channels)])

        if diagonals.size != 1:
            print('Aborting fluorescence compensation')
            return False

        if diagonals.item(0) != 1:
            spill_matrix = spill_matrix / diagonals.item(0)
        self._comp_matrix = np.linalg.inv(spill_matrix)


    def __load_compensated_channels(self):
        if not self.spec.spillover:
            print('--> No $SPILLOVER data found within FCS Text Section.')
            return False

        if not self.__matrix_loaded:
            self.__load_spillover_matrix()

        self.parameters.compensate_channel_values(self._comp_ids, self._comp_matrix)
        print('---> fcs.data.parameters.compensated')
        return True


    def __load_logscaled_compensated(self):
        if not self.spec.spillover:
            print('--> No $SPILLOVER data found within FCS Text Section.')
            return

        if not self.__matrix_loaded:
            self.get_compensated()

        self.parameters.set_logscale_compensated(self._comp_ids, self._comp_matrix)
        print('---> fcs.data.parameters.scale_compensated')

    # --------------------------------------------------------------------------
