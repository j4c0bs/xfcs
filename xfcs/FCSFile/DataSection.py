
from itertools import islice

import numpy as np

from xfcs.FCSFile.ParameterData import ParameterData
# ------------------------------------------------------------------------------
class DataSection(object):
    """Instantiates a DataSection object.
    Separates raw data into separate parameter channels and delegates access to
    raw / transformed data within ParameterData. Performs final prep to read
    fluorescence compensation matrix and prepare comp factors, ids for use.
    """

    def __init__(self, raw_data, spec, norm_count, norm_time):
        """Initialize DataSection.

        Attributes:
            spec: namedtuple of all prepared metadata
            raw, channel, scale, channel_scale, compensated, scale_compensated:
                access points to retrieve data sets from ParameterData
        """

        self.spec = spec
        self._comp_matrix = None
        self.__raw = None
        self.__channel = None
        self.__channel_scale = None
        self.__scale = None
        self.__compensated = None
        self.__scale_compensated = None
        self._parameter_data = ParameterData(spec)
        self._load_parameter_channels(raw_data, norm_count, norm_time)


    def __dir__(self):
        """Prevents iPython tab complete from calling property descriptor attrs"""
        return self.keys()


    def _load_parameter_channels(self, raw_data, norm_count, norm_time):
        """Separates numeric raw data into individual parameter channels.
        Initializes ParameterData values, settings to prepare raw and channel
        values.

        Args:
            raw_data: fcs data section read from bytes to int or float
            norm_count: bool - enable count normalization
            norm_time: bool - enable time normalization
        """

        par = self.spec.par
        mode_dtype = np.dtype(self.spec.txt_dtype)

        # slice all event data into separate channels
        raw_values = []
        for param_n in range(par):
            raw_ch = np.array(tuple(islice(raw_data, param_n, None, par)), dtype=mode_dtype)
            raw_values.append(raw_ch)

        # set_ reference and channel values, load spillover matrix
        self._parameter_data.set_raw_values(raw_values)
        self._parameter_data.load_reference_channels(norm_count, norm_time)
        self._parameter_data.set_channel_values()
        if self.spec.spillover:
            comp_matrix_map, comp_ids = self.__load_spillover_matrix()
            self._parameter_data.set_compensation_matrix(comp_matrix_map, comp_ids)


    # --------------------------------------------------------------------------
    @property
    def raw(self):
        return self._parameter_data.get_raw()

    @property
    def channel(self):
        return self._parameter_data.get_channel()

    @property
    def scale(self):
        return self._parameter_data.get_scale()

    @property
    def channel_scale(self):
        return self._parameter_data.get_xcxs()

    @property
    def compensated(self):
        return self._parameter_data.get_compensated()

    @property
    def scale_compensated(self):
        return self._parameter_data.get_scale_compensated()

    # --------------------------------------------------------------------------
    def __load_spillover_matrix(self):
        """Calculates compensation matrix values based on spillover matrix.
        Due to the lack of consistency in fcs file formats, if spillover matrix
        contains negative values, it is assumed to be pre-formatted as the
        compensation matrix.

        Returns:
            comp_matrix_map: dict mapping numeric param id to compensation factor
            comp_ids: list of numeric param ids to compensate
        """

        spillover = self.spec.spillover.split(',')
        n_channels = int(spillover[0])

        param_ids = [n for n in spillover[1:n_channels + 1]]
        if all(id_.isdigit() for id_ in param_ids):
            comp_ids = tuple(int(n) for n in param_ids)
        else:
            comp_ids = tuple(self._parameter_data.id_map[p_id] for p_id in param_ids)

        comp_vals = [float(n) for n in spillover[n_channels + 1:]]
        spill_matrix = np.array(comp_vals).reshape(n_channels, n_channels)
        if np.any(spill_matrix < 0):
            print('>>> spillover matrix contains negative values.')
            self._comp_matrix = spill_matrix
            return spill_matrix, comp_ids

        diagonals = np.unique(spill_matrix[np.diag_indices(n_channels)])
        if diagonals.size != 1:
            print('>>> Aborting fluorescence compensation due to malformed matrix diagonals.')
            return {}, []

        if diagonals.item(0) != 1:
            spill_matrix = spill_matrix / diagonals.item(0)
        self._comp_matrix = np.linalg.inv(spill_matrix)

        comp_matrix_map = {}
        for ix, param_n in enumerate(comp_ids):
            comp_factor = self._comp_matrix[:,ix].sum()
            comp_matrix_map[param_n] = comp_factor

        return comp_matrix_map, comp_ids


    # --------------------------------------------------------------------------
