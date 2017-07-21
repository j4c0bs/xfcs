
from itertools import islice

import numpy as np

from XFCS.FCSFile.Parameter import Parameters
# ------------------------------------------------------------------------------
class DataSection(object):
    def __init__(self, raw_data, spec, norm_count, norm_time):
        self.spec = spec
        self._comp_ids = []
        self._comp_matrix = None
        self.__raw = None
        self.__channel = None
        self.__channel_scale = None
        self.__scale = None
        self.__compensated = None
        self.__scale_compensated = None
        self.parameters = Parameters(spec)
        self._load_parameter_channels(raw_data, norm_count, norm_time)


    def _load_parameter_channels(self, raw_data, norm_count, norm_time):
        par = self.spec.par
        mode_dtype = np.dtype(self.spec.txt_dtype)

        # slice all event data into separate channels
        raw_values = []
        for param_n in range(par):
            raw_ch = np.array(tuple(islice(raw_data, param_n, None, par)), dtype=mode_dtype)
            raw_values.append(raw_ch)

        # set_ reference and channel values, load spillover matrix
        self.parameters.set_raw_values(raw_values)
        self.parameters.load_reference_channels(norm_count, norm_time)
        self.parameters.set_channel_values()
        if self.spec.spillover:
            self.__load_spillover_matrix()
            self.parameters.set_spillover(self._comp_matrix, self._comp_ids)
        print('---> All data read and channels loaded.')


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
        if self.spec.spillover:
            return self.parameters.get_compensated()
        else:
            print('>>> No $SPILLOVER data found within FCS Text Section.')
            return None

    @property
    def scale_compensated(self):
        if self.spec.spillover:
            return self.parameters.get_scale_compensated()
        else:
            print('>>> No $SPILLOVER data found within FCS Text Section.')
            return None

    # --------------------------------------------------------------------------

    def __load_spillover_matrix(self):

        spillover = self.spec.spillover.split(',')
        n_channels = int(spillover[0])

        param_ids = [n for n in spillover[1:n_channels + 1]]
        if all(id_.isdigit() for id_ in param_ids):
            self._comp_ids = tuple(int(n) for n in param_ids)
        else:
            self._comp_ids = tuple(self.parameters.id_map[p_id] for p_id in param_ids)

        comp_vals = [float(n) for n in spillover[n_channels + 1:]]
        spill_matrix = np.array(comp_vals).reshape(n_channels, n_channels)
        if np.any(spill_matrix < 0):
            print('>>> spillover matrix contains negative values')
            self._comp_matrix = spill_matrix
            return

        diagonals = np.unique(spill_matrix[np.diag_indices(n_channels)])
        if diagonals.size != 1:
            print('>>> Aborting fluorescence compensation')
            return

        if diagonals.item(0) != 1:
            spill_matrix = spill_matrix / diagonals.item(0)
        self._comp_matrix = np.linalg.inv(spill_matrix)


    # --------------------------------------------------------------------------
