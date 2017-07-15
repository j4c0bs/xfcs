
from itertools import islice
import os

import numpy as np
import pandas as pd

from XFCS.FCSFile.Parameter import Parameters
# ------------------------------------------------------------------------------

# ('begindata', 'byteord', 'channels', 'data_len', 'enddata', 'par', 'spillover',
# 'timestep', 'tot', 'word_len')
# >>> add in access to data values --> fcs.data.channel ?

class DataSection(object):
    def __init__(self, raw_data, spec):
        self.spec = spec
        self.parameters = Parameters(spec.channels)
        self.__separate_channels(raw_data)
        # self.__load_channel_values()
        self.__channel_values = None
        self.__scale_values = None
        self.__comp_ids = None
        self.__compensation_matrix = None


    def __separate_channels(self, raw_data):
        par = self.spec.par
        word_len = self.spec.word_len
        dt = np.dtype('uint{}'.format(word_len))

        # slice all event data into separate channels
        raw_values = []
        for param_n in range(par):
            raw_channel = np.array(tuple(islice(raw_data, param_n, None, par)), dtype=dt)
            raw_values.append(raw_channel)

        self.parameters.set_raw_values(raw_values)
        self.parameters.set_channel_values(self.spec.timestep)
        print('---> DataSection.__separate_channels: all raw and channel value loaded')


    def __load_channel_values(self):
        self.parameters.set_channel_values(self.spec.timestep)
        print('---> all raw and channel value loaded')

    @property
    def channel_values(self):
        return self.__channel_values

    def channel_df(self):
        return self.parameters.get_channel_df()

    @property
    def scale_values(self):
        if not self.__scale_values:
            self.parameters.set_logscale_values()
            self.__scale_values = self.parameters.scale
        return self.__scale_values

    def logscale_df(self):
        if not self.__scale_values:
            self.parameters.set_logscale_values()
            self.__scale_values = self.parameters.scale
        return self.parameters.get_logscale_df()


    def __load_spillover_matrix(self):
        # >>> check for neg vals
        spillover = self.spec.spillover.split(',')
        n_channels = int(spillover[0])
        self.__comp_ids = [int(n) for n in spillover[1:n_channels + 1]]
        comp_vals = [float(n) for n in spillover[n_channels + 1:]]
        spill_matrix = np.array(comp_vals).reshape(n_channels, n_channels)
        diagonals = np.unique(spill_matrix[np.diag_indices(n_channels)])

        if diagonals.size != 1:
            print('Aborting fluorescence compensation')
            return False

        if diagonals.item(0) != 1:
            spill_matrix = spill_matrix / diagonals.item(0)
        self.__compensation_matrix = np.linalg.inv(spill_matrix)

    def load_compensated_channels(self):
        if not self.spec.spillover:
            print('--> No $SPILLOVER data found within FCS Text Section.')
            return

        if not self.__compensation_matrix:
            self.__load_spillover_matrix()
        self.parameters.compensate_channel(self.__comp_ids, self.__compensation_matrix)
        print('---> fcs.data.parameters.compensated')

    def load_logscaled_compensated(self):
        if not self.spec.spillover:
            print('--> No $SPILLOVER data found within FCS Text Section.')
            return

        if not self.__compensation_matrix:
            self.get_compensated_channel()
        self.parameters.logscale_comp_channel(self.__comp_ids, self.__compensation_matrix)
        print('---> fcs.data.parameters.scale_compensated')

    # --------------------------------------------------------------------------

    # def store_csv_data(self, data_folder):
    #     dcsv = self.data_name + '.csv'
    #     fn = os.path.join(data_folder, dcsv)
    #     self.xc_df.to_csv(fn, index=False)
    #     return fn
    #
    # def store_hdf5_data(self, data_folder):
    #     fn_hdf = self.data_name + '.h5'
    #     fn = os.path.join(data_folder, fn_hdf)
    #
    #     self.xc_df.to_hdf(fn, self.data_name, mode='w', complib='zlib', complevel=9)
    #
    #     return fn_hdf

    # --------------------------------------------------------------------------
